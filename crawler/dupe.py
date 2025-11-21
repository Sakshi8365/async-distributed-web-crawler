from __future__ import annotations

import time
from typing import Iterable

from redis.asyncio import Redis

VISITED_SET = "visited:set"
VISITED_TS = "visited:ts"


class Dedupe:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def is_visited(self, url: str) -> bool:
        res = await self.redis.sismember(VISITED_SET, url)
        return bool(res)

    async def mark_visited(self, url: str, ts: float | None = None) -> None:
        ts = ts or time.time()
        pipe = self.redis.pipeline()
        pipe.sadd(VISITED_SET, url)
        pipe.hset(VISITED_TS, url, str(ts))
        await pipe.execute()

    async def has_many(self, urls: Iterable[str]) -> list[bool]:
        # Efficient membership check using SMISMEMBER (Redis 6.2+)
        url_list = list(urls)
        if not url_list:
            return []
        # redis-py exposes 'smismember' on asyncio client
        res = await self.redis.smismember(VISITED_SET, url_list)
        return [bool(x) for x in res]

    async def count(self) -> int:
        return int(await self.redis.scard(VISITED_SET))
