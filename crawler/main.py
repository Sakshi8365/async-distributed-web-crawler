from __future__ import annotations

import argparse
import asyncio
import sys
from typing import List
from urllib.parse import urlparse
import os
import time
import json
from datetime import datetime, timezone

from redis.asyncio import Redis

from .config import load_config
from .frontier import Frontier
from .storage import Storage
from .worker import Worker
from .dupe import VISITED_SET


async def seed_cmd(redis: Redis, urls: List[str]) -> None:
    frontier = Frontier(redis)
    await frontier.push_many(urls)
    print(f"Seeded {len(urls)} URLs")


async def stats_cmd(redis: Redis, storage: Storage) -> None:
    from .dupe import VISITED_SET
    from .frontier import FRONTIER_ZSET

    frontier_sz = await redis.zcard(FRONTIER_ZSET)
    visited = await redis.scard(VISITED_SET)
    pages = await storage.count_pages()
    print(f"Frontier: {frontier_sz}, Visited: {visited}, Pages: {pages}")


async def run_cmd(concurrency: int, max_pages: int | None) -> None:
    cfg = load_config()
    redis = Redis.from_url(cfg.redis_url, decode_responses=False)
    storage = Storage(cfg.mongo_url, cfg.mongo_db)
    await storage.init()

    # Reset per-run metrics counters
    try:
        await redis.set("metrics:robots_blocked", 0)
    except Exception:
        pass

    # Seed from config if provided
    if cfg.seed_urls:
        await seed_cmd(redis, list(cfg.seed_urls))

    # Start N workers
    stop_event = asyncio.Event()

    async def worker_task():
        w = Worker(cfg, redis, storage)
        await w.run(stop_event)

    tasks = [asyncio.create_task(worker_task()) for _ in range(max(1, concurrency))]

    # Monitor for max_pages if requested
    start_ts = time.time()
    start_visited = await redis.scard(VISITED_SET)

    async def monitor():
        if not max_pages:
            return
        target = start_visited + max_pages
        while not stop_event.is_set():
            curr = await redis.scard(VISITED_SET)
            if curr >= target:
                stop_event.set()
                break
            await asyncio.sleep(0.2)

    mon_task = asyncio.create_task(monitor())
    try:
        await asyncio.gather(*tasks, mon_task)
    except asyncio.CancelledError:
        pass

    # Metrics and export
    end_ts = time.time()
    curr = await redis.scard(VISITED_SET)
    pages_crawled = max(0, curr - start_visited)
    duration = max(1e-6, end_ts - start_ts)
    pps = pages_crawled / duration

    os.makedirs("output", exist_ok=True)
    metrics = {
        "pages_crawled": pages_crawled,
        "duration_seconds": duration,
        "pages_per_second": pps,
        "start_ts": start_ts,
        "end_ts": end_ts,
    }

    # Aggregate status codes for pages in this run window
    try:
        pipeline = [
            {"$match": {"timestamp": {"$gte": start_ts}}},
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        ]
        status_counts: dict[str, int] = {}
        async for doc in storage._pages.aggregate(pipeline):  # type: ignore
            status = str(doc.get("_id"))
            status_counts[status] = int(doc.get("count", 0))
        try:
            robots_blocked = int(await redis.get("metrics:robots_blocked") or 0)
        except Exception:
            robots_blocked = 0
        metrics["status_counts"] = status_counts
        metrics["robots_blocked"] = robots_blocked
    except Exception:
        pass
    with open("output/metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # Export graph edges seen in this run (filter by timestamp)
    # Limit to a reasonable number of rows if very large
    MAX_EDGES = 200000
    written = 0
    async for doc in storage._pages.find({"timestamp": {"$gte": start_ts}}, {"url": 1, "links": 1, "_id": 0}):
        src = doc.get("url")
        links = doc.get("links", [])
        if not src or not links:
            continue
        # Lazy open per first write
        if written == 0:
            outf = open("output/graph.csv", "w", encoding="utf-8")
            outf.write("src,dst\n")
        for dst in links:
            outf.write(f"{src},{dst}\n")
            written += 1
            if written >= MAX_EDGES:
                break
        if written >= MAX_EDGES:
            break
    if written > 0:
        outf.close()
    # Graceful teardown of resources
    try:
        await storage.close()
    except Exception:
        pass
    try:
        await redis.aclose()
    except Exception:
        pass

    print(f"Run complete: pages={pages_crawled}, pps={pps:.2f}. Metrics at output/metrics.json. Graph at output/graph.csv{'' if written>0 else ' (no edges)'}.")


def dump_status(path_json: str = "output/status.json", path_html: str = "output/dashboard.html") -> None:
    """Dump current crawler status (frontier, visited, pages) to JSON and static HTML."""
    cfg = load_config()
    redis = Redis.from_url(cfg.redis_url, decode_responses=False)
    storage = Storage(cfg.mongo_url, cfg.mongo_db)
    async def _do():
        await storage.init()
        from .dupe import VISITED_SET
        from .frontier import FRONTIER_ZSET
        frontier_sz = await redis.zcard(FRONTIER_ZSET)
        visited = await redis.scard(VISITED_SET)
        pages = await storage.count_pages()
        ts = datetime.now(timezone.utc).isoformat()
        data = {"frontier": frontier_sz, "visited": visited, "pages": pages, "ts": ts}
        os.makedirs("output", exist_ok=True)
        with open(path_json, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        dash = f"""<html><head><meta charset='utf-8'><title>Crawler Dashboard</title>
        <meta http-equiv='refresh' content='15'>
        <style>body{{font-family:Arial;margin:1.5rem;}}table{{border-collapse:collapse}}td,th{{padding:4px 8px;border:1px solid #ddd}}</style></head><body>
        <h1>Crawler Dashboard Snapshot</h1>
        <table><tr><th>Frontier</th><th>Visited</th><th>Pages Stored</th><th>Timestamp (UTC)</th></tr>
        <tr><td>{frontier_sz}</td><td>{visited}</td><td>{pages}</td><td>{ts}</td></tr></table>
        <p>Refresh after running <code>dump-status</code> again for updated numbers.</p>
        <p>Raw JSON: <code>{path_json}</code></p>
        </body></html>"""
        with open(path_html, "w", encoding="utf-8") as f:
            f.write(dash)
        print(f"Status written: {path_json}, {path_html}")
        try:
            await storage.close()
        except Exception:
            pass
        try:
            await redis.aclose()
        except Exception:
            pass
    asyncio.run(_do())


def main() -> None:
    parser = argparse.ArgumentParser(description="Distributed Web Crawler")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="Seed URLs into the frontier")
    p_seed.add_argument("urls", nargs="+", help="One or more URLs")

    p_stats = sub.add_parser("stats", help="Show basic stats")

    p_run = sub.add_parser("run", help="Run workers")
    p_run.add_argument("--concurrency", type=int, default=None, help="Worker count (defaults to CONCURRENCY)")
    p_run.add_argument("--max-pages", type=int, default=None, help="Stop after crawling this many pages (approximate)")

    p_dump = sub.add_parser("dump-status", help="Write status.json and dashboard.html snapshot")
    p_domain = sub.add_parser("domain-stats", help="Show top domains in frontier, visited, stored pages")
    p_domain.add_argument("--limit", type=int, default=15, help="Number of domains to show")
    p_domain.add_argument("--json", action="store_true", help="Output JSON instead of table")

    args = parser.parse_args()

    cfg = load_config()
    redis = Redis.from_url(cfg.redis_url, decode_responses=False)
    storage = Storage(cfg.mongo_url, cfg.mongo_db)

    if args.cmd == "seed":
        async def seed_entry():
            await seed_cmd(redis, args.urls)
            try:
                await redis.aclose()
            except Exception:
                pass
        asyncio.run(seed_entry())
    elif args.cmd == "stats":
        async def stats_entry():
            await storage.init()
            await stats_cmd(redis, storage)
            try:
                await storage.close()
            except Exception:
                pass
            try:
                await redis.aclose()
            except Exception:
                pass
        asyncio.run(stats_entry())
    elif args.cmd == "run":
        conc = args.concurrency if args.concurrency is not None else cfg.concurrency
        try:
            asyncio.run(run_cmd(conc, args.max_pages))
        except KeyboardInterrupt:
            print("\nShutting down...")
    elif args.cmd == "dump-status":
        dump_status()
    elif args.cmd == "domain-stats":
        async def domain_stats_entry():
            await storage.init()
            from .frontier import FRONTIER_ZSET
            from .dupe import VISITED_SET
            import collections, urllib.parse

            # Frontier domains
            frontier_counts = collections.Counter()
            cursor = 0
            while True:
                cursor, items = await redis.zscan(FRONTIER_ZSET, cursor=cursor, count=500)
                for member, _score in items:
                    url = member.decode() if isinstance(member, (bytes, bytearray)) else member
                    host = urllib.parse.urlparse(url).hostname or ""
                    if host.startswith("www."): host = host[4:]
                    if host: frontier_counts[host] += 1
                if cursor == 0: break

            # Visited domains
            visited_counts = collections.Counter()
            cursor = 0
            while True:
                cursor, batch = await redis.sscan(VISITED_SET, cursor=cursor, count=1000)
                for member in batch:
                    url = member.decode() if isinstance(member, (bytes, bytearray)) else member
                    host = urllib.parse.urlparse(url).hostname or ""
                    if host.startswith("www."): host = host[4:]
                    if host: visited_counts[host] += 1
                if cursor == 0: break

            # Stored pages domains (Mongo aggregate)
            stored_counts = collections.Counter()
            pipeline = [
                {"$group": {"_id": "$domain", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": args.limit},
            ]
            async for doc in storage._pages.aggregate(pipeline):
                d = doc.get("_id") or ""
                if d: stored_counts[d] = doc.get("count", 0)

            def top(counter) -> list[tuple[str, int]]:  # type: ignore
                return [(str(dom), int(cnt)) for dom, cnt in counter.most_common(args.limit)]

            data = {
                "frontier": top(frontier_counts),
                "visited": top(visited_counts),
                "stored": top(stored_counts),
            }
            if args.json:
                print(json.dumps(data, indent=2))
            else:
                def print_table(title: str, rows: list[tuple[str, int]]) -> None:
                    print(f"\n{title} (top {len(rows)})")
                    print("Domain".ljust(40), "Count")
                    for dom, cnt in rows:
                        print(dom.ljust(40), cnt)
                print_table("Frontier Domains", data["frontier"])
                print_table("Visited Domains", data["visited"])
                print_table("Stored Domains", data["stored"])
            try:
                await storage.close()
            except Exception:
                pass
            try:
                await redis.aclose()
            except Exception:
                pass
        asyncio.run(domain_stats_entry())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
