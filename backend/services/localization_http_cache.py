"""Reuse verified HTTP cache bodies only for immutable localization source URLs."""
from __future__ import annotations

import re
import tempfile
from pathlib import Path

MAX_BYTES = 96 * 1024 * 1024
IMMUTABLE_URL = re.compile(
    r'https://raw\.githubusercontent\.com/(?:Arikatsu/WutheringWaves_Data|Waifus-Grace/NTE_Assets)/'
    r'[0-9a-f]{40}/[^?#]+\.json'
)


def request_localization_json(url: str, *, timeout: int, cache_dir: Path | None = None):
    from backend.services.game_data_sources import _read_source_http_cache, _request_bytes, _decode_json
    if cache_dir is not None:
        if IMMUTABLE_URL.fullmatch(url):
            cached = _read_source_http_cache(Path(cache_dir), url, MAX_BYTES)
            if cached is not None:
                return _decode_json(cached[0], url=url)
        # Branch/API requests must still revalidate; never directly reuse a
        # cached mutable ref. The existing downloader enforces the deadline.
        raw, _ = _request_bytes(url, timeout=timeout, attempts=1,
                                max_bytes=MAX_BYTES, cache_dir=Path(cache_dir))
    else:
        with tempfile.TemporaryDirectory(prefix='milora-language-fetch-') as folder:
            raw, _ = _request_bytes(url, timeout=timeout, attempts=1,
                                    max_bytes=MAX_BYTES, cache_dir=Path(folder))
    return _decode_json(raw, url=url)
