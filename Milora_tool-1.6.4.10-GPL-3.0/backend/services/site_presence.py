"""Bounded, process-local estimates of active browsers; no account or DB state."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import threading
import time
from typing import Callable

from fastapi import FastAPI, HTTPException, Request


HEARTBEAT_PATH = "/api/site-presence/heartbeat"
SNAPSHOT_PATH = "/api/site-presence"
VISITOR_ID = re.compile(r"[0-9a-f]{32}", re.ASCII)


class PresenceLimitError(RuntimeError):
    pass


class PresenceCapacityError(RuntimeError):
    pass


class SitePresenceStore:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic,
                 ttl_seconds: int = 90, max_browsers: int = 10000,
                 max_sources: int = 4096, requests_per_minute: int = 600):
        self._clock = clock
        self.ttl_seconds = ttl_seconds
        self._max_browsers = max_browsers
        self._max_sources = max_sources
        self._request_limit = requests_per_minute
        self._salt = secrets.token_bytes(32)
        self._lock = threading.Lock()
        self._visitors: dict[bytes, float] = {}
        self._sources: dict[bytes, tuple[float, int]] = {}

    def _key(self, value: str) -> bytes:
        return hashlib.blake2s(value.encode("utf-8"), key=self._salt).digest()

    def _prune(self, stamp: float) -> None:
        self._visitors = {key: seen for key, seen in self._visitors.items()
                          if stamp - seen < self.ttl_seconds}
        self._sources = {key: state for key, state in self._sources.items()
                         if stamp - state[0] < 60}

    def _allow(self, source: str, stamp: float) -> None:
        key = self._key(source)
        start, count = self._sources.get(key, (stamp, 0))
        if key not in self._sources and len(self._sources) >= self._max_sources:
            raise PresenceLimitError("Presence request capacity reached")
        if count >= self._request_limit:
            raise PresenceLimitError("Presence request rate exceeded")
        self._sources[key] = (start, count + 1)

    def _payload(self) -> dict:
        return {"ok": True, "count": len(self._visitors),
                "heartbeat_seconds": 30, "expires_after_seconds": self.ttl_seconds}

    def heartbeat(self, visitor_id: str, source: str) -> dict:
        if not isinstance(visitor_id, str) or not VISITOR_ID.fullmatch(visitor_id):
            raise ValueError("Invalid visitor identifier")
        with self._lock:
            stamp = self._clock()
            self._prune(stamp)
            self._allow(source, stamp)
            key = self._key(visitor_id)
            if key not in self._visitors and len(self._visitors) >= self._max_browsers:
                raise PresenceCapacityError("Presence visitor capacity reached")
            self._visitors[key] = stamp
            return self._payload()

    def snapshot(self, source: str) -> dict:
        with self._lock:
            stamp = self._clock()
            self._prune(stamp)
            self._allow(source, stamp)
            return self._payload()


def register_site_presence(app: FastAPI, trusted_origins: list[str],
                           get_client_ip: Callable[[Request], str], *,
                           store: SitePresenceStore | None = None) -> SitePresenceStore:
    presence = store if store is not None else SitePresenceStore()
    origins = {origin.rstrip("/") for origin in trusted_origins}

    def read_count(request: Request, visitor_id: str | None = None) -> dict:
        try:
            source = get_client_ip(request)
            return presence.snapshot(source) if visitor_id is None else presence.heartbeat(visitor_id, source)
        except ValueError:
            raise HTTPException(status_code=422, detail="瀏覽人數識別格式無效。") from None
        except PresenceLimitError:
            raise HTTPException(status_code=429, detail="瀏覽人數請求過於頻繁，請稍後再試。") from None
        except PresenceCapacityError:
            raise HTTPException(status_code=503, detail="瀏覽人數暫時無法取得。") from None

    @app.get(SNAPSHOT_PATH, include_in_schema=False)
    def site_presence_snapshot(request: Request):
        return read_count(request)

    @app.post(HEARTBEAT_PATH, include_in_schema=False)
    async def site_presence_heartbeat(request: Request):
        origin = request.headers.get("origin", "").rstrip("/")
        if origin not in origins or request.headers.get("sec-fetch-site") == "cross-site":
            raise HTTPException(status_code=403, detail="來源驗證失敗。")
        if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
            raise HTTPException(status_code=415, detail="瀏覽人數請求格式無效。")
        data = bytearray()
        async for chunk in request.stream():
            if len(data) + len(chunk) > 256:
                raise HTTPException(status_code=413, detail="瀏覽人數請求過大。")
            data.extend(chunk)
        try:
            payload = json.loads(data)
        except (ValueError, UnicodeError):
            raise HTTPException(status_code=422, detail="瀏覽人數請求格式無效。") from None
        if not isinstance(payload, dict) or set(payload) != {"visitor_id"}:
            raise HTTPException(status_code=422, detail="瀏覽人數請求格式無效。")
        visitor_id = payload["visitor_id"]
        if not isinstance(visitor_id, str) or not VISITOR_ID.fullmatch(visitor_id):
            raise HTTPException(status_code=422, detail="瀏覽人數識別格式無效。")
        return read_count(request, visitor_id)

    return presence
