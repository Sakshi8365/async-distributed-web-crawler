from __future__ import annotations

from typing import Any, Dict, Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection


class Storage:
    def __init__(self, mongo_url: str, db_name: str) -> None:
        self._client: AsyncIOMotorClient = AsyncIOMotorClient(mongo_url)
        self._db = self._client[db_name]
        self._pages: AsyncIOMotorCollection = self._db["pages"]

    async def init(self) -> None:
        # Ensure index on URL for uniqueness and fast lookups
        await self._pages.create_index("url", unique=True)
        await self._pages.create_index("domain")
        await self._pages.create_index("timestamp")

    async def save_page(
        self,
        url: str,
        title: str,
        html: str,
        links: list[str],
        domain: str,
        timestamp: float,
        status: int,
        content_type: str | None,
    ) -> None:
        doc: Dict[str, Any] = {
            "url": url,
            "title": title,
            "html": html,
            "links": links,
            "domain": domain,
            "timestamp": timestamp,
            "status": status,
            "content_type": content_type,
        }
        await self._pages.update_one({"url": url}, {"$set": doc}, upsert=True)

    async def get_page(self, url: str) -> Optional[dict]:
        return await self._pages.find_one({"url": url}, {"_id": 0})

    async def count_pages(self) -> int:
        return await self._pages.estimated_document_count()

    async def close(self) -> None:
        self._client.close()
