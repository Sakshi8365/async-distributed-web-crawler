from __future__ import annotations

import time
from typing import Tuple

from redis.asyncio import Redis

RL_HASH = "rate:domains"

CHECK_AND_RESERVE_LUA = """
-- KEYS[1] = hash key
-- ARGV[1] = domain
-- ARGV[2] = now
-- ARGV[3] = cooldown seconds
local key = KEYS[1]
local domain = ARGV[1]
local now = tonumber(ARGV[2])
local cooldown = tonumber(ARGV[3])
local next_ts = redis.call('HGET', key, domain)
if not next_ts then
  redis.call('HSET', key, domain, now + cooldown)
  return {now, 1}
end
next_ts = tonumber(next_ts)
if next_ts <= now then
  redis.call('HSET', key, domain, now + cooldown)
  return {now, 1}
else
  return {next_ts, 0}
end
"""


class RateLimiter:
    def __init__(self, redis: Redis):
        self.redis = redis
        self._script = redis.register_script(CHECK_AND_RESERVE_LUA)

    async def check_and_reserve(
        self, domain: str, cooldown_seconds: float
    ) -> Tuple[float, bool]:
        now = time.time()
        allowed_at, reserved = await self._script(
            keys=[RL_HASH], args=[domain, now, cooldown_seconds]
        )
        if isinstance(allowed_at, (bytes, bytearray)):
            allowed_at = float(allowed_at.decode())
        else:
            allowed_at = float(allowed_at)
        return allowed_at, bool(int(reserved))
