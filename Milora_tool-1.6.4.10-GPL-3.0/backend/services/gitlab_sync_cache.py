"""Request-scoped, verified transport for Genshin/HSR only.

Mutable refs/files are revalidated for every preview. Only exact commit URLs may
reuse verified bytes without an HTTP revalidation. No application/DB imports.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import tempfile
import threading
import time
import urllib.parse
from email.utils import parsedate_to_datetime
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path


PROJECTS = {"genshin": "Dimbreath/animegamedata2", "hsr": "Dimbreath/turnbasedgamedata"}
_current: ContextVar[GitlabSyncCache | None] = ContextVar("gitlab_sync_cache", default=None)
_network_guard = threading.RLock()
_limited_until: dict[str, float] = {}
_last_request: dict[str, float] = {}


class GitlabSyncCache:
    def __init__(self, game_id: str, folder: Path):
        self.project = PROJECTS[game_id]
        self.folder = Path(folder)
        self._refs: dict[str, tuple[bytes, dict]] = {}
        self._failed_refs: dict[str, Exception] = {}
        self._responses: dict[str, tuple[bytes, dict]] = {}
        self._locks: dict[str, threading.RLock] = {}
        self._limited_error = None
        self._guard = threading.RLock()
        self.shared_folder = self.folder.parent.parent if self.folder.name == "gitlab-http-cache" else self.folder
        self.bucket = str(self.shared_folder.resolve())
        self.stats = {"requests": 0, "immutable_hits": 0, "revalidated": 0, "conditional_reuses": 0, "request_hits": 0}

    def _rate_error(self, seconds):
        from backend.services import game_data_sources as source
        return source.RepositorySourceError(
            f"GitLab 限制請求（HTTP 429），約 {seconds} 秒後才能重試。本次已停止抓取，不覆蓋既有預覽。",
            code="upstream_http_429", diagnostics={"http_status": 429, "retry_after_seconds": seconds})

    def raise_if_limited(self):
        if self._limited_error is not None:
            raise self._limited_error
        with _network_guard:
            until = _limited_until.get(self.bucket, 0)
            try:
                state = json.loads((self.shared_folder / "gitlab-rate-limit.json").read_text(encoding="utf-8"))
                stamp = float(state["retry_at"])
                if state.get("schema") == 1 and math.isfinite(stamp):
                    until = max(until, stamp)
            except (OSError, ValueError, TypeError, KeyError):
                pass
            if until > time.time():
                self._limited_error = self._rate_error(max(1, math.ceil(until - time.time())))
                raise self._limited_error

    def _record_limit(self, error):
        header = str(error.diagnostics.get("retry_after") or "")
        try:
            seconds = int(header) if re.fullmatch(r"\d{1,8}", header) else math.ceil(parsedate_to_datetime(header).timestamp() - time.time())
        except (ValueError, TypeError, OverflowError):
            seconds = 60
        seconds = max(1, seconds)
        until = time.time() + seconds
        _limited_until[self.bucket] = max(_limited_until.get(self.bucket, 0), until)
        self._limited_error = self._rate_error(seconds)
        temporary = None
        try:
            self.shared_folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.shared_folder, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump({"schema": 1, "retry_at": _limited_until[self.bucket]}, stream)
            temporary.replace(self.shared_folder / "gitlab-rate-limit.json")
        except OSError:
            pass
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    pass

    def _download(self, url, *, timeout, max_bytes, attempts, conditional=None):
        from backend.services import game_data_sources as source
        # Cached transport has a wall-clock read loop as well as a socket limit.
        # Large raw files may need 120s on a cold cache; metadata uses 20s.
        budget = max(timeout, 120) if "/-/raw/" in url else timeout
        # Serialize this GitLab transport only, across both games. No queued
        # speculative history and no burst from localization worker pools.
        with _network_guard:
            self.raise_if_limited()
            gap = 0.2 - (time.monotonic() - _last_request.get(self.bucket, 0))
            if gap > 0:
                time.sleep(gap)
            with self._guard:
                self.stats["requests"] += 1
            try:
                options = {"conditional_cache": conditional} if conditional is not None else {}
                raw, manifest = source._request_bytes(url, timeout=budget, max_bytes=max_bytes,
                    attempts=attempts, cache_dir=self.folder, stale_on_timeout=False, **options)
            except source.RepositorySourceError as error:
                if error.code == "upstream_http_429":
                    self._record_limit(error)
                    raise self._limited_error from error
                raise
            finally:
                _last_request[self.bucket] = time.monotonic()
        if manifest.get("cache_revalidated"):
            with self._guard:
                self.stats["revalidated"] += 1
        if manifest.get("conditional_reuse"):
            with self._guard:
                self.stats["conditional_reuses"] += 1
        return raw, manifest

    def _conditional_body(self, url, raw_prefix, max_bytes):
        """Propose a same-preview branch body; target URL must still confirm 304."""
        commit, _, relative = url[len(raw_prefix):].partition("/")
        api_prefix = "https://gitlab.com/api/v4/projects/" + urllib.parse.quote(self.project, safe="") + "/repository/commits/"
        with self._guard:
            for old_url, (raw, manifest) in self._responses.items():
                if not old_url.startswith(raw_prefix):
                    continue
                ref, _, old_path = old_url[len(raw_prefix):].partition("/")
                resolved = self._refs.get(api_prefix + ref)
                if old_path != relative or resolved is None or len(raw) > max_bytes:
                    continue
                if json.loads(resolved[0]).get("id", "").lower() != commit:
                    continue
                etag = str(manifest.get("etag") or "")
                if etag and manifest.get("sha256") == hashlib.sha256(raw).hexdigest():
                    return raw, {**manifest, "url": url, "requested_url": url}
        return None

    def _resolve(self, url, *, timeout):
        from backend.services import game_data_sources as source
        # request() owns the per-URL lock. Never hold the response lock while
        # waiting for the shared network gate (the inverse order would deadlock).
        with self._guard:
            if url in self._failed_refs:
                raise self._failed_refs[url]
            if url in self._refs:
                return self._refs[url]
        try:
            raw, manifest = self._download(url, timeout=min(timeout, 20),
                max_bytes=4 * 1024 * 1024, attempts=1)
            value = source._decode_json(raw, url=url)
            commit = str(value.get("id") or "").lower() if isinstance(value, dict) else ""
            if not re.fullmatch(r"[0-9a-f]{40}", commit):
                raise source.RepositorySourceError("來源提交無法確認。", code="repository_commit_unavailable")
            with self._guard:
                self._refs[url] = (raw, manifest)
            return raw, manifest
        except source.RepositorySourceError as error:
            with self._guard:
                self._failed_refs[url] = error
            raise

    def request(self, url, *, timeout=30, max_bytes=64 * 1024 * 1024, attempts=1):
        with self._guard:
            lock = self._locks.setdefault(url, threading.RLock())
        with lock:
            with self._guard:
                saved = self._responses.get(url)
                if saved is not None and len(saved[0]) <= max_bytes:
                    self.stats["request_hits"] += 1
                    return saved
            result = self._request(url, timeout=timeout, max_bytes=max_bytes, attempts=attempts)
            with self._guard:
                self._responses[url] = result
            return result

    def _request(self, url, *, timeout, max_bytes, attempts):
        from backend.services import game_data_sources as source
        original = url
        conditional = None
        raw_prefix = "https://gitlab.com/" + self.project + "/-/raw/"
        api_prefix = "https://gitlab.com/api/v4/projects/" + urllib.parse.quote(self.project, safe="") + "/repository/commits/"
        if url.startswith(api_prefix) and not urllib.parse.urlsplit(url).query:
            return self._resolve(url, timeout=timeout)
        if url.startswith(raw_prefix):
            # Keep the original branch download contract. Resolving the commit
            # API is optional localization work, not a new primary-source gate.
            # Mutable raw URLs always go through HTTP conditional revalidation.
            immutable = bool(re.fullmatch(re.escape(raw_prefix) + r"[0-9a-f]{40}/[^?#]+\.json", url))
            if immutable:
                saved = source._read_source_http_cache(self.folder, url, max_bytes)
                if saved is not None:
                    with self._guard:
                        self.stats["immutable_hits"] += 1
                    return saved[0], {**saved[1], "elapsed_ms": 0, "immutable_cache_hit": True,
                                      "original_requested_url": original}
                conditional = self._conditional_body(url, raw_prefix, max_bytes)
        else:
            # Never silently extend this transport to another game/host.
            parsed = urllib.parse.urlsplit(url)
            allowed_api = "https://gitlab.com/api/v4/projects/" + urllib.parse.quote(self.project, safe="") + "/"
            if not url.startswith(allowed_api) or parsed.scheme != "https":
                raise source.RepositorySourceError("來源不屬於此遊戲的已授權 GitLab 倉庫。", code="source_url_not_allowed")
        raw, manifest = self._download(url, timeout=timeout, max_bytes=max_bytes, attempts=attempts, conditional=conditional)
        return raw, {**manifest, "original_requested_url": original}


def current_cache():
    return _current.get()


def ordered_history(releases, fetch):
    """Strictly lazy: closing/breaking the iterator starts no extra downloads."""
    for release in releases:
        try:
            yield release, fetch(release), None
        except Exception as error:
            yield release, None, error


@contextmanager
def cache_scope(game_id, folder):
    client = GitlabSyncCache(game_id, folder)
    token = _current.set(client)
    try:
        yield client
    finally:
        _current.reset(token)


def request_bytes(url, *, timeout=30, max_bytes=64 * 1024 * 1024, attempts=2, client=None):
    from backend.services import game_data_sources as source
    active = client if client is not None else current_cache()
    if active is None:
        # Preserve existing standalone/parser fixture behavior outside these previews.
        return source._request_bytes(url, timeout=timeout, max_bytes=max_bytes, attempts=attempts)
    return active.request(url, timeout=timeout, max_bytes=max_bytes, attempts=1)
