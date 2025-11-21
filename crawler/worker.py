from __future__ import annotations

import asyncio
import time
from typing import Optional
from urllib.parse import urlparse

import aiohttp
from redis.asyncio import Redis

from .config import Config
from .dupe import Dedupe
from .frontier import Frontier
from .parser import extract_links
from .rate_limiter import RateLimiter
from .robots import Robots
from .storage import Storage


class Worker:
    def __init__(self, cfg: Config, redis: Redis, storage: Storage):
        self.cfg = cfg
        self.redis = redis
        self.frontier = Frontier(redis)
        self.dupe = Dedupe(redis)
        self.rl = RateLimiter(redis)
        self.robots = Robots(redis, cfg.user_agent)
        self.storage = storage

    async def _fetch(
        self, session: aiohttp.ClientSession, url: str
    ) -> tuple[int, Optional[str], Optional[str]]:
        attempts = 0
        delay = 0.5
        last_status: int = 0
        last_ctype: Optional[str] = None
        last_html: Optional[str] = None
        while attempts < 3:
            try:
                async with session.get(
                    url,
                    timeout=self.cfg.request_timeout_seconds,
                    headers={"User-Agent": self.cfg.user_agent},
                ) as resp:
                    ctype = resp.headers.get("Content-Type")
                    if resp.status != 200 or (
                        ctype and "text/html" not in ctype.lower()
                    ):
                        await resp.read()
                        last_status, last_ctype, last_html = resp.status, ctype, None
                    else:
                        body = await resp.content.read(
                            self.cfg.max_content_size_bytes + 1
                        )
                        if len(body) > self.cfg.max_content_size_bytes:
                            last_status, last_ctype, last_html = 200, ctype, None
                        else:
                            last_status, last_ctype, last_html = (
                                200,
                                ctype,
                                body.decode(errors="ignore"),
                            )
                break  # successful attempt (even if non-200 we stop)
            except Exception:
                last_status, last_ctype, last_html = 0, None, None
                attempts += 1
                if attempts < 3:
                    await asyncio.sleep(delay)
                    delay *= 2
        return last_status, last_ctype, last_html

    async def process_one(self, session: aiohttp.ClientSession) -> bool:
        urls = await self.frontier.pop_ready(max_count=1)
        if not urls:
            return False
        url = urls[0]

        # Dedup
        if await self.dupe.is_visited(url):
            return True

        # Politeness: robots + rate limiter
        allowed = await self.robots.is_allowed(session, url)
        if not allowed:
            # Count robots disallowed occurrences for metrics
            try:
                await self.redis.incr("metrics:robots_blocked")
            except Exception:
                pass
            await self.dupe.mark_visited(url)
            return True

        domain = (urlparse(url).hostname or "").lower()
        allowed_at, reserved = await self.rl.check_and_reserve(
            domain, self.cfg.domain_cooldown_seconds
        )
        if not reserved:
            # Not yet allowed; reschedule URL for its allowed_at
            await self.frontier.push(url, scheduled_at=allowed_at)
            return True

        status, ctype, html = await self._fetch(session, url)
        ts = time.time()
        title = ""
        new_links: list[str] = []
        if html:
            title, new_links = extract_links(
                url, html, allowed_domains=self.cfg.allowed_domains
            )

        # Save page
        await self.storage.save_page(
            url=url,
            title=title,
            html=html or "",
            links=new_links,
            domain=domain,
            timestamp=ts,
            status=status,
            content_type=ctype,
        )

        # Mark visited
        await self.dupe.mark_visited(url, ts)

        # Enqueue new links
        if new_links:
            # Filter out visited in batch
            flags = await self.dupe.has_many(new_links)
            to_add = [u for u, seen in zip(new_links, flags) if not seen]
            if to_add:
                await self.frontier.push_many(to_add)

        return True

    async def run(self, stop_event: asyncio.Event) -> None:
        timeout = aiohttp.ClientTimeout(total=None)
        conn = aiohttp.TCPConnector(limit=self.cfg.concurrency)
        async with aiohttp.ClientSession(timeout=timeout, connector=conn) as session:
            while True:
                if stop_event.is_set():
                    break
                worked = await self.process_one(session)
                if not worked:
                    await asyncio.sleep(0.1)
