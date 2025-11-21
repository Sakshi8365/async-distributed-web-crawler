from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Set

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    redis_url: str
    mongo_url: str
    mongo_db: str
    concurrency: int
    domain_cooldown_seconds: float
    request_timeout_seconds: int
    max_content_size_bytes: int
    user_agent: str
    seed_urls: tuple[str, ...]
    allowed_domains: Optional[Set[str]]
    max_pages: Optional[int]


def _parse_csv(env_value: Optional[str]) -> tuple[str, ...]:
    if not env_value:
        return tuple()
    return tuple(u.strip() for u in env_value.split(",") if u.strip())


def _parse_domains(env_value: Optional[str]) -> Optional[Set[str]]:
    if not env_value:
        return None
    return {d.strip().lower() for d in env_value.split(",") if d.strip()}


def load_config() -> Config:
    # Load from .env if present
    load_dotenv(override=False)

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    mongo_url = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    mongo_db = os.getenv("MONGO_DB", "crawler")
    _concurrency_raw = os.getenv("CONCURRENCY")
    concurrency = int(_concurrency_raw) if _concurrency_raw is not None else 200
    domain_cooldown_seconds = float(os.getenv("DOMAIN_COOLDOWN_SECONDS", "1.0"))
    _rto_raw = os.getenv("REQUEST_TIMEOUT_SECONDS")
    request_timeout_seconds = int(_rto_raw) if _rto_raw is not None else 15
    _mcs_raw = os.getenv("MAX_CONTENT_SIZE_BYTES")
    max_content_size_bytes = int(_mcs_raw) if _mcs_raw is not None else 3 * 1024 * 1024
    user_agent = os.getenv("USER_AGENT", "DistributedCrawler/1.0")
    seed_urls = _parse_csv(os.getenv("SEED_URLS"))
    allowed_domains = _parse_domains(os.getenv("ALLOWED_DOMAINS"))
    _max_pages_raw = os.getenv("MAX_PAGES")
    max_pages = int(_max_pages_raw) if _max_pages_raw is not None else None

    return Config(
        redis_url=redis_url,
        mongo_url=mongo_url,
        mongo_db=mongo_db,
        concurrency=concurrency,
        domain_cooldown_seconds=domain_cooldown_seconds,
        request_timeout_seconds=request_timeout_seconds,
        max_content_size_bytes=max_content_size_bytes,
        user_agent=user_agent,
        seed_urls=seed_urls,
        allowed_domains=allowed_domains,
        max_pages=max_pages,
    )
