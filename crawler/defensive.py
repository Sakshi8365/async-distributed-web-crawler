from __future__ import annotations

from typing import Iterable


def chunked(seq: Iterable[str], size: int) -> list[list[str]]:
    batch: list[str] = []
    out: list[list[str]] = []
    for item in seq:
        batch.append(item)
        if len(batch) >= size:
            out.append(batch)
            batch = []
    if batch:
        out.append(batch)
    return out
