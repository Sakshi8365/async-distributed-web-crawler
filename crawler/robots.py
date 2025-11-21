from __future__ import annotations

import asyncio
import time
from typing import Optional
from urllib.parse import urlparse, urlunparse

import aiohttp
from redis.asyncio import Redis
from urllib import robotparser


ROBOTS_CACHE_KEY = "robots:cache"  # HSET domain -> serialized rules
ROBOTS_TS_KEY = "robots:ts"        # HSET domain -> fetched_at
DEFAULT_TTL_SECONDS = 24 * 3600


def _robots_url_for(url: str) -> str:
    p = urlparse(url)
    base = (p.scheme, p.netloc, "/robots.txt", "", "", "")
    return urlunparse(base)


class Robots:
    def __init__(self, redis: Redis, user_agent: str, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.redis = redis
        self.user_agent = user_agent
        self.ttl = ttl_seconds

    async def _fetch_robots(self, session: aiohttp.ClientSession, robots_url: str) -> str:
        try:
            async with session.get(robots_url, timeout=10) as resp:
                if resp.status >= 400:
                    return ""  # treat as empty robots (allow all)
                text = await resp.text(errors="ignore")
                return text
        except Exception:
            return ""

    async def _load_or_update(self, session: aiohttp.ClientSession, domain: str, robots_url: str) -> str:
        now = time.time()
        ts_raw = await self.redis.hget(ROBOTS_TS_KEY, domain)
        if ts_raw is not None:
            try:
                ts = float(ts_raw)
            except Exception:
                ts = 0.0
        else:
            ts = 0.0
        if now - ts < self.ttl:
            cached = await self.redis.hget(ROBOTS_CACHE_KEY, domain)
            return cached.decode() if isinstance(cached, (bytes, bytearray)) else (cached or "")

        text = await self._fetch_robots(session, robots_url)
        pipe = self.redis.pipeline()
        pipe.hset(ROBOTS_CACHE_KEY, domain, text)
        pipe.hset(ROBOTS_TS_KEY, domain, now)
        await pipe.execute()
        return text

    async def is_allowed(self, session: aiohttp.ClientSession, url: str) -> bool:
        p = urlparse(url)
        domain = p.hostname or ""
        robots_url = _robots_url_for(url)
        text = await self._load_or_update(session, domain, robots_url)

        rp = robotparser.RobotFileParser()
        rp.parse(text.splitlines())
        return rp.can_fetch(self.user_agent, url)
