import asyncio
from redis.asyncio import Redis
from crawler.config import load_config
from crawler.storage import Storage
from crawler.dupe import VISITED_SET
from crawler.frontier import FRONTIER_ZSET


async def main() -> None:
    cfg = load_config()
    redis = Redis.from_url(cfg.redis_url, decode_responses=False)
    storage = Storage(cfg.mongo_url, cfg.mongo_db)
    await storage.init()
    frontier_sz = await redis.zcard(FRONTIER_ZSET)
    visited = await redis.scard(VISITED_SET)
    pages = await storage.count_pages()
    print({"frontier": frontier_sz, "visited": visited, "pages": pages})


if __name__ == "__main__":
    asyncio.run(main())
