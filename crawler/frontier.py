from __future__ import annotations

import time
from typing import Optional

from redis.asyncio import Redis


FRONTIER_ZSET = "frontier:zset"


POP_READY_LUA = """
-- Pops up to ARGV[1] urls with score <= ARGV[2] (now)
-- Returns array of urls
local key = KEYS[1]
local max_count = tonumber(ARGV[1])
local now = tonumber(ARGV[2])
local results = {}
local popped = 0
while popped < max_count do
  local items = redis.call('ZRANGEBYSCORE', key, '-inf', now, 'LIMIT', 0, 1)
  if #items == 0 then
    break
  end
  local member = items[1]
  local removed = redis.call('ZREM', key, member)
  if removed == 1 then
    table.insert(results, member)
    popped = popped + 1
  else
    -- Concurrently removed, try again
  end
end
return results
"""


class Frontier:
    def __init__(self, redis: Redis):
        self.redis = redis
        self._pop_ready = self.redis.register_script(POP_READY_LUA)

    async def push(self, url: str, scheduled_at: Optional[float] = None) -> None:
        score = float(scheduled_at) if scheduled_at is not None else time.time()
        await self.redis.zadd(FRONTIER_ZSET, {url: score})

    async def push_many(self, urls: list[str], scheduled_at: Optional[float] = None) -> None:
        if not urls:
            return
        score = float(scheduled_at) if scheduled_at is not None else time.time()
        mapping = {u: score for u in urls}
        await self.redis.zadd(FRONTIER_ZSET, mapping)

    async def pop_ready(self, max_count: int = 1) -> list[str]:
        now = time.time()
        return [u.decode() if isinstance(u, (bytes, bytearray)) else u for u in await self._pop_ready(keys=[FRONTIER_ZSET], args=[max_count, now])]

    async def size(self) -> int:
        return int(await self.redis.zcard(FRONTIER_ZSET))

    async def clear(self) -> None:
        await self.redis.delete(FRONTIER_ZSET)