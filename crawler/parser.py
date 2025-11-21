from __future__ import annotations

from typing import Iterable, Optional, Set, Tuple
from urllib.parse import urljoin, urldefrag, urlparse, urlunparse

from bs4 import BeautifulSoup


ALLOWED_SCHEMES = {"http", "https"}
BLOCKED_PREFIXES = ("mailto:", "javascript:", "data:")
BLOCKED_EXTS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".pdf",
    ".zip",
    ".gz",
    ".tar",
    ".mp4",
    ".mp3",
}


def normalize_url(base_url: str, href: str) -> Optional[str]:
    href = href.strip()
    if not href or href.startswith(BLOCKED_PREFIXES):
        return None
    # Make absolute
    abs_url = urljoin(base_url, href)
    # Remove fragment
    abs_url, _frag = urldefrag(abs_url)
    p = urlparse(abs_url)
    if p.scheme not in ALLOWED_SCHEMES:
        return None
    # Normalize netloc to lowercase and strip default ports
    netloc = p.netloc.lower()
    if netloc.endswith(":80") and p.scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and p.scheme == "https":
        netloc = netloc[:-4]
    # Drop useless path trailing slash normalization
    path = p.path or "/"
    # Rebuild URL
    norm = urlunparse((p.scheme, netloc, path, "", p.query, ""))
    # Filter obvious binary resources by extension
    lower_path = path.lower()
    for ext in BLOCKED_EXTS:
        if lower_path.endswith(ext):
            return None
    return norm


def extract_links(base_url: str, html: str, allowed_domains: Optional[Set[str]] = None) -> Tuple[str, list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    # Title
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Links
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        norm = normalize_url(base_url, a["href"]) 
        if not norm:
            continue
        if allowed_domains:
            host = urlparse(norm).hostname or ""
            if host.startswith("www."):
                host = host[4:]
            if host not in allowed_domains:
                continue
        out.append(norm)

    # Dedupe while preserving order
    seen = set()
    deduped: list[str] = []
    for u in out:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return title, deduped