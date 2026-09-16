"""Общий httpx-клиент: один пул соединений на весь процесс + ретраи."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None
_lock = asyncio.Lock()


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        async with _lock:
            if _client is None or _client.is_closed:
                s = get_settings()
                _client = httpx.AsyncClient(
                    timeout=httpx.Timeout(s.http_timeout),
                    headers={
                        "User-Agent": s.user_agent,
                        "Accept-Encoding": "gzip",
                    },
                    follow_redirects=True,
                    limits=httpx.Limits(max_connections=32, max_keepalive_connections=16),
                )
    return _client


async def close_client() -> None:
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
    _client = None


async def get_json(
    url: str,
    params: dict[str, Any] | None = None,
    *,
    headers: dict[str, str] | None = None,
    retries: int = 2,
) -> dict[str, Any]:
    """GET c JSON-ответом. Ретраим только сетевые сбои и 429/5xx."""
    client = await get_client()
    delay = 0.4
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = await client.get(url, params=params, headers=headers)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                await asyncio.sleep(delay)
                delay *= 2
                continue
            r.raise_for_status()
            return r.json()
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            last_exc = exc
            if attempt >= retries:
                break
            await asyncio.sleep(delay)
            delay *= 2
    assert last_exc is not None
    log.warning("GET %s failed: %s", url, last_exc)
    raise last_exc
