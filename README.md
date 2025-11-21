# Distributed Web Crawler (Async, Redis, Mongo)

![Build](https://img.shields.io/badge/build-pending-lightgrey) ![Python](https://img.shields.io/badge/python-3.12-blue) ![License](https://img.shields.io/badge/license-MIT-green)

A scalable async web crawler demonstrating distributed-style scheduling via Redis + Lua scripts and durable page/link storage in MongoDB. Suitable as a portfolio project: shows concurrency (asyncio + aiohttp), data structures (ZSET frontier, SET dedupe), politeness (rate limiting & robots.txt), and analytics (status codes, domain stats, link graph export).

## Architecture

```
                   +----------------+
                   | Seed URLs      |
                   +-------+--------+
                           |
                           v
                   +-------+--------+
                   | URL Frontier   |  (Redis ZSET)
                   +-------+--------+
                           |
                   +-------+--------+
                   | Deduplication  |
                   | (Redis Set)    |
                   +-------+--------+
                           |
             +-------------+-------------+
             |                           |
             v                           v
     +-------+-------+          +--------+-------+
     | Worker Node 1 |   ...    | Worker Node N  |
     +-------+-------+          +--------+-------+
             |                           |
      +------+-----------+       +--------+------+
      | Politeness Check |       | Robots.txt    |
      | (Rate Limiter)  |       | Cache/Parser  |
      +------+-----------+       +---------------+
             |
             v
     +-------+-------+
     | HTML Fetcher  |
     +-------+-------+
             |
             v
     +-------+--------+
     | HTML Parser    |
     +-------+--------+
             |
      +------+----------+              +-----------------+
      | Extracted Links |   ----->     | Storage (Mongo) |
      +------+----------+              +-----------------+
             |                          | HTML content   |
             v                          | Metadata       |
     +-------+--------+                 | Outgoing links |
     | URL Frontier   |                 +-----------------+
     | (new URLs)     |
     +----------------+
```

## Features

- Politeness: per-domain cooldown via Redis + Lua.
- Concurrency: asyncio + aiohttp; configurable worker count.
- Fault-tolerance: frontier/dedupe in Redis; pages in Mongo.
- Robots.txt: fetched and cached in Redis; enforced before fetch.
- HTML parsing: BeautifulSoup; link normalization and filtering.
- Retries: transient fetch failures retried with exponential backoff.
- Metrics: pages crawled, pages/sec, status code distribution, robots blocks.
- Domain analytics: `domain-stats` command for top domains frontier/visited/stored.
- Graph export: CSV edge list for post-processing (NetworkX, etc.).

## Data Models

Page document (Mongo):

```json
{
  "url": "https://example.com",
  "title": "Example",
  "html": "<html>...</html>",
  "links": ["https://example.com/about"],
  "domain": "example.com",
  "timestamp": 17372993,
  "status": 200,
  "content_type": "text/html"
}
```

Frontier entry: Redis ZSET member=`url`, score=`scheduled_at`.

## Quick Start (Local)

1. Create a virtual environment and install deps:

```powershell
python -m venv .venv
. .venv/Scripts/Activate.ps1
python -m pip install -r requirements.txt
```

2. Run Redis and Mongo (easiest via Docker):

```powershell
docker compose up -d redis mongo
```

3. Create a `.env` (optional; defaults are fine):

```powershell
Copy-Item .env.example .env
```

4. Seed and run:

```powershell
python -m crawler.main seed https://example.com https://www.python.org
python -m crawler.main run --concurrency 100
```

5. Show stats:

```powershell
python scripts/show_stats.py
python -m crawler.main domain-stats --limit 10
```

## Docker Compose

Build and run all services (Redis + Mongo + crawler workers):

```powershell
docker compose up --build
```

Scale workers:

```powershell
docker compose up --scale crawler=4 -d
```

## Configuration (.env)

- `REDIS_URL`, `MONGO_URL`, `MONGO_DB`
- `CONCURRENCY`, `DOMAIN_COOLDOWN_SECONDS`, `REQUEST_TIMEOUT_SECONDS`, `MAX_CONTENT_SIZE_BYTES`
- `USER_AGENT`, `SEED_URLS`, `ALLOWED_DOMAINS`, `MAX_PAGES`

## Tests

Run unit tests (parser sample):

```powershell
pytest -q
```

## Notes / Extensions

- Add priority scheduling by using ZSET scores per priority.
- Add Bloom filter to reduce Redis memory for dedupe.
- Add monitoring (e.g., Prometheus) and a small dashboard.
- Add sitemap parsing and recrawl policies.

## Status Snapshot & Dashboard

To capture a point-in-time view of the crawl (frontier size, visited counts, stored pages, and metrics) and generate a lightweight HTML dashboard:

```powershell
python -m crawler.main dump-status
```

Artifacts written to the `output/` directory:

- `output/status.json` – counts: frontier size, visited set size, pages stored, timestamp.
- `output/metrics.json` – crawl performance metrics (pages/sec, total pages, duration, HTTP status grouping).
- `output/graph.csv` – edge list (from_url,to_url) built during the run command.
- `output/dashboard.html` – simple static HTML summary you can open in a browser.

### One-Command Helper (Windows PowerShell)

Use the helper script to (optionally) run a short crawl, dump status, and auto-open the dashboard:

```powershell
./scripts/view_status.ps1                   # dump & open existing snapshot
./scripts/view_status.ps1 -RunCrawl         # run a short crawl (default ~50 pages) then snapshot
./scripts/view_status.ps1 -RunCrawl -Pages 200 -Concurrency 40
./scripts/view_status.ps1 -SkipOpen         # generate snapshot only
```

Parameters:

- `-RunCrawl` – perform a crawl before dumping status.
- `-Pages <int>` – approximate max pages for that crawl (default 50).
- `-Concurrency <int>` – worker count (default 10).
- `-SkipOpen` – do not auto-launch `dashboard.html`.

If a virtual environment exists at `.venv/`, the script will use it; otherwise it falls back to the global `python`.

### Manual Workflow Recap

1. (Optional) Seed: `python -m crawler.main seed <urls...>`
2. Run crawl: `python -m crawler.main run --concurrency 100 --max-pages 1000`
3. Dump snapshot: `python -m crawler.main dump-status`
4. Open `output/dashboard.html` in a browser.

This snapshot approach replaces an earlier experimental live HTTP server and avoids runtime connectivity issues.

## Domain Stats Command

Inspect top domains across three dimensions (frontier = queued, visited = processed, stored = persisted HTML):

```powershell
python -m crawler.main domain-stats --limit 15           # table output
python -m crawler.main domain-stats --limit 30 --json    # JSON output
```

## Metrics JSON Example

Excerpt of `output/metrics.json` after a run:

```json
{
  "pages_crawled": 1000,
  "duration_seconds": 54.2,
  "pages_per_second": 18.45,
  "status_counts": { "200": 880, "404": 55, "301": 40, "0": 25 },
  "robots_blocked": 12
}
```

`0` status indicates fetch failures after all retries.

## Packaging & Docker

Install locally (editable):

```powershell
pip install -e .
crawler-cli stats
```

Build and run with Docker:

```powershell
docker build -t distributed-crawler .
docker run --rm -e REDIS_URL=redis://host.docker.internal:6379/0 -e MONGO_URL=mongodb://host.docker.internal:27017 distributed-crawler run --concurrency 50 --max-pages 500
```

Compose (Redis + Mongo + crawler):

```powershell
docker compose up --build
```

## Roadmap (Potential Enhancements)

- Advanced priority scheduling & per-domain quotas.
- Structured logging + Prometheus exporter.
- Content compression (gzip) and text extraction.
- Incremental re-crawl & freshness scoring.
- Bloom filter dedupe memory optimization.
- Robust robots.txt wildcard & crawl-delay handling.
- API/Live dashboard with domain metrics trend.

## License

MIT License © 2025 Sakshi8365. See `LICENSE` for full text.

---

> Badges will show actual status after you push to GitHub and CI runs.
