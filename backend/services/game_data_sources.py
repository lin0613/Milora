from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from backend.services.source_pipeline import PIPELINE_VERSION, adapter_id as source_adapter_id

SOURCE_ARCHITECTURE_VERSION = "source-architecture-primary-repository-history-v18"
DEFAULT_TIMEOUT = 30
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_BUNDLE_BYTES = 192 * 1024 * 1024
MAX_REDIRECTS = 4
USER_AGENT = "Milora_tool-SourceArchitecture/PrimaryRepositoryHistory"
TRUSTED_SOURCE_HOSTS = frozenset({
    "api.github.com",
    "github.com",
    "git.mero.moe",
    "gitlab.com",
    "raw.githubusercontent.com",
})

class RepositorySourceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "source_error", diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.diagnostics = diagnostics or {}


@dataclass(frozen=True)
class SourceFileSpec:
    key: str
    paths: tuple[str, ...]
    required: bool = True


@dataclass(frozen=True)
class RepositoryDefinition:
    game_id: str
    primary_id: str
    primary_name: str
    repository_url: str
    raw_bases: tuple[str, ...]
    files: tuple[SourceFileSpec, ...]
    minimum_count: int


@dataclass
class FetchBundle:
    definition: RepositoryDefinition
    files: dict[str, Any]
    manifests: list[dict[str, Any]]
    fetched_at: int
    source_ref: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class ParsedCatalog:
    rows: list[dict[str, Any]]
    diagnostics: dict[str, Any]


SOURCE_DEFINITIONS: dict[str, RepositoryDefinition] = {
    "wuwa": RepositoryDefinition(
        game_id="wuwa",
        primary_id="ww_data",
        primary_name="Arikatsu/WutheringWaves_Data（WW_Data）",
        repository_url="https://github.com/Arikatsu/WutheringWaves_Data",
        raw_bases=(
            "https://raw.githubusercontent.com/Arikatsu/WutheringWaves_Data/master/",
            "https://raw.githubusercontent.com/Arikatsu/WutheringWaves_Data/main/",
        ),
        files=(
            SourceFileSpec("achievements", ("BinData/achievement/achievement.json",)),
            SourceFileSpec("groups", ("BinData/achievement/achievementgroup.json",)),
            SourceFileSpec("categories", ("BinData/achievement/achievementcategory.json",)),
            SourceFileSpec(
                "textmap",
                (
                    "Textmaps/zh-Hant.json",
                    "Textmaps/zh-Hant/textmap.json",
                    "Textmaps/zh-Hant/TextMap.json",
                    "Textmaps/zh-Hant/MultiText.json",
                    "Textmaps/zh-Hant/multi_text/MultiText.json",
                    "Textmaps/zh-Hant/multi_text/multi_text.json",
                ),
            ),
        ),
        minimum_count=800,
    ),
    "genshin": RepositoryDefinition(
        game_id="genshin",
        primary_id="anime_game_data",
        primary_name="Dimbreath/animegamedata2",
        repository_url="https://gitlab.com/Dimbreath/animegamedata2",
        raw_bases=(
            "https://gitlab.com/Dimbreath/animegamedata2/-/raw/main/",
            "https://gitlab.com/Dimbreath/animegamedata2/-/raw/master/",
        ),
        files=(
            SourceFileSpec(
                "achievements",
                (
                    "ExcelBinOutput/AchievementExcelConfigData.json",
                    "ExcelOutput/AchievementExcelConfigData.json",
                ),
            ),
            SourceFileSpec(
                "groups",
                (
                    "ExcelBinOutput/AchievementGoalExcelConfigData.json",
                    "ExcelOutput/AchievementGoalExcelConfigData.json",
                ),
            ),
            SourceFileSpec(
                "rewards",
                (
                    "ExcelBinOutput/RewardExcelConfigData.json",
                    "ExcelOutput/RewardExcelConfigData.json",
                ),
                required=False,
            ),
            SourceFileSpec(
                "textmap",
                (
                    "TextMap/TextMap_MediumCHT.json",
                    "TextMap_MediumCHT.json",
                    "TextMap/TextMapCHT.json",
                    "TextMapCHT.json",
                ),
            ),
        ),
        minimum_count=1200,
    ),
    "hsr": RepositoryDefinition(
        game_id="hsr",
        primary_id="turn_based_game_data",
        primary_name="Dimbreath/TurnBasedGameData",
        repository_url="https://gitlab.com/Dimbreath/turnbasedgamedata",
        raw_bases=("https://gitlab.com/Dimbreath/turnbasedgamedata/-/raw/main/",),
        files=(
            SourceFileSpec("achievements", ("ExcelOutput/AchievementData.json",)),
            SourceFileSpec("groups", ("ExcelOutput/AchievementSeries.json",)),
            SourceFileSpec("quests", ("ExcelOutput/QuestData.json",), required=False),
            SourceFileSpec("rewards", ("ExcelOutput/RewardData.json",), required=False),
            SourceFileSpec("textjoin_config", ("ExcelOutput/TextJoinConfig.json",), required=False),
            SourceFileSpec("textjoin_items", ("ExcelOutput/TextJoinItem.json",), required=False),
            SourceFileSpec("textmap", ("TextMap/TextMapCHT.json",)),
            SourceFileSpec("textmap_main", ("TextMap/TextMapMainCHT.json",), required=False),
        ),
        minimum_count=1200,
    ),
    "zzz": RepositoryDefinition(
        game_id="zzz",
        primary_id="zenless_data",
        primary_name="Dimbreath/ZenlessData",
        repository_url="https://git.mero.moe/dimbreath/ZenlessData",
        raw_bases=(
            "https://git.mero.moe/dimbreath/ZenlessData/raw/branch/master/",
            "https://raw.githubusercontent.com/Dimbreath/ZenlessData/master/",
        ),
        files=(
            SourceFileSpec("achievements", ("FileCfg/AchievementTemplateTb.json",)),
            SourceFileSpec("groups", ("FileCfg/AchieveSecondClassConfigTemplateTb.json",)),
            SourceFileSpec("arcade_achievements", ("FileCfg/ArcadeAchievementConfigTemplateTb.json",), required=False),
            SourceFileSpec("arcade_groups", ("FileCfg/ArcadeAchievementGroupTemplateTb.json",), required=False),
            SourceFileSpec("rewards", ("FileCfg/OnceRewardTemplateTb.json",), required=False),
            SourceFileSpec("monster_cards", ("FileCfg/MonsterCardConfigTemplateTb.json",), required=False),
            SourceFileSpec(
                "textmap",
                (
                    "TextMap/TextMap_CHTTemplateTb.json",
                    "TextMap/TextMapCHT.json",
                ),
            ),
            SourceFileSpec(
                "textmap_overwrite",
                ("TextMap/TextMap_CHTOverwriteTemplateTb.json",),
                required=False,
            ),
        ),
        minimum_count=600,
    ),
    "nte": RepositoryDefinition(
        game_id="nte",
        primary_id="nte_assets",
        primary_name="Waifus-Grace/NTE_Assets",
        repository_url="https://github.com/Waifus-Grace/NTE_Assets",
        raw_bases=(
            "https://raw.githubusercontent.com/Waifus-Grace/NTE_Assets/main/",
            "https://raw.githubusercontent.com/Waifus-Grace/NTE_Assets/master/",
        ),
        files=(
            SourceFileSpec("achievements", ("DataTable/DT_AchievementConfigInfo.json",)),
            SourceFileSpec("achievement_text", ("Text/ST_Achievement.json",)),
            SourceFileSpec("localization_zh_hant", ("Localization/zh-Hant/game.json",)),
        ),
        minimum_count=380,
    ),
}


def definition_for(game_id: str) -> RepositoryDefinition:
    try:
        return SOURCE_DEFINITIONS[str(game_id or "").strip()]
    except KeyError as exc:
        raise RepositorySourceError("不支援的遊戲來源。", code="unsupported_game") from exc


def _validated_source_url(value: str) -> str:
    url = str(value or "").strip()
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if parsed.scheme.casefold() != "https" or not host or host not in TRUSTED_SOURCE_HOSTS:
        raise RepositorySourceError(
            "來源網址不在允許的 HTTPS 主機清單中。",
            code="source_url_not_allowed",
            diagnostics={"host": host},
        )
    if parsed.username or parsed.password or (parsed.port not in {None, 443}):
        raise RepositorySourceError(
            "來源網址包含不允許的驗證資訊或連接埠。",
            code="source_url_not_allowed",
            diagnostics={"host": host},
        )
    return urllib.parse.urlunsplit(parsed)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_trusted_source(request: urllib.request.Request, *, timeout: int):
    opener = urllib.request.build_opener(_NoRedirect)
    current_url = _validated_source_url(request.full_url)
    for redirect_count in range(MAX_REDIRECTS + 1):
        current_request = urllib.request.Request(current_url, headers=dict(request.header_items()))
        try:
            return opener.open(current_request, timeout=timeout), current_url, redirect_count
        except urllib.error.HTTPError as exc:
            if exc.code not in {301, 302, 303, 307, 308}:
                raise
            location = str(exc.headers.get("Location") or "").strip()
            if not location or redirect_count >= MAX_REDIRECTS:
                raise RepositorySourceError(
                    "來源重新導向次數過多或缺少目標。",
                    code="source_redirect_invalid",
                    diagnostics={"url": current_url, "redirect_count": redirect_count},
                ) from exc
            current_url = _validated_source_url(urllib.parse.urljoin(current_url, location))
    raise RepositorySourceError("來源重新導向次數過多。", code="source_redirect_invalid")


def _request_bytes(url: str, *, timeout: int = DEFAULT_TIMEOUT, max_bytes: int = MAX_FILE_BYTES, attempts: int = 2) -> tuple[bytes, dict[str, Any]]:
    last_error: RepositorySourceError | None = None
    for attempt in range(1, max(1, attempts) + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json,text/plain;q=0.9,text/html;q=0.5,*/*;q=0.1",
                "Accept-Encoding": "identity",
            },
        )
        started = time.monotonic()
        try:
            response, effective_url, redirect_count = _open_trusted_source(request, timeout=timeout)
            with response:
                status = int(getattr(response, "status", 200) or 200)
                content_length = int(response.headers.get("Content-Length") or 0)
                if content_length > max_bytes:
                    raise RepositorySourceError(
                        f"來源檔案過大（{content_length} bytes），已停止下載。",
                        code="source_file_too_large",
                        diagnostics={"url": url, "content_length": content_length},
                    )
                chunks: list[bytes] = []
                total = 0
                while True:
                    chunk = response.read(min(1024 * 1024, max_bytes - total + 1))
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise RepositorySourceError(
                            "來源檔案超過安全大小上限，已停止下載。",
                            code="source_file_too_large",
                            diagnostics={"url": url, "received_bytes": total},
                        )
                    chunks.append(chunk)
                payload = b"".join(chunks)
                return payload, {
                    "url": effective_url,
                    "requested_url": url,
                    "redirect_count": redirect_count,
                    "http_status": status,
                    "size_bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "attempt": attempt,
                    "etag": str(response.headers.get("ETag") or ""),
                    "last_modified": str(response.headers.get("Last-Modified") or ""),
                }
        except RepositorySourceError as exc:
            last_error = exc
            if exc.code in {"source_file_too_large", "source_bundle_too_large", "source_json_invalid", "source_encoding_invalid", "source_url_not_allowed", "source_redirect_invalid"}:
                raise
        except urllib.error.HTTPError as exc:
            last_error = RepositorySourceError(
                f"來源回應 HTTP {exc.code}。",
                code=f"upstream_http_{int(exc.code)}",
                diagnostics={"url": url, "http_status": int(exc.code), "attempt": attempt},
            )
            if int(exc.code) not in {408, 429, 500, 502, 503, 504}:
                raise last_error from exc
        except urllib.error.URLError as exc:
            reason = str(getattr(exc, "reason", "") or exc)
            code = "upstream_timeout" if "timed out" in reason.casefold() else "upstream_connection_failed"
            last_error = RepositorySourceError(
                f"無法連線來源：{reason}",
                code=code,
                diagnostics={"url": url, "reason": reason, "attempt": attempt},
            )
        except TimeoutError:
            last_error = RepositorySourceError(
                "來源連線逾時。", code="upstream_timeout", diagnostics={"url": url, "attempt": attempt}
            )
        if attempt < max(1, attempts):
            time.sleep(min(1.5, 0.35 * attempt))
    assert last_error is not None
    raise last_error


def _github_default_raw_base(repository_url: str, *, timeout: int = DEFAULT_TIMEOUT) -> tuple[str, str] | None:
    owner_repo = _github_owner_repo(repository_url)
    if not owner_repo:
        return None
    owner, repo = owner_repo
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        raw, _ = _request_bytes(api_url, timeout=min(timeout, 10), max_bytes=256 * 1024, attempts=1)
        payload = _decode_json(raw, url=api_url)
    except RepositorySourceError:
        return None
    branch = str((payload.get("default_branch") if isinstance(payload, dict) else "") or "").strip()
    if not branch:
        return None
    return f"https://raw.githubusercontent.com/{owner}/{repo}/{urllib.parse.quote(branch, safe='')}/", branch


def _github_owner_repo(repository_url: str) -> tuple[str, str] | None:
    match = re.search(r"github\.com/([^/]+)/([^/#?]+)", str(repository_url or ""))
    if not match:
        return None
    owner = urllib.parse.quote(match.group(1), safe="")
    repo = urllib.parse.quote(match.group(2).removesuffix(".git"), safe="")
    return owner, repo


def _version_sort_key(value: Any) -> tuple[int, ...]:
    version = _valid_version(value)
    if not version:
        return ()
    return tuple(int(part) for part in version.split("."))


def _version_less_than(left: Any, right: Any) -> bool:
    left_key = _version_sort_key(left)
    right_key = _version_sort_key(right)
    return bool(left_key and right_key and left_key < right_key)


def _wuwa_public_version_branches(repository_url: str, *, current_ref: str, timeout: int = DEFAULT_TIMEOUT) -> tuple[list[str], dict[str, Any]]:
    owner_repo = _github_owner_repo(repository_url)
    current_version = _valid_version(current_ref)
    if not owner_repo:
        return [], {"status": "unsupported_repository_url", "current_ref": current_ref}
    owner, repo = owner_repo
    api_url = f"https://api.github.com/repos/{owner}/{repo}/branches?per_page=100"
    try:
        raw, manifest = _request_bytes(api_url, timeout=min(timeout, 15), max_bytes=1024 * 1024, attempts=1)
        payload = _decode_json(raw, url=api_url)
    except RepositorySourceError as exc:
        return [], {
            "status": "unavailable",
            "reason": exc.code,
            "error": str(exc),
            "diagnostics": dict(exc.diagnostics or {}),
            "current_ref": current_ref,
        }
    branches: list[str] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
            else:
                name = str(item or "").strip()
            version = _valid_version(name)
            if not version:
                continue
            if _version_less_than(version, "1.0"):
                continue
            if current_version and _version_less_than(current_version, version):
                continue
            branches.append(version)
    if current_version and current_version not in branches:
        branches.append(current_version)
    branches = sorted(set(branches), key=_version_sort_key)
    return branches, {
        "status": "ok",
        "url": api_url,
        "http_status": manifest.get("http_status"),
        "current_ref": current_ref,
        "current_version": current_version,
        "minimum_version": "1.0",
        "branch_count": len(branches),
        "branches": branches,
    }


def _wuwa_achievement_ids_for_ref(repository_url: str, ref: str, *, timeout: int = DEFAULT_TIMEOUT) -> tuple[set[str], dict[str, Any]]:
    owner_repo = _github_owner_repo(repository_url)
    if not owner_repo:
        raise RepositorySourceError("GitHub repository URL is not supported", code="unsupported_repository_url")
    owner, repo = owner_repo
    encoded_ref = urllib.parse.quote(str(ref or "").strip(), safe="")
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{encoded_ref}/BinData/achievement/achievement.json"
    raw, manifest = _request_bytes(url, timeout=min(timeout, 20), max_bytes=16 * 1024 * 1024, attempts=1)
    payload = _decode_json(raw, url=url)
    rows = _unwrap_rows(payload)
    achievement_ids = {
        _text_key(_get(row, "Id", "ID", "id"))
        for row in rows
        if _text_key(_get(row, "Id", "ID", "id"))
    }
    return achievement_ids, {"ref": ref, "row_count": len(rows), "id_count": len(achievement_ids), **manifest}


def _resolve_wuwa_first_seen_versions(
    achievement_ids: Iterable[str],
    *,
    repository_url: str,
    current_ref: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[dict[str, str], dict[str, Any]]:
    unresolved = {
        str(value or "").strip()
        for value in achievement_ids
        if str(value or "").strip()
    }
    if not unresolved:
        return {}, {"status": "skipped", "requested_count": 0}

    branches, branch_diagnostics = _wuwa_public_version_branches(
        repository_url,
        current_ref=current_ref,
        timeout=timeout,
    )
    if not branches:
        return {}, {
            "status": "unavailable",
            "requested_count": len(unresolved),
            "branch_resolution": branch_diagnostics,
            "resolved_count": 0,
            "unresolved_count": len(unresolved),
        }

    resolved: dict[str, str] = {}
    manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for ref in branches:
        try:
            ref_ids, manifest = _wuwa_achievement_ids_for_ref(
                repository_url,
                ref,
                timeout=timeout,
            )
        except RepositorySourceError as exc:
            failures.append({
                "ref": ref,
                "error_code": exc.code,
                "error": str(exc),
                "diagnostics": dict(exc.diagnostics or {}),
            })
            continue
        matched = sorted(unresolved.intersection(ref_ids), key=lambda value: int(value) if value.isdigit() else value)
        for achievement_id in matched:
            resolved[achievement_id] = ref
        unresolved.difference_update(matched)
        manifests.append({**manifest, "resolved_new_count": len(matched)})
        if not unresolved:
            break

    return resolved, {
        "status": "ok" if not failures else "partial",
        "requested_count": len(resolved) + len(unresolved),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "unresolved_ids": sorted(unresolved, key=lambda value: int(value) if value.isdigit() else value)[:200],
        "branch_resolution": branch_diagnostics,
        "manifests": manifests,
        "failures": failures,
    }


def _gitlab_project_path(repository_url: str) -> str:
    match = re.search(r"gitlab\.com/([^?#]+)", str(repository_url or ""), flags=re.I)
    if not match:
        return ""
    return urllib.parse.unquote(match.group(1)).strip("/").removesuffix(".git")


def _hsr_release_commits(
    repository_url: str,
    *,
    current_ref: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    project_path = _gitlab_project_path(repository_url)
    if not project_path:
        return [], {"status": "unsupported_repository_url", "repository_url": repository_url}
    query = urllib.parse.urlencode({
        "path": "ExcelOutput/AchievementData.json",
        "ref_name": current_ref or "main",
        "per_page": 100,
    })
    api_url = (
        "https://gitlab.com/api/v4/projects/"
        f"{urllib.parse.quote(project_path, safe='')}/repository/commits?{query}"
    )
    try:
        raw, manifest = _request_bytes(
            api_url,
            timeout=min(timeout, 20),
            max_bytes=4 * 1024 * 1024,
            attempts=2,
        )
        payload = _decode_json(raw, url=api_url)
    except RepositorySourceError as exc:
        return [], {
            "status": "unavailable",
            "reason": exc.code,
            "error": str(exc),
            "diagnostics": dict(exc.diagnostics or {}),
            "url": api_url,
        }

    releases_by_version: dict[str, dict[str, str]] = {}
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        commit_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or item.get("message") or "").strip()
        parsed_version = _valid_version(title)
        if not commit_id or not parsed_version:
            continue
        parts = parsed_version.split(".")
        version = ".".join(parts[:2])
        if version not in releases_by_version:
            releases_by_version[version] = {
                "version": version,
                "commit_id": commit_id,
                "title": title,
                "created_at": str(item.get("created_at") or ""),
            }
    releases = sorted(releases_by_version.values(), key=lambda item: _version_sort_key(item["version"]))
    return releases, {
        "status": "ok" if releases else "release_commits_not_found",
        "url": api_url,
        "http_status": manifest.get("http_status"),
        "current_ref": current_ref or "main",
        "release_count": len(releases),
        "versions": [item["version"] for item in releases],
    }


def _hsr_achievement_ids_for_commit(
    repository_url: str,
    commit_id: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[set[str], dict[str, Any]]:
    base = str(repository_url or "").rstrip("/").removesuffix(".git")
    if not _gitlab_project_path(base):
        raise RepositorySourceError("GitLab repository URL is not supported", code="unsupported_repository_url")
    encoded_commit = urllib.parse.quote(str(commit_id or "").strip(), safe="")
    url = f"{base}/-/raw/{encoded_commit}/ExcelOutput/AchievementData.json"
    raw, manifest = _request_bytes(
        url,
        timeout=min(timeout, 25),
        max_bytes=16 * 1024 * 1024,
        attempts=2,
    )
    payload = _decode_json(raw, url=url)
    rows = _unwrap_rows(payload)
    achievement_ids = {
        _text_key(_get(row, "AchievementID", "AchievementId", "achievementId", "ID", "id"))
        for row in rows
        if _text_key(_get(row, "AchievementID", "AchievementId", "achievementId", "ID", "id"))
    }
    return achievement_ids, {
        "commit_id": commit_id,
        "row_count": len(rows),
        "id_count": len(achievement_ids),
        **manifest,
    }


def _resolve_hsr_first_seen_versions(
    achievement_ids: Iterable[str],
    *,
    repository_url: str,
    current_ref: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[dict[str, str], dict[str, Any]]:
    requested = {
        str(value or "").strip()
        for value in achievement_ids
        if str(value or "").strip()
    }
    if not requested:
        return {}, {"status": "skipped", "requested_count": 0}

    releases, release_diagnostics = _hsr_release_commits(
        repository_url,
        current_ref=current_ref,
        timeout=timeout,
    )
    if len(releases) < 2:
        return {}, {
            "status": "unavailable",
            "requested_count": len(requested),
            "resolved_count": 0,
            "unresolved_count": len(requested),
            "release_resolution": release_diagnostics,
        }

    unresolved = set(requested)
    resolved: dict[str, str] = {}
    seen_ids: set[str] = set()
    manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    baseline_ready = False
    for release in releases:
        try:
            release_ids, manifest = _hsr_achievement_ids_for_commit(
                repository_url,
                release["commit_id"],
                timeout=timeout,
            )
        except RepositorySourceError as exc:
            failures.append({
                "version": release["version"],
                "commit_id": release["commit_id"],
                "error_code": exc.code,
                "error": str(exc),
                "diagnostics": dict(exc.diagnostics or {}),
            })
            break

        newly_seen = release_ids - seen_ids if baseline_ready else set()
        matched = sorted(
            unresolved.intersection(newly_seen),
            key=lambda value: int(value) if value.isdigit() else value,
        )
        for achievement_id in matched:
            resolved[achievement_id] = release["version"]
        unresolved.difference_update(matched)
        seen_ids.update(release_ids)
        baseline_ready = True
        manifests.append({
            **manifest,
            "version": release["version"],
            "release_title": release["title"],
            "first_seen_count": len(newly_seen),
            "resolved_requested_count": len(matched),
        })
        if not unresolved:
            break

    status = "ok" if not unresolved and not failures else ("partial" if resolved else "unavailable")
    return resolved, {
        "status": status,
        "requested_count": len(requested),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "unresolved_ids": sorted(
            unresolved,
            key=lambda value: int(value) if value.isdigit() else value,
        )[:200],
        "release_resolution": release_diagnostics,
        "manifests": manifests,
        "failures": failures,
        "rule": "first_release_snapshot_where_id_appears_after_prior_baseline",
    }


def _genshin_release_commits(
    repository_url: str,
    *,
    current_ref: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    project_path = _gitlab_project_path(repository_url)
    if not project_path:
        return [], {"status": "unsupported_repository_url", "repository_url": repository_url}
    source_path = "ExcelBinOutput/AchievementExcelConfigData.json"
    query = urllib.parse.urlencode({
        "path": source_path,
        "ref_name": current_ref or "main",
        "per_page": 100,
    })
    api_url = (
        "https://gitlab.com/api/v4/projects/"
        f"{urllib.parse.quote(project_path, safe='')}/repository/commits?{query}"
    )
    try:
        raw, manifest = _request_bytes(
            api_url,
            timeout=min(timeout, 20),
            max_bytes=4 * 1024 * 1024,
            attempts=2,
        )
        payload = _decode_json(raw, url=api_url)
    except RepositorySourceError as exc:
        return [], {
            "status": "unavailable",
            "reason": exc.code,
            "error": str(exc),
            "diagnostics": dict(exc.diagnostics or {}),
            "url": api_url,
        }

    releases_by_version: dict[str, dict[str, str]] = {}
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        commit_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or item.get("message") or "").strip()
        version_match = re.search(r"CNRELWin(\d+\.\d+)(?:\.\d+)?", title, flags=re.I)
        if not commit_id or not version_match:
            continue
        version = version_match.group(1)
        if version not in releases_by_version:
            releases_by_version[version] = {
                "version": version,
                "commit_id": commit_id,
                "title": title,
                "created_at": str(item.get("created_at") or ""),
            }
    releases = sorted(releases_by_version.values(), key=lambda item: _version_sort_key(item["version"]))
    return releases, {
        "status": "ok" if releases else "release_commits_not_found",
        "url": api_url,
        "http_status": manifest.get("http_status"),
        "current_ref": current_ref or "main",
        "source_path": source_path,
        "release_count": len(releases),
        "versions": [item["version"] for item in releases],
    }


def _genshin_achievement_ids_for_commit(
    repository_url: str,
    commit_id: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[set[str], dict[str, Any]]:
    base = str(repository_url or "").rstrip("/").removesuffix(".git")
    if not _gitlab_project_path(base):
        raise RepositorySourceError("GitLab repository URL is not supported", code="unsupported_repository_url")
    encoded_commit = urllib.parse.quote(str(commit_id or "").strip(), safe="")
    url = f"{base}/-/raw/{encoded_commit}/ExcelBinOutput/AchievementExcelConfigData.json"
    raw, manifest = _request_bytes(
        url,
        timeout=min(timeout, 25),
        max_bytes=16 * 1024 * 1024,
        attempts=2,
    )
    payload = _decode_json(raw, url=url)
    rows = _unwrap_rows(payload)
    active_rows = [
        row for row in rows
        if not _as_bool(_get(row, "isDisuse", "IsDisuse", "disused", "Disused"))
    ]
    achievement_ids = {
        _text_key(_get(row, "id", "Id", "achievementId", "AchievementId"))
        for row in active_rows
        if _text_key(_get(row, "id", "Id", "achievementId", "AchievementId"))
    }
    return achievement_ids, {
        "commit_id": commit_id,
        "row_count": len(rows),
        "active_row_count": len(active_rows),
        "id_count": len(achievement_ids),
        **manifest,
    }


def _resolve_genshin_first_seen_versions(
    achievement_ids: Iterable[str],
    *,
    repository_url: str,
    current_ref: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[dict[str, str], dict[str, Any]]:
    requested = {
        str(value or "").strip()
        for value in achievement_ids
        if str(value or "").strip()
    }
    if not requested:
        return {}, {"status": "skipped", "requested_count": 0}

    releases, release_diagnostics = _genshin_release_commits(
        repository_url,
        current_ref=current_ref,
        timeout=timeout,
    )
    if len(releases) < 2:
        return {}, {
            "status": "unavailable",
            "requested_count": len(requested),
            "resolved_count": 0,
            "unresolved_count": len(requested),
            "release_resolution": release_diagnostics,
        }

    unresolved = set(requested)
    resolved: dict[str, str] = {}
    seen_ids: set[str] = set()
    manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    baseline_ready = False
    for release in releases:
        try:
            release_ids, manifest = _genshin_achievement_ids_for_commit(
                repository_url,
                release["commit_id"],
                timeout=timeout,
            )
        except RepositorySourceError as exc:
            failures.append({
                "version": release["version"],
                "commit_id": release["commit_id"],
                "error_code": exc.code,
                "error": str(exc),
                "diagnostics": dict(exc.diagnostics or {}),
            })
            break

        newly_seen = release_ids - seen_ids if baseline_ready else set()
        matched = sorted(
            unresolved.intersection(newly_seen),
            key=lambda value: int(value) if value.isdigit() else value,
        )
        for achievement_id in matched:
            resolved[achievement_id] = release["version"]
        unresolved.difference_update(matched)
        seen_ids.update(release_ids)
        baseline_ready = True
        manifests.append({
            **manifest,
            "version": release["version"],
            "release_title": release["title"],
            "first_seen_count": len(newly_seen),
            "resolved_requested_count": len(matched),
        })
        if not unresolved:
            break

    status = "ok" if not unresolved and not failures else ("partial" if resolved else "unavailable")
    return resolved, {
        "status": status,
        "requested_count": len(requested),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "unresolved_ids": sorted(
            unresolved,
            key=lambda value: int(value) if value.isdigit() else value,
        )[:200],
        "release_resolution": release_diagnostics,
        "manifests": manifests,
        "failures": failures,
        "rule": "first_available_cnrel_release_snapshot_where_active_id_appears_after_prior_baseline",
    }


def _gitea_owner_repo(repository_url: str) -> tuple[str, str, str] | None:
    match = re.match(r"^(https?://[^/]+)/([^/]+)/([^/#?]+)", str(repository_url or "").rstrip("/"), flags=re.I)
    if not match:
        return None
    host = match.group(1).rstrip("/")
    owner = urllib.parse.unquote(match.group(2)).strip()
    repo = urllib.parse.unquote(match.group(3)).strip().removesuffix(".git")
    if not host or not owner or not repo:
        return None
    return host, owner, repo


def _zzz_release_commits(
    repository_url: str,
    *,
    current_ref: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    coordinates = _gitea_owner_repo(repository_url)
    if not coordinates:
        return [], {"status": "unsupported_repository_url", "repository_url": repository_url}
    host, owner, repo = coordinates
    releases_by_version: dict[str, dict[str, str]] = {}
    manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for page in range(1, 5):
        branch = urllib.parse.quote(current_ref or "master", safe="")
        page_url = (
            f"{host}/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(repo, safe='')}"
            f"/commits/branch/{branch}?page={page}"
        )
        try:
            raw, manifest = _request_bytes(
                page_url,
                timeout=min(timeout, 25),
                max_bytes=5 * 1024 * 1024,
                attempts=2,
            )
        except RepositorySourceError as exc:
            failures.append({
                "page": page,
                "url": page_url,
                "error_code": exc.code,
                "error": str(exc),
                "diagnostics": dict(exc.diagnostics or {}),
            })
            break
        source = raw.decode("utf-8", errors="replace")
        page_rows: list[dict[str, str]] = []
        for row_html in re.findall(r"<tr\b[^>]*>.*?</tr>", source, flags=re.I | re.S):
            commit_match = re.search(r'/commit/([0-9a-f]{40})', row_html, flags=re.I)
            title_match = re.search(
                r'<span\b[^>]*class="[^"]*\bcommit-summary\b[^"]*"[^>]*title="([^"]*)"',
                row_html,
                flags=re.I | re.S,
            )
            if not commit_match or not title_match:
                continue
            date_match = re.search(r'<relative-time\b[^>]*datetime="([^"]*)"', row_html, flags=re.I)
            page_rows.append({
                "commit_id": commit_match.group(1),
                "title": html.unescape(title_match.group(1)).strip(),
                "created_at": html.unescape(date_match.group(1)).strip() if date_match else "",
            })
        manifests.append({"page": page, "row_count": len(page_rows), "mode": "gitea_commit_page", **manifest})
        for item in page_rows:
            commit_id = item["commit_id"]
            title = item["title"]
            parsed_version = _valid_version(title)
            if not commit_id or not parsed_version:
                continue
            version = ".".join(parsed_version.split(".")[:2])
            if version in releases_by_version:
                continue
            releases_by_version[version] = {
                "version": version,
                "commit_id": commit_id,
                "title": title,
                "created_at": item["created_at"],
            }
        if not page_rows:
            break
    releases = sorted(releases_by_version.values(), key=lambda item: _version_sort_key(item["version"]))
    status = "ok" if releases and not failures else ("partial" if releases else "unavailable")
    return releases, {
        "status": status,
        "repository_url": repository_url,
        "current_ref": current_ref or "master",
        "release_count": len(releases),
        "versions": [item["version"] for item in releases],
        "manifests": manifests,
        "failures": failures,
    }


def _zzz_achievement_ids_for_commit(
    repository_url: str,
    commit_id: str,
    *,
    include_normal: bool,
    include_arcade: bool,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[set[str], dict[str, Any]]:
    coordinates = _gitea_owner_repo(repository_url)
    if not coordinates:
        raise RepositorySourceError("Gitea repository URL is not supported", code="unsupported_repository_url")
    host, owner, repo = coordinates
    paths: list[tuple[str, tuple[str, ...], re.Pattern[str], bool]] = []
    if include_normal:
        paths.append((
            "normal",
            ("GJAFKJENFBK", "MPLJPOKFCAP", "GAPDDOJPFGI", "Id", "ID", "id", "AchievementId"),
            re.compile(r"^AchievementName_(\d+)$"),
            True,
        ))
    if include_arcade:
        paths.append((
            "arcade",
            ("PEFODMAOLPK", "NOBPPDIPFPO", "Id", "ID", "id", "AchievementId"),
            re.compile(r"^ArcadeAchievement_(\d+)_Name$"),
            False,
        ))
    encoded_commit = urllib.parse.quote(str(commit_id or "").strip(), safe="")
    base = (
        f"{host}/{urllib.parse.quote(owner, safe='')}/{urllib.parse.quote(repo, safe='')}"
        f"/raw/commit/{encoded_commit}/FileCfg/"
    )
    achievement_ids: set[str] = set()
    manifests: list[dict[str, Any]] = []
    for source_type, id_keys, name_token_pattern, required in paths:
        filename = "AchievementTemplateTb.json" if source_type == "normal" else "ArcadeAchievementConfigTemplateTb.json"
        url = f"{base}{filename}"
        try:
            raw, manifest = _request_bytes(
                url,
                timeout=min(timeout, 25),
                max_bytes=16 * 1024 * 1024,
                attempts=2,
            )
            payload = _decode_json(raw, url=url)
        except RepositorySourceError as exc:
            if required:
                raise
            manifests.append({
                "source_type": source_type,
                "url": url,
                "status": "optional_missing",
                "error_code": exc.code,
            })
            continue
        rows = _unwrap_rows(payload)
        source_ids: set[str] = set()
        token_derived_count = 0
        fallback_key_count = 0
        for row in rows:
            achievement_id = ""
            if isinstance(row, dict):
                for value in row.values():
                    match = name_token_pattern.fullmatch(str(value or "").strip())
                    if match:
                        achievement_id = match.group(1)
                        token_derived_count += 1
                        break
            if not achievement_id:
                achievement_id = _text_key(_get(row, *id_keys))
                if achievement_id:
                    fallback_key_count += 1
            if achievement_id:
                source_ids.add(achievement_id)
        achievement_ids.update(source_ids)
        manifests.append({
            "source_type": source_type,
            "row_count": len(rows),
            "id_count": len(source_ids),
            "token_derived_count": token_derived_count,
            "fallback_key_count": fallback_key_count,
            **manifest,
        })
    return achievement_ids, {
        "commit_id": commit_id,
        "id_count": len(achievement_ids),
        "files": manifests,
    }


def _resolve_zzz_first_seen_versions(
    normal_achievement_ids: Iterable[str],
    arcade_achievement_ids: Iterable[str],
    *,
    repository_url: str,
    current_ref: str,
    baseline_version: str = "",
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[dict[str, str], dict[str, Any]]:
    normal_requested = {str(value or "").strip() for value in normal_achievement_ids if str(value or "").strip()}
    arcade_requested = {str(value or "").strip() for value in arcade_achievement_ids if str(value or "").strip()}
    requested = normal_requested | arcade_requested
    if not requested:
        return {}, {"status": "skipped", "requested_count": 0}
    releases, release_diagnostics = _zzz_release_commits(
        repository_url,
        current_ref=current_ref,
        timeout=timeout,
    )
    normalized_baseline = _valid_version(baseline_version)
    if normalized_baseline and releases:
        baseline_key = _version_sort_key(normalized_baseline)
        prior = [release for release in releases if _version_sort_key(release["version"]) <= baseline_key]
        if prior:
            selected_baseline = prior[-1]
            releases = [
                release for release in releases
                if _version_sort_key(release["version"]) >= _version_sort_key(selected_baseline["version"])
            ]
            release_diagnostics["requested_baseline_version"] = normalized_baseline
            release_diagnostics["selected_baseline_version"] = selected_baseline["version"]
            release_diagnostics["selected_versions"] = [release["version"] for release in releases]
    if len(releases) < 2:
        return {}, {
            "status": "unavailable",
            "requested_count": len(requested),
            "resolved_count": 0,
            "unresolved_count": len(requested),
            "release_resolution": release_diagnostics,
        }
    unresolved = set(requested)
    resolved: dict[str, str] = {}
    seen_ids: set[str] = set()
    manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    baseline_ready = False
    for release in releases:
        try:
            release_ids, manifest = _zzz_achievement_ids_for_commit(
                repository_url,
                release["commit_id"],
                include_normal=bool(normal_requested),
                include_arcade=bool(arcade_requested),
                timeout=timeout,
            )
        except RepositorySourceError as exc:
            failures.append({
                "version": release["version"],
                "commit_id": release["commit_id"],
                "error_code": exc.code,
                "error": str(exc),
                "diagnostics": dict(exc.diagnostics or {}),
            })
            break
        newly_seen = release_ids - seen_ids if baseline_ready else set()
        matched = sorted(unresolved.intersection(newly_seen), key=lambda value: int(value) if value.isdigit() else value)
        for achievement_id in matched:
            resolved[achievement_id] = release["version"]
        unresolved.difference_update(matched)
        seen_ids.update(release_ids)
        baseline_ready = True
        manifests.append({
            **manifest,
            "version": release["version"],
            "release_title": release["title"],
            "first_seen_count": len(newly_seen),
            "resolved_requested_count": len(matched),
        })
        if not unresolved:
            break
    status = "ok" if not unresolved and not failures else ("partial" if resolved else "unavailable")
    return resolved, {
        "status": status,
        "requested_count": len(requested),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "unresolved_ids": sorted(unresolved, key=lambda value: int(value) if value.isdigit() else value)[:200],
        "release_resolution": release_diagnostics,
        "manifests": manifests,
        "failures": failures,
        "rule": "first_release_snapshot_where_id_appears_after_prior_baseline",
    }


NTE_ACHIEVEMENT_PATH = "DataTable/DT_AchievementConfigInfo.json"


def _nte_release_commits(repository_url: str, *, timeout: int = DEFAULT_TIMEOUT) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    owner_repo = _github_owner_repo(repository_url)
    if not owner_repo:
        return [], {"status": "unsupported_repository_url", "repository_url": repository_url}
    owner, repo = owner_repo
    commits_url = (
        f"https://api.github.com/repos/{owner}/{repo}/commits"
        f"?path={urllib.parse.quote(NTE_ACHIEVEMENT_PATH, safe='')}&per_page=100"
    )
    try:
        raw, commit_manifest = _request_bytes(
            commits_url,
            timeout=min(timeout, 20),
            max_bytes=5 * 1024 * 1024,
            attempts=2,
        )
        payload = _decode_json(raw, url=commits_url)
    except RepositorySourceError as exc:
        return [], {
            "status": "unavailable",
            "repository_url": repository_url,
            "error_code": exc.code,
            "error": str(exc),
            "diagnostics": dict(exc.diagnostics or {}),
        }

    releases: list[dict[str, Any]] = []
    readme_manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        commit_id = str(item.get("sha") or "").strip()
        commit = item.get("commit") if isinstance(item.get("commit"), dict) else {}
        message = str(commit.get("message") or "").splitlines()[0].strip()
        committer = commit.get("committer") if isinstance(commit.get("committer"), dict) else {}
        created_at = str(committer.get("date") or "").strip()
        if not commit_id:
            continue
        readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{urllib.parse.quote(commit_id, safe='')}/README.md"
        try:
            readme_raw, readme_manifest = _request_bytes(
                readme_url,
                timeout=min(timeout, 15),
                max_bytes=256 * 1024,
                attempts=1,
            )
            readme = readme_raw.decode("utf-8-sig", errors="strict")
            readme_manifests.append({"commit_id": commit_id, **readme_manifest})
        except (RepositorySourceError, UnicodeDecodeError) as exc:
            failures.append({"commit_id": commit_id, "stage": "readme", "error": str(exc)})
            continue
        version_line = re.search(r"Version\s*:\s*([^\r\n]+)", readme, flags=re.I)
        version_context = version_line.group(1).strip() if version_line else ""
        if not re.search(r"\bGlobal\b", version_context, flags=re.I):
            continue
        if re.search(r"\b(?:CN|CBT)\b", version_context, flags=re.I):
            continue
        version_match = re.search(r"\d+\.\d+(?:\.\d+)?", message)
        if not version_match:
            version_match = re.search(r"\d+\.\d+(?:\.\d+)?", version_context)
        if not version_match:
            failures.append({"commit_id": commit_id, "stage": "version", "message": message, "readme": version_context})
            continue
        releases.append({
            "version": version_match.group(0),
            "first_seen_version": f"{version_match.group(0)} Global",
            "commit_id": commit_id,
            "title": message,
            "created_at": created_at,
            "readme_version": version_context,
        })
    releases.sort(key=lambda row: (str(row.get("created_at") or ""), _version_sort_key(row.get("version"))))
    return releases, {
        "status": "ok" if releases and not failures else ("partial" if releases else "unavailable"),
        "repository_url": repository_url,
        "commits_url": commits_url,
        "release_count": len(releases),
        "versions": [row["version"] for row in releases],
        "rule": "global_readme_scope_and_commit_version",
        "commit_manifest": commit_manifest,
        "readme_manifests": readme_manifests,
        "failures": failures,
    }


def _nte_achievement_ids_for_commit(
    repository_url: str,
    commit_id: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[set[str], dict[str, Any]]:
    owner_repo = _github_owner_repo(repository_url)
    if not owner_repo:
        raise RepositorySourceError("GitHub repository URL is not supported", code="unsupported_repository_url")
    owner, repo = owner_repo
    encoded_commit = urllib.parse.quote(str(commit_id or "").strip(), safe="")
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{encoded_commit}/{NTE_ACHIEVEMENT_PATH}"
    raw, manifest = _request_bytes(url, timeout=min(timeout, 25), max_bytes=16 * 1024 * 1024, attempts=2)
    payload = _decode_json(raw, url=url)
    container = payload[0] if isinstance(payload, list) and payload and isinstance(payload[0], dict) else {}
    rows = container.get("Rows") if isinstance(container, dict) else None
    if not isinstance(rows, dict):
        raise RepositorySourceError(
            "NTE_Assets 歷史成就檔缺少 Rows 對照表。",
            code="source_structure_changed",
            diagnostics={"url": url, "commit_id": commit_id},
        )
    ids = {str(value).strip() for value in rows if str(value).strip()}
    return ids, {"commit_id": commit_id, "row_count": len(rows), "id_count": len(ids), **manifest}


def _resolve_nte_first_seen_versions(
    achievement_ids: Iterable[str],
    *,
    repository_url: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[dict[str, str], dict[str, Any]]:
    requested = {str(value or "").strip() for value in achievement_ids if str(value or "").strip()}
    if not requested:
        return {}, {"status": "skipped", "requested_count": 0}
    releases, release_diagnostics = _nte_release_commits(repository_url, timeout=timeout)
    if not releases:
        return {}, {
            "status": "unavailable",
            "requested_count": len(requested),
            "resolved_count": 0,
            "unresolved_count": len(requested),
            "release_resolution": release_diagnostics,
        }
    unresolved = set(requested)
    resolved: dict[str, str] = {}
    manifests: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for release in releases:
        try:
            release_ids, manifest = _nte_achievement_ids_for_commit(
                repository_url,
                release["commit_id"],
                timeout=timeout,
            )
        except RepositorySourceError as exc:
            failures.append({
                "version": release["version"],
                "commit_id": release["commit_id"],
                "error_code": exc.code,
                "error": str(exc),
                "diagnostics": dict(exc.diagnostics or {}),
            })
            continue
        matched = sorted(unresolved.intersection(release_ids))
        for achievement_id in matched:
            resolved[achievement_id] = release["first_seen_version"]
        unresolved.difference_update(matched)
        manifests.append({
            **manifest,
            "version": release["version"],
            "first_seen_version": release["first_seen_version"],
            "resolved_new_count": len(matched),
        })
        if not unresolved:
            break
    status = "ok" if not unresolved and not failures else ("partial" if resolved else "unavailable")
    return resolved, {
        "status": status,
        "requested_count": len(requested),
        "resolved_count": len(resolved),
        "unresolved_count": len(unresolved),
        "unresolved_ids": sorted(unresolved)[:200],
        "release_resolution": release_diagnostics,
        "manifests": manifests,
        "failures": failures,
        "rule": "first_global_release_snapshot_where_achievement_row_id_exists",
    }


def _raw_base_ref(base: str) -> str:
    match = re.search(r"raw\.githubusercontent\.com/[^/]+/[^/]+/([^/]+)/", str(base or ""))
    if match:
        return urllib.parse.unquote(match.group(1))
    if "/master/" in str(base or ""):
        return "master"
    if "/main/" in str(base or ""):
        return "main"
    return ""


def _decode_json(data: bytes, *, url: str) -> Any:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return json.loads(data.decode(encoding))
        except UnicodeDecodeError:
            continue
        except json.JSONDecodeError as exc:
            raise RepositorySourceError(
                f"來源檔案不是有效 JSON：{exc}",
                code="source_json_invalid",
                diagnostics={"url": url, "line": exc.lineno, "column": exc.colno},
            ) from exc
    raise RepositorySourceError("來源文字編碼不是 UTF-8。", code="source_encoding_invalid", diagnostics={"url": url})


def _repository_ref_from_base(base: str) -> str:
    match = re.search(r"/-/raw/([^/]+)/", str(base or ""))
    if match:
        return match.group(1)
    match = re.search(r"/([^/]+)/$", str(base or ""))
    return match.group(1) if match else ""


def _active_achievement_probe_count(game_id: str, payload: Any) -> tuple[int, int]:
    rows = _unwrap_rows(payload)
    total = len(rows)
    if game_id != "genshin":
        return total, total
    active = sum(
        1 for row in rows
        if not _as_bool(_get(row, "isDisuse", "IsDisuse", "disused", "Disused"))
    )
    return active, total


def _enforce_bundle_budget(manifests: Sequence[Mapping[str, Any]]) -> None:
    total = sum(max(0, int(item.get("size_bytes") or 0)) for item in manifests)
    if total > MAX_BUNDLE_BYTES:
        raise RepositorySourceError(
            "來源資料組合超過安全大小上限，已停止同步。",
            code="source_bundle_too_large",
            diagnostics={"received_bytes": total, "max_bytes": MAX_BUNDLE_BYTES},
        )


def _fetch_genshin_coherent_bundle(definition: RepositoryDefinition, *, timeout: int) -> FetchBundle:
    achievement_spec = next((spec for spec in definition.files if spec.key == "achievements"), None)
    if achievement_spec is None:
        raise RepositorySourceError(
            "AnimeGameData2 未設定成就主檔。",
            code="required_source_file_missing",
            diagnostics={"game_id": definition.game_id, "file_key": "achievements"},
        )

    probes: list[dict[str, Any]] = []
    probe_failures: list[dict[str, Any]] = []
    for base_index, base in enumerate(definition.raw_bases):
        last_error: RepositorySourceError | None = None
        for relative_path in achievement_spec.paths:
            url = base + relative_path
            try:
                raw, manifest = _request_bytes(url, timeout=timeout)
                payload = _decode_json(raw, url=url)
                active_count, total_count = _active_achievement_probe_count(definition.game_id, payload)
                probes.append({
                    "base": base,
                    "base_index": base_index,
                    "ref": _repository_ref_from_base(base),
                    "path": relative_path,
                    "payload": payload,
                    "manifest": {"key": "achievements", "path": relative_path, **manifest},
                    "active_count": active_count,
                    "total_count": total_count,
                })
                break
            except RepositorySourceError as exc:
                last_error = exc
        if last_error and not any(row.get("base") == base for row in probes):
            probe_failures.append({
                "base": base,
                "ref": _repository_ref_from_base(base),
                "error_code": last_error.code,
                "error": str(last_error),
                "diagnostics": dict(last_error.diagnostics or {}),
            })

    if not probes:
        raise RepositorySourceError(
            "AnimeGameData2 的 main 與 master 分支都無法取得成就主檔。",
            code="required_source_file_missing",
            diagnostics={"game_id": definition.game_id, "file_key": "achievements", "branch_failures": probe_failures},
        )

    # Prefer the branch exposing the largest active catalogue. A tie keeps the
    # configured order, while every remaining file is fetched from that same
    # branch so a preview can never mix stale and current branch generations.
    ranked = sorted(
        probes,
        key=lambda row: (int(row["active_count"]), int(row["total_count"]), -int(row["base_index"])),
        reverse=True,
    )
    bundle_failures: list[dict[str, Any]] = []
    for selected in ranked:
        files: dict[str, Any] = {"achievements": selected["payload"]}
        manifests: list[dict[str, Any]] = [dict(selected["manifest"])]
        _enforce_bundle_budget(manifests)
        warnings: list[str] = []
        complete = True
        for spec in definition.files:
            if spec.key == "achievements":
                continue
            last_error: RepositorySourceError | None = None
            found = False
            for relative_path in spec.paths:
                url = str(selected["base"]) + relative_path
                try:
                    raw, manifest = _request_bytes(url, timeout=timeout)
                    files[spec.key] = _decode_json(raw, url=url)
                    manifests.append({"key": spec.key, "path": relative_path, **manifest})
                    _enforce_bundle_budget(manifests)
                    found = True
                    break
                except RepositorySourceError as exc:
                    last_error = exc
            if found:
                continue
            if spec.required:
                complete = False
                bundle_failures.append({
                    "base": selected["base"],
                    "ref": selected["ref"],
                    "file_key": spec.key,
                    "error_code": last_error.code if last_error else "required_source_file_missing",
                    "error": str(last_error or "missing"),
                })
                break
            warnings.append(f"未取得選用來源檔案：{spec.key}")
        if not complete:
            continue

        branch_candidates = [
            {
                "ref": str(row["ref"]),
                "base": str(row["base"]),
                "active_achievement_count": int(row["active_count"]),
                "total_achievement_rows": int(row["total_count"]),
                "selected": row is selected,
            }
            for row in ranked
        ]
        manifests.insert(0, {
            "key": "branch_selection",
            "selection_policy": "highest_active_achievement_count_with_branch_consistency",
            "selected_ref": selected["ref"],
            "selected_base": selected["base"],
            "selected_active_achievement_count": selected["active_count"],
            "candidates": branch_candidates,
            "probe_failures": probe_failures,
        })
        if ranked[0] is not probes[0] or selected.get("base_index") != 0:
            warnings.append(
                f"已選擇成就筆數較完整的 {selected['ref'] or '候選'} 分支（{selected['active_count']} 筆），"
                "並由同一分支讀取全部必要檔案。"
            )
        return FetchBundle(
            definition=definition,
            files=files,
            manifests=manifests,
            fetched_at=int(time.time()),
            source_ref=str(selected["ref"] or ""),
            warnings=warnings,
        )

    raise RepositorySourceError(
        "AnimeGameData2 可取得成就主檔，但沒有任何單一分支同時提供完整必要檔案；已停止混用分支資料。",
        code="repository_branch_bundle_incomplete",
        diagnostics={"game_id": definition.game_id, "branch_candidates": [
            {"ref": row["ref"], "active_count": row["active_count"], "total_count": row["total_count"]}
            for row in ranked
        ], "bundle_failures": bundle_failures, "probe_failures": probe_failures},
    )


def fetch_repository_bundle(game_id: str, *, timeout: int = DEFAULT_TIMEOUT) -> FetchBundle:
    definition = definition_for(game_id)
    if game_id == "genshin" and len(definition.raw_bases) > 1:
        return _fetch_genshin_coherent_bundle(definition, timeout=timeout)

    raw_bases = list(definition.raw_bases)
    if game_id == "wuwa":
        dynamic = _github_default_raw_base(definition.repository_url, timeout=timeout)
        if dynamic and dynamic[0] not in raw_bases:
            raw_bases.insert(0, dynamic[0])

    files: dict[str, Any] = {}
    manifests: list[dict[str, Any]] = []
    warnings: list[str] = []
    used_ref = ""
    for spec in definition.files:
        last_error: RepositorySourceError | None = None
        found = False
        for base in raw_bases:
            for relative_path in spec.paths:
                url = base + relative_path
                try:
                    raw, manifest = _request_bytes(url, timeout=timeout)
                    files[spec.key] = _decode_json(raw, url=url)
                    manifests.append({"key": spec.key, "path": relative_path, **manifest})
                    _enforce_bundle_budget(manifests)
                    used_ref = _raw_base_ref(base) or used_ref
                    found = True
                    break
                except RepositorySourceError as exc:
                    last_error = exc
                    if exc.code not in {"upstream_http_404"}:
                        continue
            if found:
                break
        if not found:
            if spec.required:
                details = dict((last_error.diagnostics if last_error else {}) or {})
                details.update({"game_id": game_id, "file_key": spec.key, "candidates": list(spec.paths)})
                raise RepositorySourceError(
                    f"主要來源缺少必要檔案：{spec.key}。已停止此遊戲更新。",
                    code="required_source_file_missing",
                    diagnostics=details,
                )
            warnings.append(f"未取得選用來源檔案：{spec.key}")
    return FetchBundle(
        definition=definition,
        files=files,
        manifests=manifests,
        fetched_at=int(time.time()),
        source_ref=used_ref,
        warnings=warnings,
    )


def _unwrap_rows(value: Any) -> list[dict[str, Any]]:
    """Return the most likely table rows from known or obfuscated JSON containers."""
    if isinstance(value, list):
        return [dict(row) for row in value if isinstance(row, dict)]
    if not isinstance(value, dict):
        return []
    for key in ("items", "data", "Data", "rows", "Rows", "list", "List", "records", "Records", "JKMFEMCLDNN"):
        nested = value.get(key)
        if isinstance(nested, list):
            rows = [dict(row) for row in nested if isinstance(row, dict)]
            if rows:
                return rows
    if value and all(isinstance(row, dict) for row in value.values()):
        return [dict(row) for row in value.values()]

    candidates: list[list[dict[str, Any]]] = []

    def visit(node: Any, depth: int = 0) -> None:
        if depth > 4:
            return
        if isinstance(node, list):
            rows = [dict(row) for row in node if isinstance(row, dict)]
            if rows and len(rows) >= max(1, len(node) // 2):
                candidates.append(rows)
            for item in node[:20]:
                if isinstance(item, (dict, list)):
                    visit(item, depth + 1)
        elif isinstance(node, dict):
            for nested in node.values():
                if isinstance(nested, (dict, list)):
                    visit(nested, depth + 1)

    visit(value)
    return max(candidates, key=len) if candidates else []


def _get(row: Mapping[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row:
            return row[name]
    lowered = {str(key).casefold(): key for key in row}
    for name in names:
        key = lowered.get(name.casefold())
        if key is not None:
            return row[key]
    return default


def _scalar(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("Hash", "hash", "Value", "value", "ID", "Id", "id", "Text", "text", "Name", "name"):
            if key in value:
                return _scalar(value[key])
        return ""
    if isinstance(value, (list, tuple)):
        return _scalar(value[0]) if value else ""
    return value


def _text_key(value: Any) -> str:
    scalar = _scalar(value)
    if scalar is None:
        return ""
    if isinstance(scalar, float) and scalar.is_integer():
        scalar = int(scalar)
    return str(scalar).strip()


def _numeric_text_key_aliases(value: Any) -> tuple[str, ...]:
    key = _text_key(value)
    aliases: list[str] = [key] if key else []
    try:
        number = int(key, 10)
    except (TypeError, ValueError):
        return tuple(dict.fromkeys(aliases))
    if 0 <= number <= 0xFFFFFFFF:
        unsigned = number
        signed = number if number < 0x80000000 else number - 0x100000000
        aliases.extend((str(unsigned), str(signed)))
    elif -0x80000000 <= number < 0:
        aliases.extend((str(number), str(number + 0x100000000)))
    return tuple(dict.fromkeys(aliases))


def _build_text_map(*payloads: Any) -> dict[str, str]:
    """Build a text map from direct dictionaries, row tables, or nested containers.

    Genshin text hashes are commonly unsigned 32-bit values while some dumps expose
    signed keys. Both representations are registered to the same Traditional Chinese text.
    """
    result: dict[str, str] = {}

    def add(key: Any, value: Any) -> None:
        text_value = value
        if isinstance(value, dict):
            text_value = _get(value, "Text", "text", "Value", "value", "Content", "content", default="")
        if isinstance(text_value, (dict, list)):
            text_value = _scalar(text_value)
        text = html.unescape(str(text_value or "")).strip()
        if not text:
            return
        for normalized_key in _numeric_text_key_aliases(key):
            if normalized_key:
                result[normalized_key] = text

    def walk(node: Any, depth: int = 0) -> None:
        if depth > 5:
            return
        if isinstance(node, dict):
            explicit_key = _get(node, "Key", "key", "ID", "Id", "id", "Hash", "hash")
            explicit_text = _get(node, "Text", "text", "Value", "value", "Content", "content")
            if explicit_key not in (None, "") and explicit_text not in (None, ""):
                add(explicit_key, explicit_text)
            for key, value in node.items():
                if isinstance(value, str):
                    add(key, value)
                elif isinstance(value, dict):
                    if _get(value, "Key", "key", "ID", "Id", "id", "Hash", "hash") is not None:
                        add(_get(value, "Key", "key", "ID", "Id", "id", "Hash", "hash"), value)
                    walk(value, depth + 1)
                elif isinstance(value, list):
                    walk(value, depth + 1)
        elif isinstance(node, list):
            for row in node:
                if isinstance(row, (dict, list)):
                    walk(row, depth + 1)

    for payload in payloads:
        walk(payload)
    return result


def _normalize_gender_template_text(value: Any) -> str:
    """Convert Genshin gender branches into a stable user-facing form.

    The raw source value remains available in raw_json; this function only
    normalizes the display/comparison text. Both source orders are accepted.
    """
    text = html.unescape(str(value or ""))
    pair = re.compile(r"\{M#([^{}]*)\}\{F#([^{}]*)\}|\{F#([^{}]*)\}\{M#([^{}]*)\}")

    def replace_pair(match: re.Match[str]) -> str:
        male = (match.group(1) if match.group(1) is not None else match.group(4) or "").strip()
        female = (match.group(2) if match.group(2) is not None else match.group(3) or "").strip()
        if male and female and male != female:
            return f"{male}／{female}"
        return male or female

    previous = None
    while previous != text:
        previous = text
        text = pair.sub(replace_pair, text)
    text = re.sub(r"\{M#([^{}]*)\}", lambda m: m.group(1).strip(), text)
    text = re.sub(r"\{F#([^{}]*)\}", lambda m: m.group(1).strip(), text)
    return text.strip()


_NAMED_PARAM_RE = re.compile(r"\{param(?P<index>\d+)\}", flags=re.IGNORECASE)


def _clean_user_facing_source_text(value: Any) -> str:
    """Normalize display-only control syntax without altering raw source evidence."""
    text = _normalize_gender_template_text(value)
    # Genshin uses a leading # as a display-control marker on some texts.
    # A numeric marker such as #1 is not removed here.
    text = re.sub(r"^#+(?=[^0-9\s])", "", text).strip()
    return text


def _extract_named_template_params(row: Mapping[str, Any]) -> tuple[dict[int, Any], dict[str, Any]]:
    """Collect parameters from the same achievement row only.

    Explicit ParamList-like containers take priority, then indexed param fields,
    and finally Genshin's progress value may supply param0. No value is shared
    between achievements and no constant is hard-coded.
    """
    params: dict[int, Any] = {}
    sources: dict[str, Any] = {}
    for key in ("ParamList", "paramList", "AchievementParam", "achievementParam", "Params", "params"):
        if key in row:
            values = _extract_template_params(row.get(key))
            for index, value in enumerate(values):
                if value not in (None, ""):
                    params[index] = value
                    sources[str(index)] = key
            if values:
                break
    for key, value in row.items():
        match = re.fullmatch(r"(?:param|parameter)_?(\d+)", str(key), flags=re.IGNORECASE)
        if match and value not in (None, ""):
            index = int(match.group(1))
            params.setdefault(index, _scalar(value))
            sources.setdefault(str(index), str(key))
    if 0 not in params:
        progress_key = next((key for key in (
            "progress", "Progress", "progressValue", "ProgressValue",
            "targetNum", "TargetNum", "finishProgress", "FinishProgress"
        ) if key in row and _scalar(row.get(key)) not in (None, "")), "")
        if progress_key:
            params[0] = _scalar(row.get(progress_key))
            sources["0"] = progress_key
    return params, sources


def _substitute_named_source_template(text: str, row: Mapping[str, Any]) -> tuple[str, bool, dict[str, Any]]:
    source = _clean_user_facing_source_text(text)
    params, param_sources = _extract_named_template_params(row)
    unresolved: list[str] = []
    used: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        index = int(match.group("index"))
        if index not in params:
            unresolved.append(match.group(0))
            return match.group(0)
        value = _format_template_param(params[index])
        if value == "":
            unresolved.append(match.group(0))
            return match.group(0)
        used[str(index)] = value
        return value

    output = _NAMED_PARAM_RE.sub(replace, source)
    for match in _NAMED_PARAM_RE.finditer(output):
        unresolved.append(match.group(0))
    return output, not bool(unresolved), {
        "parameters": {str(index): _format_template_param(value) for index, value in sorted(params.items())},
        "parameter_sources": param_sources,
        "used": used,
        "unresolved": list(dict.fromkeys(unresolved)),
    }


def _resolved_text_is_valid(value: Any, *, resolved_from_textmap: bool, allow_numeric_title: bool = False) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if allow_numeric_title and resolved_from_textmap and re.fullmatch(r"\d+", text):
        return True
    return not _looks_like_unresolved_source_text(text)


def _resolve_text_with_status(value: Any, text_map: Mapping[str, str], *, fallback: str = "") -> tuple[str, bool]:
    if value is None:
        return fallback, False
    raw = _text_key(value)
    if not raw:
        return fallback, False
    for candidate in _numeric_text_key_aliases(raw):
        mapped = text_map.get(candidate)
        if mapped:
            return _normalize_gender_template_text(mapped), True
    # Literal text is accepted only when it is not an obvious source key/hash/code.
    code_like = bool(
        re.fullmatch(r"[-+]?\d+", raw)
        or re.fullmatch(r"(?:Achievement|ArcadeAchievement)[A-Za-z_]*_?\d+", raw, flags=re.IGNORECASE)
        or re.fullmatch(r"[A-Z0-9_]{10,}", raw)
    )
    return (fallback if code_like else _normalize_gender_template_text(raw)), not code_like


def _resolve_text(value: Any, text_map: Mapping[str, str], *, fallback: str = "") -> str:
    return _resolve_text_with_status(value, text_map, fallback=fallback)[0]


def _translation_coverage_error(
    *,
    source_name: str,
    source_rows: int,
    parsed_rows: int,
    unresolved_names: int,
    unresolved_conditions: int,
    unresolved_categories: int,
    minimum_name_ratio: float = 0.98,
    minimum_condition_ratio: float = 0.90,
    minimum_category_ratio: float = 0.90,
) -> None:
    denominator = max(1, parsed_rows)
    name_ratio = (parsed_rows - unresolved_names) / denominator
    condition_ratio = (parsed_rows - unresolved_conditions) / denominator
    category_ratio = (parsed_rows - unresolved_categories) / denominator
    if name_ratio < minimum_name_ratio or condition_ratio < minimum_condition_ratio or category_ratio < minimum_category_ratio:
        raise RepositorySourceError(
            f"{source_name} 的繁體中文文字對照不完整，為避免顯示代碼或 Hash，已停止更新。",
            code="traditional_chinese_mapping_incomplete",
            diagnostics={
                "source_rows": source_rows,
                "parsed_rows": parsed_rows,
                "unresolved_names": unresolved_names,
                "unresolved_conditions": unresolved_conditions,
                "unresolved_categories": unresolved_categories,
                "name_coverage": round(name_ratio, 4),
                "condition_coverage": round(condition_ratio, 4),
                "category_coverage": round(category_ratio, 4),
            },
        )

def _as_int(value: Any, default: int = 0) -> int:
    scalar = _scalar(value)
    if scalar in (None, ""):
        return default
    try:
        return int(float(str(scalar)))
    except (TypeError, ValueError):
        return default


def _as_bool(value: Any) -> bool:
    scalar = _scalar(value)
    if isinstance(scalar, bool):
        return scalar
    if isinstance(scalar, (int, float)):
        return scalar != 0
    return str(scalar or "").strip().casefold() in {"1", "true", "yes", "hidden", "hide"}


def _clean_markup(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    text = text.replace("\\n", "\n")
    return html.unescape(text).strip()


def _reward_value(reward_row: Any) -> int:
    if not isinstance(reward_row, dict):
        return 0
    direct = _get(reward_row, "Reward", "reward", "RewardValue", "rewardValue", "Num", "num", "Count", "count")
    if direct not in (None, ""):
        return _as_int(direct)
    item_list = _get(reward_row, "RewardItemList", "rewardItemList", "ItemList", "itemList", default=[])
    if isinstance(item_list, list):
        amounts = []
        for item in item_list:
            if isinstance(item, dict):
                amounts.append(_as_int(_get(
                    item,
                    "ItemNum", "itemNum", "ItemCount", "itemCount",
                    "Count", "count", "Num", "num", "Amount", "amount",
                )))
        return max(amounts or [0])
    return 0


def _normalize_compare_text(value: Any) -> str:
    text = _clean_markup(str(value or ""))
    text = re.sub(r"[\s\u3000]+", "", text)
    text = text.translate(str.maketrans({
        "，": ",", "。": ".", "：": ":", "；": ";", "！": "!", "？": "?",
        "（": "(", "）": ")", "【": "[", "】": "]", "「": '"', "」": '"',
        "『": '"', "』": '"', "·": "・", "—": "-", "–": "-",
    }))
    return text.casefold()


def _looks_like_unresolved_source_text(value: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    # Do not treat every literal ``#55`` as an unresolved parameter. HSR uses
    # number signs in names, colour tags and TEXTJOIN macros. Only markers that
    # are unambiguously machine formatting are rejected here. Bare indexed
    # markers are validated by _substitute_source_template with the actual
    # ParamList length.
    return bool(
        re.fullmatch(r"[-+]?\d+", text)
        or re.fullmatch(r"(?:[A-Z0-9]+_[A-Z0-9_]+|[A-Z0-9_]{16,})", text)
        or re.fullmatch(r"(?:Achievement|ArcadeAchievement|TextMap)[A-Za-z0-9_]*", text, flags=re.IGNORECASE)
        or re.search(r"#\d+\[[^\]]*\]", text)
        or re.search(r"\{\d+\}", text)
        or re.search(r"%(?:\d+\$)?[sdif]", text)
        or re.search(r"\{TEXTJOIN#\d+\}", text, flags=re.IGNORECASE)
        or _NAMED_PARAM_RE.search(text)
    )


def _scalar_column_stats(rows: Sequence[dict[str, Any]], key: str) -> dict[str, Any]:
    values: list[Any] = []
    numeric: list[int] = []
    for row in rows:
        if key not in row or isinstance(row[key], (dict, list, tuple)):
            continue
        value = _scalar(row[key])
        if value in (None, ""):
            continue
        values.append(value)
        try:
            numeric.append(int(float(str(value))))
        except (TypeError, ValueError):
            pass
    count = len(values)
    return {
        "count": count,
        "coverage": count / max(1, len(rows)),
        "unique_ratio": len({_text_key(value) for value in values}) / max(1, count),
        "numeric_ratio": len(numeric) / max(1, count),
        "minimum": min(numeric) if numeric else None,
        "maximum": max(numeric) if numeric else None,
        "median": sorted(numeric)[len(numeric) // 2] if numeric else None,
    }


def _infer_unique_numeric_key(
    rows: Sequence[dict[str, Any]],
    *,
    preferred_names: Sequence[str] = (),
    excluded: Sequence[str] = (),
    allow_small: bool = False,
) -> tuple[str, dict[str, Any]]:
    """Infer a stable ID column without trusting obfuscated field names.

    The selected field must be numeric, present on almost all rows, and almost
    unique.  Near ties are treated as ambiguous and stop the update rather than
    selecting a possibly unrelated reward/order column.
    """
    if not rows:
        return "", {"reason": "no_rows", "candidates": []}
    sample_keys = list(dict.fromkeys(str(key) for row in rows[:100] for key in row))
    lowered = {key.casefold(): key for key in sample_keys}
    for name in preferred_names:
        key = lowered.get(str(name).casefold())
        if key:
            stats = _scalar_column_stats(rows, key)
            if stats["coverage"] >= 0.80 and stats["numeric_ratio"] >= 0.95 and stats["unique_ratio"] >= 0.95:
                return key, {"method": "semantic", "selected": key, "stats": stats}

    excluded_set = {str(key) for key in excluded if str(key)}
    candidates: list[dict[str, Any]] = []
    for key in sample_keys:
        if key in excluded_set:
            continue
        stats = _scalar_column_stats(rows, key)
        if stats["coverage"] < 0.80 or stats["numeric_ratio"] < 0.95 or stats["unique_ratio"] < 0.95:
            continue
        median = int(stats["median"] or 0)
        maximum = int(stats["maximum"] or 0)
        if not allow_small and median < 1000:
            continue
        if maximum <= 1:
            continue
        score = stats["coverage"] * 5 + stats["unique_ratio"] * 6
        if 1_000 <= median <= 99_999_999:
            score += 1.5
        if re.search(r"(?:^|_)(?:id|achievement)", key, flags=re.IGNORECASE):
            score += 3
        candidates.append({"key": key, "score": round(score, 4), "stats": stats})
    candidates.sort(key=lambda item: (float(item["score"]), float(item["stats"]["unique_ratio"])), reverse=True)
    if not candidates:
        return "", {"reason": "no_safe_candidate", "candidates": []}
    if len(candidates) > 1 and float(candidates[0]["score"]) - float(candidates[1]["score"]) < 0.35:
        return "", {"reason": "ambiguous", "candidates": candidates[:10]}
    return str(candidates[0]["key"]), {"method": "structure", "selected": candidates[0]["key"], "candidates": candidates[:10]}


def _mapped_text_column_stats(rows: Sequence[dict[str, Any]], key: str, text_map: Mapping[str, str]) -> dict[str, Any]:
    observed = 0
    resolved: list[str] = []
    for row in rows:
        if key not in row or isinstance(row[key], (dict, list, tuple)):
            continue
        value = row[key]
        if isinstance(value, bool) or _text_key(value) == "":
            continue
        observed += 1
        text, ok = _resolve_text_with_status(value, text_map)
        inference_text = _NAMED_PARAM_RE.sub("1", text)
        if ok and text and not _looks_like_unresolved_source_text(inference_text):
            resolved.append(text)
    lengths = [len(value) for value in resolved]
    return {
        "observed": observed,
        "coverage": observed / max(1, len(rows)),
        "resolved": len(resolved),
        "resolved_ratio": len(resolved) / max(1, observed),
        "average_length": round(sum(lengths) / max(1, len(lengths)), 3),
        "unique_ratio": len(set(resolved)) / max(1, len(resolved)),
    }


def _infer_text_key(
    rows: Sequence[dict[str, Any]],
    text_map: Mapping[str, str],
    *,
    role: str,
    preferred_names: Sequence[str] = (),
    excluded: Sequence[str] = (),
) -> tuple[str, dict[str, Any]]:
    if not rows:
        return "", {"reason": "no_rows", "candidates": []}
    sample_keys = list(dict.fromkeys(str(key) for row in rows[:100] for key in row))
    lowered = {key.casefold(): key for key in sample_keys}
    for name in preferred_names:
        key = lowered.get(str(name).casefold())
        if not key:
            continue
        stats = _mapped_text_column_stats(rows, key, text_map)
        # Since Genshin 5.5+, formerly semantic field names may remain populated
        # while their values no longer point at the active TextMap entries. A
        # populated column is therefore not enough: require high translation
        # coverage before accepting it, otherwise continue structural inference.
        if stats["coverage"] >= 0.50 and stats["resolved_ratio"] >= 0.75 and stats["unique_ratio"] >= 0.20:
            return key, {"method": "semantic_verified", "selected": key, "stats": stats}

    excluded_set = {str(key) for key in excluded if str(key)}
    candidates: list[dict[str, Any]] = []
    for key in sample_keys:
        if key in excluded_set:
            continue
        stats = _mapped_text_column_stats(rows, key, text_map)
        if stats["coverage"] < 0.50 or stats["resolved_ratio"] < 0.75 or stats["unique_ratio"] < 0.20:
            continue
        avg = float(stats["average_length"])
        score = stats["coverage"] * 4 + stats["resolved_ratio"] * 6 + min(1.5, stats["unique_ratio"])
        if role in {"name", "category"}:
            if 1 <= avg <= 42:
                score += 2.5
            if role == "name" and 2 <= avg <= 28:
                score += 1
        elif role == "description":
            if avg >= 8:
                score += min(4.0, avg / 20)
            else:
                score -= 2
        candidates.append({"key": key, "score": round(score, 4), "stats": stats})
    candidates.sort(key=lambda item: (float(item["score"]), float(item["stats"]["resolved_ratio"])), reverse=True)
    if not candidates:
        return "", {"reason": "no_safe_candidate", "candidates": []}
    return str(candidates[0]["key"]), {"method": "textmap_structure", "selected": candidates[0]["key"], "candidates": candidates[:10]}



def _extract_template_params(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, dict):
        for key in ("ParamList", "paramList", "Params", "params", "Values", "values"):
            if key in value:
                return _extract_template_params(value[key])
        scalar = _scalar(value)
        return [] if scalar in (None, "") else [scalar]
    if isinstance(value, (list, tuple)):
        result: list[Any] = []
        for item in value:
            if isinstance(item, dict):
                scalar = _get(item, "Value", "value", "Param", "param", "Num", "num", "Count", "count")
                if scalar in (None, ""):
                    scalar = _scalar(item)
                if scalar not in (None, ""):
                    result.append(scalar)
            else:
                result.append(item)
        return result
    return [value]


def _format_template_param(value: Any) -> str:
    scalar = _scalar(value)
    if scalar is None:
        return ""
    if isinstance(scalar, float):
        return str(int(scalar)) if scalar.is_integer() else (f"{scalar:.6f}".rstrip("0").rstrip("."))
    text = str(scalar).strip()
    try:
        number = float(text)
        return str(int(number)) if number.is_integer() else (f"{number:.6f}".rstrip("0").rstrip("."))
    except (TypeError, ValueError):
        return text


_TEMPLATE_MARKER_RE = re.compile(
    r"#(?P<one>\d+)(?:\[(?P<format>[^\]]*)\])?|\{(?P<zero>\d+)\}|%(?:\d+\$)?[sdif]"
)
_TEXTJOIN_RE = re.compile(r"\{TEXTJOIN#(?P<id>\d+)\}", flags=re.IGNORECASE)


def _format_template_param_with_spec(value: Any, spec: str, *, followed_by_percent: bool = False) -> str:
    scalar = _scalar(value)
    if scalar is None:
        return ""
    try:
        number = float(str(scalar).strip())
    except (TypeError, ValueError):
        return _format_template_param(scalar)
    normalized = str(spec or "").strip().casefold()
    if normalized == "m":
        number *= 100
    if followed_by_percent and abs(number) <= 1:
        number *= 100
    if normalized in {"i", "d", "m"} or number.is_integer():
        return str(int(round(number)))
    precision_match = re.fullmatch(r"f(\d+)", normalized)
    if precision_match:
        precision = max(0, min(8, int(precision_match.group(1))))
        return f"{number:.{precision}f}".rstrip("0").rstrip(".")
    return f"{number:.6f}".rstrip("0").rstrip(".")


def _substitute_source_template(text: str, params: Sequence[Any]) -> tuple[str, bool]:
    # Remove markup first so colour values such as <color=#8790abff> can never
    # be interpreted as achievement parameters.
    source = _clean_markup(str(text or ""))
    raw_values = list(params)
    sequential_index = 0
    unresolved: list[str] = []

    def replace(match: re.Match[str]) -> str:
        nonlocal sequential_index
        # TEXTJOIN macros contain a literal #number and are not ParamList slots.
        prefix = source[max(0, match.start() - 10):match.start()].casefold()
        if prefix.endswith("textjoin"):
            return match.group(0)
        one_based = match.group("one")
        zero_based = match.group("zero")
        if one_based is not None:
            index = int(one_based) - 1
        elif zero_based is not None:
            index = int(zero_based)
        else:
            index = sequential_index
            sequential_index += 1
        if not (0 <= index < len(raw_values)):
            # A bracketed marker is always formatting. A bare #55 outside the
            # available ParamList can be legitimate title text and is preserved.
            if match.group("format") is not None or one_based is None:
                unresolved.append(match.group(0))
            return match.group(0)
        followed_by_percent = match.end() < len(source) and source[match.end()] == "%"
        value = _format_template_param_with_spec(
            raw_values[index], match.group("format") or "", followed_by_percent=followed_by_percent
        )
        if value == "":
            unresolved.append(match.group(0))
            return match.group(0)
        return value

    output = _TEMPLATE_MARKER_RE.sub(replace, source)
    # Check only actionable markers. Literal unmatched #numbers and TEXTJOIN are
    # handled separately instead of aborting the entire game catalogue.
    for match in _TEMPLATE_MARKER_RE.finditer(output):
        prefix = output[max(0, match.start() - 10):match.start()].casefold()
        if prefix.endswith("textjoin"):
            continue
        one = match.group("one")
        if one is not None and match.group("format") is None and int(one) > len(raw_values):
            continue
        unresolved.append(match.group(0))
    return output, not bool(unresolved)


def _infer_nested_reward_fields(
    rows: Sequence[dict[str, Any]],
    *,
    id_key: str,
    reference_ids: set[str],
) -> tuple[str, str, dict[str, Any]]:
    relevant = [
        row for row in rows
        if not reference_ids or _text_key(row.get(id_key)) in reference_ids
    ]
    candidates: list[dict[str, Any]] = []
    for list_key in dict.fromkeys(
        str(key)
        for row in relevant[:500]
        for key, value in row.items()
        if isinstance(value, list) and any(isinstance(item, dict) for item in value)
    ):
        items = [
            item
            for row in relevant
            for item in (row.get(list_key) or [])
            if isinstance(item, dict)
        ]
        if not items:
            continue
        item_keys = list(dict.fromkeys(str(key) for item in items[:500] for key in item))
        for value_key in item_keys:
            numeric: list[int] = []
            for item in items:
                if value_key not in item or isinstance(item[value_key], (dict, list, tuple, bool)):
                    continue
                try:
                    numeric.append(int(float(str(item[value_key]))))
                except (TypeError, ValueError):
                    continue
            if len(numeric) < max(1, int(len(items) * 0.80)):
                continue
            positive = [value for value in numeric if value > 0]
            if len(positive) < max(1, int(len(numeric) * 0.80)):
                continue
            distinct = len(set(positive))
            median = sorted(positive)[len(positive) // 2]
            maximum = max(positive)
            score = len(numeric) / max(1, len(items)) * 5
            score += len(positive) / max(1, len(numeric)) * 3
            if distinct > 1:
                score += 3
            if maximum <= 1000:
                score += 2
            if median <= 100:
                score += 2
            if re.search(r"(?:count|num|amount|quantity|value)", value_key, flags=re.I):
                score += 3
            candidates.append({
                "list_key": list_key,
                "value_key": value_key,
                "score": round(score, 4),
                "coverage": round(len(numeric) / max(1, len(items)), 4),
                "positive_ratio": round(len(positive) / max(1, len(numeric)), 4),
                "distinct": distinct,
                "minimum": min(positive),
                "maximum": maximum,
                "median": median,
                "item_count": len(items),
            })
    candidates.sort(
        key=lambda item: (float(item["score"]), int(item["distinct"]), -int(item["maximum"])),
        reverse=True,
    )
    if not candidates:
        return "", "", {"status": "not_found", "candidates": []}
    best = candidates[0]
    if len(candidates) > 1 and float(best["score"]) - float(candidates[1]["score"]) < 1:
        return "", "", {"status": "ambiguous", "candidates": candidates[:10]}
    return str(best["list_key"]), str(best["value_key"]), {
        "status": "ok",
        "selected": {"list_key": best["list_key"], "value_key": best["value_key"]},
        "candidates": candidates[:10],
    }


def _nested_reward_value(reward_row: Mapping[str, Any], list_key: str, value_key: str) -> int:
    item_list = reward_row.get(list_key) if list_key else None
    if not isinstance(item_list, list):
        return 0
    amounts = [
        _as_int(item.get(value_key))
        for item in item_list
        if isinstance(item, dict) and value_key in item
    ]
    return max(amounts or [0])


def _build_reward_map(rows: Sequence[dict[str, Any]], *, reference_ids: set[str] | None = None) -> tuple[dict[str, int], dict[str, Any]]:
    if not rows:
        return {}, {"rows": 0, "resolved": 0, "id_key": "", "value_key": ""}
    reference_ids = {_text_key(value) for value in (reference_ids or set()) if _text_key(value)}
    id_key = ""
    id_diagnostics: dict[str, Any] = {}
    if reference_ids:
        id_key, matches, scores = _infer_reference_key(rows, reference_ids)
        id_diagnostics = {"method": "reference", "matches": matches, "scores": scores}
    if not id_key:
        id_key, id_diagnostics = _infer_unique_numeric_key(
            rows,
            preferred_names=("RewardID", "RewardId", "rewardId", "ID", "Id", "id", "OnceRewardId"),
            allow_small=True,
        )
    nested_list_key, nested_value_key, nested_diagnostics = _infer_nested_reward_fields(
        rows,
        id_key=id_key,
        reference_ids=reference_ids,
    ) if id_key else ("", "", {"status": "skipped", "reason": "reward_id_key_unresolved"})
    result: dict[str, int] = {}
    direct_count = 0
    nested_count = 0
    for row in rows:
        reward_id = _text_key(row.get(id_key)) if id_key else _text_key(_get(row, "RewardID", "RewardId", "rewardId", "ID", "Id", "id"))
        if not reward_id:
            continue
        value = _reward_value(row)
        if value <= 0 and nested_list_key and nested_value_key:
            value = _nested_reward_value(row, nested_list_key, nested_value_key)
            if value > 0:
                nested_count += 1
        if value > 0:
            result[reward_id] = value
            direct_count += 1
    return result, {
        "rows": len(rows),
        "resolved": len(result),
        "id_key": id_key,
        "id_diagnostics": id_diagnostics,
        "direct_count": direct_count - nested_count,
        "nested_count": nested_count,
        "nested_diagnostics": nested_diagnostics,
    }


def _normalized_row(
    *,
    game_id: str,
    achievement_id: Any,
    name: str,
    condition: str,
    category: str,
    source_order: int,
    source_id: str,
    version: str = "版本待確認",
    reward: int = 0,
    hidden: bool = False,
    tags: Sequence[str] = (),
    category_id: Any = "",
    group_id: Any = "",
    group_name: str = "",
    progress_value: int = 0,
    level: int = 0,
    next_link: Any = "",
    reward_id: Any = "",
    raw: Mapping[str, Any] | None = None,
    provenance: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    achievement_key = _text_key(achievement_id)
    return {
        "achievement_id": achievement_key,
        "name": _clean_markup(name),
        "condition": _clean_markup(condition),
        "version": str(version or "版本待確認").strip(),
        "category": _clean_markup(category) or "未辨識分類",
        "reward": int(reward or 0),
        "hidden": 1 if hidden else 0,
        "tags_json": json.dumps([str(tag) for tag in tags if str(tag).strip()], ensure_ascii=False),
        "source": source_id,
        "source_order": int(source_order),
        "category_id": _text_key(category_id),
        "group_id": _text_key(group_id),
        "group_name": _clean_markup(group_name),
        "progress_value": int(progress_value or 0),
        "level": int(level or 0),
        "next_link": _text_key(next_link),
        "reward_id": _text_key(reward_id),
        "primary_source_id": source_id,
        "secondary_source_id": "",
        "raw_json": json.dumps(dict(raw or {}), ensure_ascii=False, separators=(",", ":"), default=str),
        "provenance_json": json.dumps(dict(provenance or {}), ensure_ascii=False, separators=(",", ":"), default=str),
    }


def parse_wuwa_bundle(files: Mapping[str, Any]) -> ParsedCatalog:
    achievements = _unwrap_rows(files.get("achievements"))
    groups = _unwrap_rows(files.get("groups"))
    categories = _unwrap_rows(files.get("categories"))
    text_map = _build_text_map(files.get("textmap"))
    if not achievements or not groups or not categories or not text_map:
        raise RepositorySourceError(
            "WW_Data 的成就、成就集、分類或繁體中文文字表結構不完整，已停止更新。",
            code="source_structure_changed",
            diagnostics={"achievements": len(achievements), "groups": len(groups), "categories": len(categories), "text_count": len(text_map)},
        )
    category_by_id: dict[str, str] = {}
    for row in categories:
        category_id = _text_key(_get(row, "Id", "ID", "id"))
        category_by_id[category_id] = _resolve_text(_get(row, "Name", "name"), text_map, fallback=f"分類 {category_id}")
    group_by_id: dict[str, dict[str, Any]] = {}
    for row in groups:
        group_id = _text_key(_get(row, "Id", "ID", "id"))
        group_by_id[group_id] = row
    reward_by_level = {1: 5, 2: 10, 3: 20}
    rows: list[dict[str, Any]] = []
    skipped = 0
    unresolved_rewards = 0
    for index, row in enumerate(achievements):
        achievement_id = _text_key(_get(row, "Id", "ID", "id"))
        group_id = _text_key(_get(row, "GroupId", "GroupID", "groupId", "group_id"))
        group = group_by_id.get(group_id, {})
        name = _resolve_text(_get(row, "Name", "name"), text_map)
        if not achievement_id or not name:
            skipped += 1
            continue
        parent_category_id = _text_key(_get(group, "Category", "category", "CategoryId", "categoryId"))
        group_name = _resolve_text(_get(group, "Name", "name"), text_map, fallback=f"成就集 {group_id}")
        parent_category_name = category_by_id.get(parent_category_id, "未辨識上層分類")
        level = _as_int(_get(row, "Level", "level"))
        reward = int(reward_by_level.get(level) or 0)
        if reward <= 0:
            unresolved_rewards += 1
        raw_with_context = dict(row)
        raw_with_context["_tracker_group_context"] = {
            "group_id": group_id,
            "group_name": group_name,
            "parent_category_id": parent_category_id,
            "parent_category_name": parent_category_name,
            "completion_drop_id": _text_key(_get(group, "DropId", "dropId")),
        }
        raw_with_context["_tracker_reward_resolution"] = {
            "rule": "achievement_level",
            "level": level,
            "reward": reward,
        }
        rows.append(_normalized_row(
            game_id="wuwa",
            achievement_id=achievement_id,
            name=name,
            condition=_resolve_text(_get(row, "Desc", "Description", "desc", "description"), text_map),
            # Tracker category means the user-facing achievement set.  WW_Data's
            # achievementcategory table is a parent navigation layer and must not
            # replace the actual achievement-group name.
            category=group_name,
            source_order=_as_int(_get(group, "Sort", "sort"), index) * 10000 + _as_int(_get(row, "Level", "level"), index),
            source_id="ww_data",
            reward=reward,
            hidden=_as_bool(_get(row, "Hidden", "hidden")),
            category_id=group_id,
            group_id=group_id,
            group_name=group_name,
            progress_value=_as_int(_get(row, "Progress", "progress", "TargetNum", "targetNum")),
            level=level,
            next_link=_get(row, "NextLink", "nextLink"),
            reward_id="",
            raw=raw_with_context,
            provenance={
                "id": "primary",
                "name": "primary_textmap_zh_hant",
                "condition": "primary_textmap_zh_hant",
                "category": "primary_achievement_group",
                "parent_category": "primary_navigation_category",
                "reward": "primary_achievement_level" if reward else "verified_catalog_snapshot_required",
                "nextLink": "primary",
                "version": "repository_history_or_verified_catalog_snapshot",
            },
        ))
    if skipped and len(rows) < max(1, len(achievements) // 2):
        raise RepositorySourceError(
            "WW_Data 成就欄位結構可能已變更，已停止更新。",
            code="source_structure_changed",
            diagnostics={"source_rows": len(achievements), "parsed_rows": len(rows), "skipped_rows": skipped},
        )
    return ParsedCatalog(rows, {
        "achievement_rows": len(achievements), "parsed_rows": len(rows), "skipped_rows": skipped,
        "group_count": len(groups), "parent_category_count": len(categories), "text_count": len(text_map),
        "category_policy": "achievement_group_name",
        "reward_rule": "achievement_level_1_2_3_to_5_10_20",
        "unresolved_reward_references": unresolved_rewards,
    })


def parse_genshin_bundle(files: Mapping[str, Any]) -> ParsedCatalog:
    all_achievements = _unwrap_rows(files.get("achievements"))
    achievements = [row for row in all_achievements if not _as_bool(_get(row, "isDisuse", "IsDisuse", "disused", "Disused"))]
    disused_rows = len(all_achievements) - len(achievements)
    goals = _unwrap_rows(files.get("groups"))
    rewards = _unwrap_rows(files.get("rewards"))
    text_map = _build_text_map(files.get("textmap"))
    if not achievements or not goals or not text_map:
        raise RepositorySourceError(
            "AnimeGameData2 的必要成就資料結構不完整，已停止更新。",
            code="source_structure_changed",
            diagnostics={"achievements": len(achievements), "groups": len(goals), "text_count": len(text_map)},
        )

    goal_name_preferred = ("nameTextMapHash", "NameTextMapHash", "name", "Name")
    goal_name_key, goal_name_diag = _infer_text_key(
        goals, text_map, role="category", preferred_names=goal_name_preferred,
    )
    if not goal_name_key:
        raise RepositorySourceError(
            "AnimeGameData2 無法由繁體中文文字表安全辨識成就集名稱欄位，已停止更新。",
            code="traditional_chinese_mapping_incomplete",
            diagnostics={"goal_rows": len(goals), "text_count": len(text_map), "goal_name_inference": goal_name_diag},
        )
    goal_id_key, goal_id_diag = _infer_unique_numeric_key(
        goals, preferred_names=("id", "Id", "goalId", "GoalId"), excluded=(goal_name_key,), allow_small=True,
    )
    if not goal_id_key:
        raise RepositorySourceError(
            "AnimeGameData2 無法安全辨識成就集 ID，已停止更新。",
            code="source_structure_changed",
            diagnostics={"goal_rows": len(goals), "goal_id_inference": goal_id_diag},
        )

    goal_names: dict[str, tuple[str, bool]] = {}
    unresolved_goal_samples: list[dict[str, Any]] = []
    for row in goals:
        goal_id_value = row.get(goal_id_key)
        if goal_id_key in {"id", "Id", "goalId", "GoalId"} and goal_id_key not in row:
            goal_id_value = 0
        goal_id = _text_key(goal_id_value)
        if not goal_id:
            continue
        value = row.get(goal_name_key) if goal_name_key else None
        name, ok = _resolve_text_with_status(value, text_map)
        if not ok or _looks_like_unresolved_source_text(name):
            name = ""
            if len(unresolved_goal_samples) < 20:
                unresolved_goal_samples.append({"goal_id": goal_id, "raw_value": _text_key(value), "field": goal_name_key})
        goal_names[goal_id] = (name, bool(name))

    name_preferred = ("titleTextMapHash", "TitleTextMapHash", "title", "Title", "nameTextMapHash", "NameTextMapHash")
    desc_preferred = ("descTextMapHash", "DescTextMapHash", "descriptionTextMapHash", "DescriptionTextMapHash", "description", "Description")
    name_key, name_diag = _infer_text_key(achievements, text_map, role="name", preferred_names=name_preferred)
    if not name_key:
        raise RepositorySourceError(
            "AnimeGameData2 無法由繁體中文文字表安全辨識成就名稱欄位，已停止更新。",
            code="traditional_chinese_mapping_incomplete",
            diagnostics={"achievement_rows": len(achievements), "text_count": len(text_map), "name_inference": name_diag},
        )
    description_key, description_diag = _infer_text_key(
        achievements, text_map, role="description", preferred_names=desc_preferred, excluded=(name_key,),
    )
    if not description_key:
        raise RepositorySourceError(
            "AnimeGameData2 無法由繁體中文文字表安全辨識成就說明欄位，已停止更新。",
            code="traditional_chinese_mapping_incomplete",
            diagnostics={"achievement_rows": len(achievements), "text_count": len(text_map), "description_inference": description_diag},
        )

    goal_ids = set(goal_names)
    explicit_group_key = next((key for key in ("goalId", "GoalId", "achievementGoalId", "AchievementGoalId") if any(key in row for row in achievements[:100])), "")
    if explicit_group_key:
        group_ref_key = explicit_group_key
        group_ref_diag: dict[str, Any] = {"method": "semantic", "selected": explicit_group_key}
    else:
        group_ref_key, group_matches, group_scores = _infer_reference_key(
            achievements, goal_ids, excluded=(name_key, description_key),
        )
        group_ref_diag = {"method": "reference", "selected": group_ref_key, "matches": group_matches, "scores": group_scores}

    achievement_id_key, achievement_id_diag = _infer_unique_numeric_key(
        achievements, preferred_names=("id", "Id", "achievementId", "AchievementId"),
        excluded=(name_key, description_key, group_ref_key), allow_small=False,
    )
    if not achievement_id_key or not group_ref_key:
        raise RepositorySourceError(
            "AnimeGameData2 無法安全辨識官方 ID 或成就集關聯，已停止更新。",
            code="source_structure_changed",
            diagnostics={
                "source_rows": len(achievements),
                "detected_fields": {"achievement_id": achievement_id_key, "goal_reference": group_ref_key},
                "inference": {"achievement_id": achievement_id_diag, "goal_reference": group_ref_diag},
            },
        )

    achievement_ids = {
        _text_key(row.get(achievement_id_key))
        for row in achievements
        if _text_key(row.get(achievement_id_key))
    }
    predecessor_by_id: dict[str, str] = {}
    next_by_id: dict[str, str] = {}
    ambiguous_predecessors: set[str] = set()
    for row in achievements:
        achievement_id = _text_key(row.get(achievement_id_key))
        predecessor_id = _text_key(_get(
            row,
            "preStageAchievementId", "PreStageAchievementId",
            "preAchievementId", "PreAchievementId",
        ))
        if not achievement_id or predecessor_id not in achievement_ids:
            continue
        predecessor_by_id[achievement_id] = predecessor_id
        if predecessor_id in next_by_id and next_by_id[predecessor_id] != achievement_id:
            ambiguous_predecessors.add(predecessor_id)
            next_by_id.pop(predecessor_id, None)
        elif predecessor_id not in ambiguous_predecessors:
            next_by_id[predecessor_id] = achievement_id

    def achievement_level(achievement_id: str) -> int:
        level = 1
        current = achievement_id
        visited = {achievement_id}
        while current in predecessor_by_id:
            current = predecessor_by_id[current]
            if current in visited:
                return 1
            visited.add(current)
            level += 1
        return level

    reward_map, reward_diagnostics = _build_reward_map(rewards)
    reward_ids = set(reward_map)
    explicit_reward_key = next((key for key in ("finishRewardId", "FinishRewardId", "rewardId", "RewardId") if any(key in row for row in achievements[:100])), "")
    reward_ref_key = explicit_reward_key
    reward_ref_diag: dict[str, Any] = {"method": "semantic", "selected": explicit_reward_key} if explicit_reward_key else {}
    if not reward_ref_key and reward_ids:
        reward_ref_key, reward_matches, reward_scores = _infer_reference_key(
            achievements, reward_ids, excluded=(achievement_id_key, name_key, description_key, group_ref_key),
        )
        reward_ref_diag = {"method": "reference", "selected": reward_ref_key, "matches": reward_matches, "scores": reward_scores}

    rows: list[dict[str, Any]] = []
    missing_id = 0
    unresolved_names = 0
    unresolved_conditions = 0
    unresolved_categories = 0
    unresolved_rewards = 0
    unresolved_templates = 0
    resolved_templates = 0
    unresolved_template_samples: list[dict[str, Any]] = []
    unresolved_samples: list[dict[str, Any]] = []
    for index, row in enumerate(achievements):
        achievement_id = _text_key(row.get(achievement_id_key))
        if not achievement_id:
            missing_id += 1
            continue
        goal_id_value = row.get(group_ref_key)
        if group_ref_key in {"goalId", "GoalId", "achievementGoalId", "AchievementGoalId"} and group_ref_key not in row:
            goal_id_value = 0
        goal_id = _text_key(goal_id_value)
        name_value = row.get(name_key) if name_key else None
        desc_value = row.get(description_key) if description_key else None
        name_template, name_ok = _resolve_text_with_status(name_value, text_map)
        condition_template, condition_ok = _resolve_text_with_status(desc_value, text_map)
        name, name_template_ok, name_template_diag = _substitute_named_source_template(name_template, row)
        condition, condition_template_ok, condition_template_diag = _substitute_named_source_template(condition_template, row)
        had_named_template = bool(_NAMED_PARAM_RE.search(name_template) or _NAMED_PARAM_RE.search(condition_template))
        if had_named_template and name_template_ok and condition_template_ok:
            resolved_templates += 1
        if not name_template_ok or not condition_template_ok:
            unresolved_templates += 1
            if len(unresolved_template_samples) < 50:
                unresolved_template_samples.append({
                    "achievement_id": achievement_id,
                    "name_template": name_template, "condition_template": condition_template,
                    "name_resolution": name_template_diag, "condition_resolution": condition_template_diag,
                })
        if not name_ok or not name_template_ok or _looks_like_unresolved_source_text(name):
            unresolved_names += 1
            name = ""
        if not condition_ok or not condition_template_ok or _looks_like_unresolved_source_text(condition):
            unresolved_conditions += 1
            condition = ""
        category, category_ok = goal_names.get(goal_id, ("", False))
        if not category_ok or _looks_like_unresolved_source_text(category):
            unresolved_categories += 1
            category = "未辨識分類"
        if (not name or not condition or category == "未辨識分類") and len(unresolved_samples) < 50:
            unresolved_samples.append({
                "achievement_id": achievement_id, "goal_id": goal_id,
                "name_field": name_key, "name_raw": _text_key(name_value),
                "description_field": description_key, "description_raw": _text_key(desc_value),
            })
        reward_id = row.get(reward_ref_key) if reward_ref_key else _get(row, "finishRewardId", "FinishRewardId", "rewardId", "RewardId")
        reward = int(reward_map.get(_text_key(reward_id)) or 0)
        if _text_key(reward_id) not in {"", "0", "-1"} and reward <= 0:
            unresolved_rewards += 1
        raw_with_mapping = dict(row)
        raw_with_mapping["_tracker_detected_fields"] = {
            "achievement_id": achievement_id_key, "name": name_key, "description": description_key,
            "goal_reference": group_ref_key, "reward_reference": reward_ref_key,
        }
        raw_with_mapping["_tracker_text_resolution"] = {
            "name_template": name_template, "condition_template": condition_template,
            "name_resolved": bool(name), "condition_resolved": bool(condition),
            "category_resolved": category != "未辨識分類",
            "name_parameter_resolution": name_template_diag,
            "condition_parameter_resolution": condition_template_diag,
        }
        rows.append(_normalized_row(
            game_id="genshin", achievement_id=achievement_id, name=name, condition=condition, category=category,
            source_order=_as_int(_get(row, "orderId", "OrderId", "priority", "Priority"), index),
            source_id="anime_game_data", reward=reward,
            hidden=(str(_scalar(_get(row, "isShow", "IsShow")) or "").strip().upper() == "SHOWTYPE_HIDE")
            if _get(row, "isShow", "IsShow") not in (None, "")
            else _as_bool(_get(row, "isHidden", "IsHidden", "hidden", "Hidden")),
            category_id=goal_id, group_id=goal_id, group_name=category if category != "未辨識分類" else "",
            progress_value=_as_int(_get(row, "progress", "Progress", "progressValue", "ProgressValue"), 1),
            level=_as_int(_get(row, "stage", "Stage", "level", "Level"), achievement_level(achievement_id)),
            next_link=_get(
                row,
                "nextAchievementId", "NextAchievementId", "nextId", "NextId",
                default=next_by_id.get(achievement_id, ""),
            ),
            reward_id=reward_id, raw=raw_with_mapping,
            provenance={
                "id": "primary_detected",
                "name": "primary_textmap_cht" if name else "snapshot_preservation_required",
                "condition": "primary_textmap_cht" if condition else "snapshot_preservation_required",
                "category": "primary_textmap_cht" if category != "未辨識分類" else "snapshot_preservation_required",
                "reward": "primary" if reward else "verified_catalog_snapshot_required",
                "hidden": "primary_isShow_enum",
                "version": "repository_history_or_verified_catalog_snapshot",
            },
        ))
    if len(rows) < max(1, len(achievements) // 2):
        raise RepositorySourceError(
            "AnimeGameData2 無法安全辨識足夠的官方成就 ID，已停止更新。",
            code="source_structure_changed",
            diagnostics={"source_rows": len(achievements), "parsed_rows": len(rows), "missing_id": missing_id},
        )
    _translation_coverage_error(
        source_name="AnimeGameData2",
        source_rows=len(achievements),
        parsed_rows=len(rows),
        unresolved_names=unresolved_names,
        unresolved_conditions=unresolved_conditions,
        unresolved_categories=unresolved_categories,
        minimum_name_ratio=0.995,
        minimum_condition_ratio=0.98,
        minimum_category_ratio=0.995,
    )
    return ParsedCatalog(rows, {
        "achievement_rows_total": len(all_achievements), "achievement_rows": len(achievements),
        "disused_rows": disused_rows, "parsed_rows": len(rows), "skipped_rows": missing_id,
        "group_count": len(goals), "reward_count": len(rewards), "text_count": len(text_map),
        "translation_state": "partial_preserve_verified_snapshot" if unresolved_names or unresolved_conditions or unresolved_categories else "complete",
        "unresolved_names": unresolved_names, "unresolved_conditions": unresolved_conditions,
        "unresolved_categories": unresolved_categories, "unresolved_reward_references": unresolved_rewards,
        "resolved_named_template_count": resolved_templates,
        "unresolved_named_template_count": unresolved_templates,
        "unresolved_named_template_samples": unresolved_template_samples,
        "unresolved_samples": unresolved_samples, "unresolved_goal_samples": unresolved_goal_samples,
        "stage_link_count": len(next_by_id),
        "ambiguous_stage_predecessor_count": len(ambiguous_predecessors),
        "hash_alias_mode": "signed_unsigned_32bit",
        "detected_fields": {
            "achievement_id": achievement_id_key, "name": name_key, "description": description_key,
            "goal_reference": group_ref_key, "goal_id": goal_id_key, "goal_name": goal_name_key,
            "reward_reference": reward_ref_key,
        },
        "field_inference": {
            "achievement_id": achievement_id_diag, "name": name_diag, "description": description_diag,
            "goal_reference": group_ref_diag, "goal_id": goal_id_diag, "goal_name": goal_name_diag,
            "reward_reference": reward_ref_diag, "reward_table": reward_diagnostics,
        },
    })

def _normalized_show_type(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(_scalar(value) or "").casefold())


def _build_hsr_textjoin_map(
    config_rows: Sequence[dict[str, Any]],
    item_rows: Sequence[dict[str, Any]],
    text_map: Mapping[str, str],
) -> tuple[dict[str, str], dict[str, Any]]:
    item_text: dict[str, str] = {}
    unresolved_items = 0
    for row in item_rows:
        item_id = _text_key(_get(row, "TextJoinItemID", "TextJoinItemId", "textJoinItemId", "ID", "id"))
        text, ok = _resolve_text_with_status(_get(row, "TextJoinText", "textJoinText", "Text", "text"), text_map)
        if not item_id:
            continue
        if ok and text and not _looks_like_unresolved_source_text(text):
            item_text[item_id] = text
        else:
            unresolved_items += 1

    result: dict[str, str] = {}
    unresolved_defaults = 0
    for row in config_rows:
        join_id = _text_key(_get(row, "TextJoinID", "TextJoinId", "textJoinId", "ID", "id"))
        default_item = _text_key(_get(row, "DefaultItem", "defaultItem"))
        if not join_id:
            continue
        default_text = item_text.get(default_item, "")
        if default_text:
            result[join_id] = default_text
        else:
            unresolved_defaults += 1
    return result, {
        "config_rows": len(config_rows),
        "item_rows": len(item_rows),
        "resolved_defaults": len(result),
        "unresolved_items": unresolved_items,
        "unresolved_defaults": unresolved_defaults,
        "rule": "TextJoinConfig.DefaultItem_to_TextJoinItem.TextJoinText",
    }


def _resolve_hsr_textjoin_template(text: str, textjoin_map: Mapping[str, str]) -> tuple[str, bool, dict[str, Any]]:
    source = str(text or "")
    requested_ids: list[str] = []
    unresolved_ids: list[str] = []

    def replace(match: re.Match[str]) -> str:
        join_id = str(match.group("id") or "")
        requested_ids.append(join_id)
        value = str(textjoin_map.get(join_id) or "").strip()
        if not value:
            unresolved_ids.append(join_id)
            return match.group(0)
        return value

    resolved = _TEXTJOIN_RE.sub(replace, source)
    ok = not unresolved_ids and not _TEXTJOIN_RE.search(resolved)
    return resolved, bool(ok), {
        "status": "resolved" if ok else "unresolved",
        "requested_ids": list(dict.fromkeys(requested_ids)),
        "unresolved_ids": list(dict.fromkeys(unresolved_ids)),
    }


def parse_hsr_bundle(files: Mapping[str, Any]) -> ParsedCatalog:
    achievements = _unwrap_rows(files.get("achievements"))
    series = _unwrap_rows(files.get("groups"))
    rewards = _unwrap_rows(files.get("rewards"))
    textjoin_configs = _unwrap_rows(files.get("textjoin_config"))
    textjoin_items = _unwrap_rows(files.get("textjoin_items"))
    text_map = _build_text_map(files.get("textmap_main"), files.get("textmap"))
    if not achievements or not series or not text_map:
        raise RepositorySourceError(
            "TurnBasedGameData 的必要成就資料結構不完整，已停止更新。",
            code="source_structure_changed",
            diagnostics={"achievements": len(achievements), "series": len(series), "text_count": len(text_map)},
        )
    textjoin_map, textjoin_diagnostics = _build_hsr_textjoin_map(textjoin_configs, textjoin_items, text_map)
    series_map: dict[str, tuple[str, int, bool]] = {}
    for index, row in enumerate(series):
        series_id = _text_key(_get(row, "SeriesID", "SeriesId", "seriesId", "id", "ID"))
        name, ok = _resolve_text_with_status(_get(row, "SeriesTitle", "SeriesName", "Name", "name"), text_map)
        if not ok or _looks_like_unresolved_source_text(name):
            name = ""
        series_map[series_id] = (name, _as_int(_get(row, "Priority", "Order", "Sort", "sort"), index), bool(name))
    reward_map = {_text_key(_get(row, "RewardID", "RewardId", "rewardId", "ID", "id")): row for row in rewards}
    rarity_reward = {"low": 5, "mid": 10, "high": 20, "raritylow": 5, "raritymid": 10, "rarityhigh": 20}
    hidden_show_types = {"showafterfinish"}
    rows: list[dict[str, Any]] = []
    skipped = 0
    unresolved_names = 0
    unresolved_conditions = 0
    unresolved_categories = 0
    unresolved_templates: list[dict[str, Any]] = []
    resolved_template_count = 0
    resolved_textjoin_count = 0
    show_type_counts: dict[str, int] = {}
    hidden_count = 0
    for index, row in enumerate(achievements):
        achievement_id = _text_key(_get(row, "AchievementID", "AchievementId", "achievementId", "ID", "id"))
        if not achievement_id:
            skipped += 1
            continue
        series_id = _text_key(_get(row, "SeriesID", "SeriesId", "seriesId"))
        name_template, name_ok = _resolve_text_with_status(_get(row, "AchievementTitle", "Title", "title"), text_map)
        condition_template, condition_ok = _resolve_text_with_status(_get(row, "AchievementDesc", "Description", "Desc", "description"), text_map)
        params = _extract_template_params(_get(row, "ParamList", "paramList", "AchievementParam", "achievementParam", default=[]))
        name, name_template_ok = _substitute_source_template(name_template, params)
        condition, condition_template_ok = _substitute_source_template(condition_template, params)
        had_template = bool(_TEMPLATE_MARKER_RE.search(name_template) or _TEMPLATE_MARKER_RE.search(condition_template))
        if had_template and name_template_ok and condition_template_ok:
            resolved_template_count += 1
        if not name_template_ok or not condition_template_ok:
            unresolved_templates.append({
                "achievement_id": achievement_id, "name_template": name_template,
                "condition_template": condition_template, "params": [_format_template_param(value) for value in params],
            })
            if not name_template_ok:
                name = ""
            if not condition_template_ok:
                condition = ""
        name_textjoin_resolution = {"status": "not_required", "requested_ids": [], "unresolved_ids": []}
        condition_textjoin_resolution = {"status": "not_required", "requested_ids": [], "unresolved_ids": []}
        if _TEXTJOIN_RE.search(name):
            name, textjoin_ok, name_textjoin_resolution = _resolve_hsr_textjoin_template(name, textjoin_map)
            if textjoin_ok:
                resolved_textjoin_count += 1
            else:
                unresolved_templates.append({"achievement_id": achievement_id, "field": "name", "reason": "textjoin", "template": name, **name_textjoin_resolution})
                name = ""
        if _TEXTJOIN_RE.search(condition):
            condition, textjoin_ok, condition_textjoin_resolution = _resolve_hsr_textjoin_template(condition, textjoin_map)
            if textjoin_ok:
                resolved_textjoin_count += 1
            else:
                unresolved_templates.append({"achievement_id": achievement_id, "field": "condition", "reason": "textjoin", "template": condition, **condition_textjoin_resolution})
                condition = ""
        if not _resolved_text_is_valid(name, resolved_from_textmap=name_ok, allow_numeric_title=True):
            unresolved_names += 1
            name = ""
        if not condition_ok or not condition or _looks_like_unresolved_source_text(condition):
            unresolved_conditions += 1
            condition = ""
        series_name, series_order, series_ok = series_map.get(series_id, ("", 0, False))
        if not series_ok:
            unresolved_categories += 1
            series_name = "未辨識分類"
        reward_id = _get(row, "RewardID", "RewardId", "rewardId")
        reward = _reward_value(reward_map.get(_text_key(reward_id)))
        if not reward:
            rarity = str(_scalar(_get(row, "Rarity", "rarity")) or "").casefold().replace("_", "")
            reward = rarity_reward.get(rarity, 0)
        progress = max([_as_int(value) for value in params] or [0])
        show_type_raw = str(_scalar(_get(row, "ShowType", "showType")) or "")
        show_type = _normalized_show_type(show_type_raw)
        show_type_counts[show_type_raw or "未標示"] = show_type_counts.get(show_type_raw or "未標示", 0) + 1
        hidden = show_type in hidden_show_types
        if hidden:
            hidden_count += 1
        hidden_desc, hidden_desc_ok = _resolve_text_with_status(_get(row, "HideAchievementDesc", "HiddenAchievementDesc", "hideAchievementDesc"), text_map)
        raw_with_decision = dict(row)
        raw_with_decision["_tracker_hidden_decision"] = {
            "show_type": show_type_raw, "normalized": show_type, "hidden": hidden,
            "hidden_description": hidden_desc if hidden_desc_ok else "",
        }
        raw_with_decision["_tracker_template_resolution"] = {
            "name_template": name_template, "condition_template": condition_template,
            "params": [_format_template_param(value) for value in params],
            "name_resolved": bool(name), "condition_resolved": bool(condition),
            "name_resolved_from_textmap": bool(name_ok),
            "numeric_title_accepted": bool(name_ok and re.fullmatch(r"\d+", name or "")),
            "name_textjoin_resolution": name_textjoin_resolution,
            "condition_textjoin_resolution": condition_textjoin_resolution,
        }
        rows.append(_normalized_row(
            game_id="hsr", achievement_id=achievement_id, name=name, condition=condition, category=series_name,
            source_order=series_order * 10000 + _as_int(_get(row, "Priority", "Order", "Sort", "sort"), index),
            source_id="turn_based_game_data", reward=reward, hidden=hidden, category_id=series_id, group_id=series_id,
            group_name=series_name if series_name != "未辨識分類" else "", progress_value=progress,
            level=_as_int(_get(row, "Level", "level")), next_link=_get(row, "NextAchievementID", "NextAchievementId", "nextAchievementId"),
            reward_id=reward_id, raw=raw_with_decision,
            provenance={
                "id": "primary", "name": "primary_textmap_cht_template_resolved" if name else "snapshot_preservation_required",
                "condition": "primary_textmap_cht_template_resolved" if condition else "snapshot_preservation_required",
                "category": "primary_textmap_cht" if series_name != "未辨識分類" else "snapshot_preservation_required",
                "reward": "primary", "hidden": "ShowType", "version": "repository_history_or_verified_catalog_snapshot",
            },
        ))
    if len(rows) < max(1, len(achievements) // 2):
        raise RepositorySourceError(
            "TurnBasedGameData 無法安全辨識足夠的成就 ID，已停止更新。",
            code="source_structure_changed",
            diagnostics={"source_rows": len(achievements), "parsed_rows": len(rows), "skipped_rows": skipped},
        )
    return ParsedCatalog(rows, {
        "achievement_rows": len(achievements), "parsed_rows": len(rows), "skipped_rows": skipped,
        "series_count": len(series), "reward_count": len(rewards), "text_count": len(text_map),
        "hidden_count": hidden_count, "show_type_counts": show_type_counts,
        "hidden_rule": ["ShowAfterFinish"],
        "hidden_rule_note": "僅 ShowType=ShowAfterFinish 視為隱藏；HideAchievementDesc 只保留為證據，不參與判定。",
        "resolved_template_count": resolved_template_count,
        "resolved_textjoin_count": resolved_textjoin_count,
        "textjoin_diagnostics": textjoin_diagnostics,
        "unresolved_template_count": len(unresolved_templates),
        "isolated_template_samples": unresolved_templates[:50],
        "unresolved_names": unresolved_names, "unresolved_conditions": unresolved_conditions,
        "unresolved_categories": unresolved_categories,
    })


_ZZZ_NORMAL_KEYS = {
    "id": ("GJAFKJENFBK", "MPLJPOKFCAP", "GAPDDOJPFGI", "Id", "ID", "id", "AchievementId", "achievementId"),
    "name": ("PIELLIBKHEG", "EBGMBNKJMLK", "BMBBBEIBOLE", "Name", "name", "Title", "title", "NameTextMapHash", "nameTextMapHash"),
    "description": ("MGJIGEMPJPD", "GGPDIGEPDIB", "MCAHHIIMKLP", "Desc", "desc", "Description", "description", "DescTextMapHash", "descTextMapHash"),
    "hidden": ("MHOLLDPKGMH", "PKIKMKKFCHN", "Hidden", "hidden", "IsHidden", "isHidden"),
    "group": ("GHDKOLIBPEO", "CPIOCKHOICN", "SecondClassId", "secondClassId", "GroupId", "groupId", "CategoryId", "categoryId"),
    "reward": ("HKNKGJEEICK", "IFDFMDFHNGG", "RewardId", "rewardId", "OnceRewardId", "onceRewardId"),
    # Achievement description templates use this value as parameter {0}.  In
    # current ZenlessData it references MonsterCardConfigTemplateTb.
    "template_param_0": ("MMKDIIHLDAD", "JKDPFGMHPBF", "TemplateParam", "templateParam", "Param0", "param0", "MonsterCardId", "monsterCardId"),
}
_ZZZ_MONSTER_CARD_KEYS = {
    "id": ("DBPDHPIBGHA", "HBKDOIKGNDE", "Id", "ID", "id", "CardId", "cardId", "MonsterCardId", "monsterCardId"),
    "name": ("NAFKIEBNJPA", "APHMGBEGGNP", "KMAEBKLOKJG", "Name", "name", "NameTextMapHash", "nameTextMapHash", "Title", "title"),
}
_ZZZ_GROUP_KEYS = {
    "id": ("ABPBJBNNCEI", "Id", "ID", "id", "SecondClassId", "secondClassId", "GroupId", "groupId"),
    "name": ("AEPCFEEHHEG", "Name", "name", "NameTextMapHash", "nameTextMapHash", "Title", "title"),
    "order": ("GBAFGKHIILE", "Sort", "sort", "Order", "order", "Priority", "priority"),
}
_ZZZ_ARCADE_KEYS = {
    "id": ("PEFODMAOLPK", "NOBPPDIPFPO", "Id", "ID", "id", "AchievementId", "achievementId"),
    "name": ("PIELLIBKHEG", "EBGMBNKJMLK", "Name", "name", "Title", "title"),
    "description": ("KHFAPCDLLCA", "MIIPOBCGDLJ", "Desc", "desc", "Description", "description"),
    "group": ("ICEKGNCNGDN", "JPBCEMNOIBA", "GroupId", "groupId", "CategoryId", "categoryId"),
    "order": ("EIBFHOIJGAK", "Sort", "sort", "Order", "order", "Priority", "priority"),
    "progress": ("BDLJLLGDHDL", "MPBJALEAGIP", "Progress", "progress", "TargetNum", "targetNum"),
    "reward": ("GBKOAIGLDOC", "IFDFMDFHNGG", "RewardId", "rewardId", "OnceRewardId", "onceRewardId"),
}
_ZZZ_ARCADE_GROUP_KEYS = {
    "id": ("DALBKGGEJEF", "DBPDHPIBGHA", "Id", "ID", "id", "GroupId", "groupId"),
    "name": ("DGOBKLFGJIL", "LHKGAICPJDG", "Name", "name", "Title", "title"),
    "order": ("DALBKGGEJEF", "DBPDHPIBGHA", "Sort", "sort", "Order", "order", "Priority", "priority"),
}

def _zzz_pattern_value(row: Mapping[str, Any], pattern: str) -> tuple[Any, str]:
    compiled = re.compile(pattern, flags=re.IGNORECASE)
    for key, value in row.items():
        raw = str(_scalar(value) or "")
        if compiled.fullmatch(raw):
            return value, str(key)
    return None, ""


def _zzz_value(row: Mapping[str, Any], names: Sequence[str], *, pattern: str = "") -> tuple[Any, str]:
    for name in names:
        if name in row:
            return row[name], name
    if pattern:
        return _zzz_pattern_value(row, pattern)
    return None, ""


def _infer_reference_key(
    rows: Sequence[dict[str, Any]],
    valid_ids: set[str],
    *,
    excluded: Sequence[str] = (),
) -> tuple[str, int, dict[str, int]]:
    """Infer an obfuscated foreign-key field by matching values to known IDs.

    ZenlessData changes obfuscated field names between releases.  The semantic
    relation remains stable, so the parser scores scalar columns by how often
    their values reference a parsed category/group ID.
    """
    normalized_ids = {_text_key(value) for value in valid_ids if _text_key(value)}
    if not rows or not normalized_ids:
        return "", 0, {}
    excluded_keys = {str(key) for key in excluded if str(key)}
    counts: dict[str, int] = {}
    observed: dict[str, int] = {}
    for row in rows:
        for key, value in row.items():
            key_text = str(key)
            if key_text in excluded_keys or isinstance(value, (dict, list, tuple)):
                continue
            scalar = _text_key(value)
            if not scalar:
                continue
            observed[key_text] = observed.get(key_text, 0) + 1
            if scalar in normalized_ids:
                counts[key_text] = counts.get(key_text, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (item[1], observed.get(item[0], 0)), reverse=True)
    if not ranked:
        return "", 0, {}
    best_key, best_count = ranked[0]
    minimum_matches = max(1, min(10, len(rows) // 20))
    coverage = best_count / max(1, observed.get(best_key, len(rows)))
    if best_count < minimum_matches or coverage < 0.20:
        return "", best_count, counts
    if len(ranked) > 1 and ranked[1][1] == best_count:
        return "", best_count, counts
    return best_key, best_count, counts


_ZZZ_INDEXED_TEMPLATE_RE = re.compile(r"\{(?P<index>\d+)\}")


def _zzz_monster_card_map(
    rows: Sequence[dict[str, Any]],
    text_map: Mapping[str, str],
    *,
    reference_ids: set[str] | None = None,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Resolve MonsterCard IDs to Traditional Chinese display names.

    AchievementTemplateTb.JKDPFGMHPBF references the Monster Card ID used by
    the game's formatted description.  MonsterCardConfigTemplateTb stores the
    corresponding localized text key, which is resolved through the same CHT
    TextMap as achievement names and descriptions.
    """
    result: dict[str, str] = {}
    detected: dict[str, str] = {}
    unresolved: list[dict[str, str]] = []
    duplicates: list[str] = []
    normalized_references = {
        _text_key(value) for value in (reference_ids or set()) if _text_key(value)
    }
    inferred_id_key, inferred_matches, inferred_scores = _infer_reference_key(
        rows,
        normalized_references,
        excluded=_ZZZ_MONSTER_CARD_KEYS["name"],
    )
    inference_method = "reference_column_coverage"
    if not inferred_id_key and normalized_references:
        sparse_scores: dict[str, int] = {}
        excluded_name_keys = set(_ZZZ_MONSTER_CARD_KEYS["name"])
        for row in rows:
            for key, value in row.items():
                key_text = str(key)
                if key_text in excluded_name_keys or isinstance(value, (dict, list, tuple)):
                    continue
                if _text_key(value) in normalized_references:
                    sparse_scores[key_text] = sparse_scores.get(key_text, 0) + 1
        ranked_sparse = sorted(sparse_scores.items(), key=lambda item: item[1], reverse=True)
        if (
            ranked_sparse
            and ranked_sparse[0][1] == len(normalized_references)
            and (len(ranked_sparse) == 1 or ranked_sparse[1][1] < ranked_sparse[0][1])
        ):
            inferred_id_key, inferred_matches = ranked_sparse[0]
            inferred_scores = sparse_scores
            inference_method = "complete_sparse_reference_set"
    for row in rows:
        card_value, card_key = _zzz_value(row, _ZZZ_MONSTER_CARD_KEYS["id"])
        if card_value in (None, "") and inferred_id_key and inferred_id_key in row:
            card_value, card_key = row[inferred_id_key], inferred_id_key
        name_value, name_key = _zzz_value(row, _ZZZ_MONSTER_CARD_KEYS["name"], pattern=r"OfficialName_Monster_[A-Za-z0-9_]+")
        card_id = _text_key(card_value)
        name, name_ok = _resolve_text_with_status(name_value, text_map)
        if not card_id:
            continue
        if card_id in result and name and result[card_id] != name:
            duplicates.append(card_id)
            continue
        if name_ok and name and not _looks_like_unresolved_source_text(name):
            result[card_id] = name
        else:
            unresolved.append({"card_id": card_id, "name_key": _text_key(name_value)})
        if card_key:
            detected.setdefault("card_id", card_key)
        if name_key:
            detected.setdefault("card_name", name_key)
    return result, {
        "source_rows": len(rows),
        "resolved_count": len(result),
        "unresolved_count": len(unresolved),
        "unresolved_samples": unresolved[:50],
        "duplicate_ids": sorted(set(duplicates))[:50],
        "detected_fields": detected,
        "reference_inference": {
            "reference_count": len(normalized_references),
            "inferred_id_key": inferred_id_key,
            "matches": inferred_matches,
            "scores": inferred_scores,
            "method": inference_method,
        },
    }


def _resolve_zzz_condition_template(
    condition: str,
    row: Mapping[str, Any],
    monster_cards: Mapping[str, str],
) -> tuple[str, bool, dict[str, Any]]:
    """Replace indexed ZZZ description parameters with source-derived text."""
    template = str(condition or "")
    placeholders = sorted({int(match.group("index")) for match in _ZZZ_INDEXED_TEMPLATE_RE.finditer(template)})
    if not placeholders:
        return template, True, {"status": "not_required", "template": template, "parameters": {}}

    parameter_value, parameter_key = _zzz_value(row, _ZZZ_NORMAL_KEYS["template_param_0"])
    parameter_id = _text_key(parameter_value)
    parameter_name = monster_cards.get(parameter_id, "") if parameter_id else ""
    parameters: dict[int, str] = {0: parameter_name} if parameter_name else {}
    unresolved: list[str] = []

    def replace(match: re.Match[str]) -> str:
        index = int(match.group("index"))
        value = str(parameters.get(index) or "").strip()
        if not value:
            unresolved.append(match.group(0))
            return match.group(0)
        return value

    resolved = _ZZZ_INDEXED_TEMPLATE_RE.sub(replace, template)
    unresolved.extend(match.group(0) for match in _ZZZ_INDEXED_TEMPLATE_RE.finditer(resolved))
    ok = not unresolved and not _looks_like_unresolved_source_text(resolved)
    return resolved, ok, {
        "status": "resolved" if ok else "unresolved",
        "template": template,
        "parameter_field": parameter_key,
        "parameter_value": parameter_id,
        "resolved_name": parameter_name,
        "lookup_source": "FileCfg/MonsterCardConfigTemplateTb.json",
        "text_source": "TextMap_CHTTemplateTb/TextMap_CHTOverwriteTemplateTb",
        "unresolved": list(dict.fromkeys(unresolved)),
    }


def _zzz_group_map(rows: Sequence[dict[str, Any]], text_map: Mapping[str, str], *, arcade: bool) -> tuple[dict[str, tuple[str, int]], dict[str, str], int]:
    result: dict[str, tuple[str, int]] = {}
    detected: dict[str, str] = {}
    unresolved = 0
    keyset = _ZZZ_ARCADE_GROUP_KEYS if arcade else _ZZZ_GROUP_KEYS
    name_pattern = r"Arcade_[A-Za-z0-9_]+_Title_\d+" if arcade else r"Achievement_SecondClassName_\d+"
    for index, row in enumerate(rows):
        group_value, group_key = _zzz_value(row, keyset["id"])
        name_value, name_key = _zzz_value(row, keyset["name"], pattern=name_pattern)
        group_id = _text_key(group_value)
        if not group_id and name_value is not None:
            match = re.search(r"(\d+)$", _text_key(name_value))
            group_id = match.group(1) if match else ""
        name, ok = _resolve_text_with_status(name_value, text_map, fallback=f"分類 {group_id}")
        if not ok:
            unresolved += 1
        if arcade and not name.startswith("【街機】"):
            name = f"【街機】{name}"
        order_value, order_key = _zzz_value(row, keyset["order"])
        if group_id:
            result[group_id] = (name, _as_int(order_value, index))
        if group_key:
            detected.setdefault("group_id", group_key)
        if name_key:
            detected.setdefault("group_name", name_key)
        if order_key:
            detected.setdefault("group_order", order_key)
    return result, detected, unresolved


def parse_zzz_bundle(files: Mapping[str, Any]) -> ParsedCatalog:
    normal = _unwrap_rows(files.get("achievements"))
    normal_groups = _unwrap_rows(files.get("groups"))
    arcade = _unwrap_rows(files.get("arcade_achievements"))
    arcade_groups = _unwrap_rows(files.get("arcade_groups"))
    rewards = _unwrap_rows(files.get("rewards"))
    monster_card_rows = _unwrap_rows(files.get("monster_cards"))
    text_map = _build_text_map(files.get("textmap"), files.get("textmap_overwrite"))
    if not normal or not normal_groups or not text_map:
        raise RepositorySourceError(
            "ZenlessData 的一般成就、分類或繁體中文文字表結構不完整，已停止更新。",
            code="source_structure_changed",
            diagnostics={"achievements": len(normal), "groups": len(normal_groups), "arcade": len(arcade), "text_count": len(text_map)},
        )
    groups, group_detected, unresolved_group_names = _zzz_group_map(normal_groups, text_map, arcade=False)
    arcade_group_map, arcade_group_detected, unresolved_arcade_group_names = _zzz_group_map(arcade_groups, text_map, arcade=True)
    monster_card_references: set[str] = set()
    for source_row in normal:
        parameter_value, _ = _zzz_value(source_row, _ZZZ_NORMAL_KEYS["template_param_0"])
        parameter_key = _text_key(parameter_value)
        if parameter_key and parameter_key not in {"0", "-1"}:
            monster_card_references.add(parameter_key)
    monster_card_map, monster_card_diagnostics = _zzz_monster_card_map(
        monster_card_rows,
        text_map,
        reference_ids=monster_card_references,
    )
    normal_excluded = tuple(
        dict.fromkeys(
            key
            for field in ("id", "name", "description", "hidden", "template_param_0")
            for key in _ZZZ_NORMAL_KEYS.get(field, ())
        )
    )
    arcade_excluded = tuple(
        dict.fromkeys(
            key
            for field in ("id", "name", "description", "order", "progress")
            for key in _ZZZ_ARCADE_KEYS.get(field, ())
        )
    )
    inferred_normal_group_key, inferred_normal_group_matches, normal_group_scores = _infer_reference_key(
        normal, set(groups), excluded=normal_excluded
    )
    inferred_arcade_group_key, inferred_arcade_group_matches, arcade_group_scores = _infer_reference_key(
        arcade, set(arcade_group_map), excluded=arcade_excluded
    )
    reward_references: set[str] = set()
    for source_table, keyset in ((normal, _ZZZ_NORMAL_KEYS), (arcade, _ZZZ_ARCADE_KEYS)):
        for source_row in source_table:
            reward_value, _ = _zzz_value(source_row, keyset.get("reward", ()))
            reward_key = _text_key(reward_value)
            if reward_key and reward_key not in {"0", "-1"}:
                reward_references.add(reward_key)
    reward_map, reward_diagnostics = _build_reward_map(rewards, reference_ids=reward_references)
    rows: list[dict[str, Any]] = []
    skipped = 0
    unresolved_names = 0
    unresolved_conditions = 0
    unresolved_categories = 0
    condition_template_count = 0
    condition_template_resolved_count = 0
    condition_template_unresolved: list[dict[str, Any]] = []
    detected_fields: dict[str, dict[str, str]] = {
        "normal_group": group_detected,
        "arcade_group": arcade_group_detected,
        "monster_cards": dict(monster_card_diagnostics.get("detected_fields") or {}),
    }

    def parse_table(table: Sequence[dict[str, Any]], group_lookup: Mapping[str, tuple[str, int]], *, is_arcade: bool) -> None:
        nonlocal skipped, unresolved_names, unresolved_conditions, unresolved_categories
        nonlocal condition_template_count, condition_template_resolved_count
        keyset = _ZZZ_ARCADE_KEYS if is_arcade else _ZZZ_NORMAL_KEYS
        local_detected: dict[str, str] = {}
        name_pattern = r"ArcadeAchievement_\d+_Name" if is_arcade else r"AchievementName_\d+"
        desc_pattern = r"ArcadeAchievement_\d+_Des" if is_arcade else r"AchievementDes_\d+"
        for index, row in enumerate(table):
            id_value, id_key = _zzz_value(row, keyset["id"])
            name_value, name_key = _zzz_value(row, keyset["name"], pattern=name_pattern)
            desc_value, desc_key = _zzz_value(row, keyset["description"], pattern=desc_pattern)
            achievement_id = _text_key(id_value)
            if not achievement_id and name_value is not None:
                match = re.search(r"(\d+)(?:_Name)?$", _text_key(name_value))
                achievement_id = match.group(1) if match else ""
            group_value, group_key = _zzz_value(row, keyset["group"])
            if group_value in (None, ""):
                inferred_key = inferred_arcade_group_key if is_arcade else inferred_normal_group_key
                if inferred_key and inferred_key in row:
                    group_value, group_key = row[inferred_key], inferred_key
            group_id = _text_key(group_value)
            name, name_ok = _resolve_text_with_status(name_value, text_map)
            condition, condition_textmap_ok = _resolve_text_with_status(desc_value, text_map)
            condition_template_resolution: dict[str, Any] = {"status": "not_required", "template": condition, "parameters": {}}
            if not is_arcade and _ZZZ_INDEXED_TEMPLATE_RE.search(condition or ""):
                condition_template_count += 1
                condition, condition_template_ok, condition_template_resolution = _resolve_zzz_condition_template(
                    condition, row, monster_card_map
                )
                if condition_template_ok:
                    condition_template_resolved_count += 1
                else:
                    condition_template_unresolved.append({
                        "achievement_id": achievement_id,
                        "name": name,
                        **condition_template_resolution,
                    })
            else:
                condition_template_ok = not _looks_like_unresolved_source_text(condition)
            condition_ok = bool(condition_textmap_ok and condition_template_ok and condition and not _looks_like_unresolved_source_text(condition))
            if not achievement_id or not name:
                skipped += 1
                continue
            if not name_ok:
                unresolved_names += 1
            if not condition_ok:
                unresolved_conditions += 1
            group_name, group_order = group_lookup.get(group_id, (("【街機】未辨識分類" if is_arcade else "未辨識分類"), 0))
            if group_id not in group_lookup:
                unresolved_categories += 1
            reward_id, reward_key = _zzz_value(row, keyset.get("reward", ()))
            reward = int(reward_map.get(_text_key(reward_id)) or 0)
            tags = ["街機成就"] if is_arcade else []
            if is_arcade:
                hidden = False
                order_value, order_key = _zzz_value(row, keyset["order"])
                progress_value, progress_key = _zzz_value(row, keyset["progress"])
            else:
                hidden_value, hidden_key = _zzz_value(row, keyset["hidden"])
                # Current ZenlessData uses an enum: value 1 is hidden, while 0
                # and 2 are visible. Generic truthiness incorrectly marked value
                # 2 as hidden. Semantic IsHidden fields still use normal booleans.
                if hidden_key in {"MHOLLDPKGMH", "PKIKMKKFCHN"}:
                    hidden = _as_int(hidden_value, -1) == 1
                    hidden_rule = f"{hidden_key}_equals_1"
                else:
                    hidden = _as_bool(hidden_value)
                    hidden_rule = "semantic_boolean"
                # The hidden enum field is not an order column. Preserve official file order
                # until a dedicated sortable field is structurally verified.
                order_value = index
                order_key = "source_index"
                progress_value = _get(row, "Progress", "progress", "TargetNum", "targetNum", default=1)
                progress_key = ""
                if hidden_key:
                    local_detected.setdefault("hidden", hidden_key)
                raw_hidden_evidence = {"field": hidden_key, "value": _scalar(hidden_value), "rule": hidden_rule, "hidden": hidden}
            template_param_value, template_param_key = _zzz_value(row, keyset.get("template_param_0", ()))
            raw_with_mapping = dict(row)
            raw_with_mapping["_tracker_detected_fields"] = {
                "id": id_key, "name": name_key, "description": desc_key, "group": group_key,
                "order": order_key, "progress": progress_key, "reward": reward_key,
                "condition_template_param_0": template_param_key,
            }
            if not is_arcade:
                raw_with_mapping["_tracker_hidden_decision"] = raw_hidden_evidence
                raw_with_mapping["_tracker_condition_template_resolution"] = condition_template_resolution
            condition_provenance: Any
            if condition_ok and condition_template_resolution.get("status") == "resolved":
                condition_provenance = {
                    "role": "primary",
                    "source": "zenless_data",
                    "reason": "textmap_template_resolved_from_monster_card",
                    "template_source": "AchievementTemplateTb + CHT TextMap",
                    "parameter_source": f"AchievementTemplateTb.{template_param_key}" if template_param_key else "",
                    "parameter_value": _text_key(template_param_value),
                    "lookup_source": "MonsterCardConfigTemplateTb",
                    "match_method": "monster_card_id",
                }
            elif condition_ok:
                condition_provenance = "primary_textmap_cht"
            else:
                condition_provenance = "snapshot_preservation_required"
            rows.append(_normalized_row(
                game_id="zzz",
                achievement_id=achievement_id,
                name=name,
                condition=condition,
                category=group_name,
                source_order=(500000 if is_arcade else 0) + group_order * 10000 + _as_int(order_value, index),
                source_id="zenless_data",
                reward=reward,
                hidden=hidden,
                tags=tags,
                category_id=group_id,
                group_id=group_id,
                group_name=group_name,
                progress_value=_as_int(progress_value, 1),
                level=_as_int(_get(row, "Level", "level", "Stage", "stage")),
                next_link=_get(row, "NextId", "nextId", "NextAchievementId", "nextAchievementId"),
                reward_id=reward_id,
                raw=raw_with_mapping,
                provenance={"id": "primary_detected", "name": "primary_textmap_cht", "condition": condition_provenance, "category": "primary_textmap_cht", "reward": "primary_once_reward" if reward else "verified_catalog_snapshot_required", "hidden": "primary" if not is_arcade else "not_applicable", "arcade": is_arcade, "version": "repository_history_or_verified_catalog_snapshot"},
            ))
            for label, key in (("id", id_key), ("name", name_key), ("description", desc_key), ("group", group_key), ("order", order_key), ("reward", reward_key), ("condition_template_param_0", template_param_key)):
                if key:
                    local_detected.setdefault(label, key)
        detected_fields["arcade" if is_arcade else "normal"] = local_detected

    detected_fields["group_reference_inference"] = {
        "normal_key": inferred_normal_group_key,
        "normal_matches": inferred_normal_group_matches,
        "arcade_key": inferred_arcade_group_key,
        "arcade_matches": inferred_arcade_group_matches,
    }
    parse_table(normal, groups, is_arcade=False)
    parse_table(arcade, arcade_group_map, is_arcade=True)
    total_source = len(normal) + len(arcade)
    if skipped and len(rows) < max(1, total_source // 2):
        raise RepositorySourceError(
            "ZenlessData 欄位結構可能已變更，無法安全辨識成就，已停止更新。",
            code="source_structure_changed",
            diagnostics={"source_rows": total_source, "parsed_rows": len(rows), "skipped_rows": skipped, "detected_fields": detected_fields},
        )
    unresolved_categories += unresolved_group_names + unresolved_arcade_group_names
    _translation_coverage_error(
        source_name="ZenlessData", source_rows=total_source, parsed_rows=len(rows),
        unresolved_names=unresolved_names, unresolved_conditions=unresolved_conditions,
        unresolved_categories=unresolved_categories, minimum_condition_ratio=0.85, minimum_category_ratio=0.80,
    )
    return ParsedCatalog(rows, {
        "normal_rows": len(normal), "arcade_rows": len(arcade), "parsed_rows": len(rows), "skipped_rows": skipped,
        "normal_group_count": len(normal_groups), "arcade_group_count": len(arcade_groups),
        "reward_count": len(rewards), "text_count": len(text_map), "detected_fields": detected_fields,
        "monster_card_count": len(monster_card_rows),
        "monster_card_name_count": len(monster_card_map),
        "monster_card_diagnostics": monster_card_diagnostics,
        "condition_template_count": condition_template_count,
        "condition_template_resolved_count": condition_template_resolved_count,
        "condition_template_unresolved_count": len(condition_template_unresolved),
        "condition_template_unresolved_samples": condition_template_unresolved[:50],
        "reward_diagnostics": reward_diagnostics,
        "unresolved_reward_references": sum(1 for row in rows if row.get("reward_id") and not int(row.get("reward") or 0)),
        "group_reference_scores": {"normal": normal_group_scores, "arcade": arcade_group_scores},
        "unresolved_names": unresolved_names, "unresolved_conditions": unresolved_conditions,
        "unresolved_categories": unresolved_categories,
    })


NTE_CATEGORY_NAMES = {
    "MainTypeExplore": "探索",
    "MainTypeFight": "戰鬥",
    "MainTypeQuest": "任務",
    "MainTypeInterest": "趣味",
    "MainTypeDevelop": "養成",
    "MainTypePlay": "玩法",
    "MainTypeCity": "城市",
    "MainTypeSocial": "羈絆",
}

NTE_PLAYSTATION_ACHIEVEMENT_ID_PATTERN = re.compile(r"Playstation_\d+")


def is_nte_playstation_achievement_id(value: Any) -> bool:
    return bool(NTE_PLAYSTATION_ACHIEVEMENT_ID_PATTERN.fullmatch(str(value or "").strip()))


def _nte_rows(value: Any) -> list[tuple[str, dict[str, Any]]]:
    container = value[0] if isinstance(value, list) and value and isinstance(value[0], dict) else {}
    rows = container.get("Rows") if isinstance(container, dict) else None
    if not isinstance(rows, dict):
        return []
    return [(str(key).strip(), dict(row)) for key, row in rows.items() if str(key).strip() and isinstance(row, dict)]


def _nte_achievement_text(value: Any) -> dict[str, str]:
    container = value[0] if isinstance(value, list) and value and isinstance(value[0], dict) else {}
    string_table = container.get("StringTable") if isinstance(container, dict) else None
    entries = string_table.get("KeysToEntries") if isinstance(string_table, dict) else None
    return {str(key): str(text) for key, text in entries.items()} if isinstance(entries, dict) else {}


def _nte_localized_text(value: Any) -> dict[str, str]:
    namespace = value.get("ST_Achievement") if isinstance(value, dict) else None
    return {str(key): str(text) for key, text in namespace.items()} if isinstance(namespace, dict) else {}


def _nte_text_reference(row: Mapping[str, Any], field: str, fallback_key: str) -> tuple[str, str, str]:
    reference = row.get(field)
    if not isinstance(reference, dict):
        return fallback_key, "", ""
    key = str(reference.get("Key") or fallback_key).strip()
    source = str(reference.get("SourceString") or "").strip()
    localized = str(reference.get("LocalizedString") or "").strip()
    return key, source, localized


def parse_nte_bundle(files: Mapping[str, Any]) -> ParsedCatalog:
    achievements = _nte_rows(files.get("achievements"))
    source_text = _nte_achievement_text(files.get("achievement_text"))
    traditional_text = _nte_localized_text(files.get("localization_zh_hant"))
    if not achievements or not source_text or not traditional_text:
        raise RepositorySourceError(
            "NTE_Assets 的成就、文字表或繁體中文本地化結構不完整，已停止更新。",
            code="source_structure_changed",
            diagnostics={
                "achievement_rows": len(achievements),
                "source_text_count": len(source_text),
                "traditional_text_count": len(traditional_text),
            },
        )

    playstation_ids = {
        achievement_id
        for achievement_id, _ in achievements
        if is_nte_playstation_achievement_id(achievement_id)
    }
    host_ids = {
        achievement_id
        for achievement_id, source_row in achievements
        if _as_bool(source_row.get("bIsHost"))
    }
    if playstation_ids != host_ids:
        raise RepositorySourceError(
            "NTE_Assets 的 PlayStation 專屬成就 ID 與 bIsHost 標記不一致，已停止更新。",
            code="nte_playstation_marker_mismatch",
            diagnostics={
                "playstation_id_count": len(playstation_ids),
                "host_flag_count": len(host_ids),
                "playstation_id_only": sorted(playstation_ids - host_ids)[:50],
                "host_flag_only": sorted(host_ids - playstation_ids)[:50],
            },
        )
    eligible_achievements = [
        (achievement_id, source_row)
        for achievement_id, source_row in achievements
        if achievement_id not in playstation_ids
    ]

    rows: list[dict[str, Any]] = []
    invalid_ids: list[str] = []
    unresolved_names = 0
    unresolved_conditions = 0
    unresolved_categories = 0
    hidden_count = 0
    extra_reward_rows = 0
    reward_item_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    for source_order, (achievement_id, source_row) in enumerate(eligible_achievements, 1):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", achievement_id) or len(achievement_id) > 64:
            invalid_ids.append(achievement_id)
            continue
        title_key, title_source, title_localized = _nte_text_reference(
            source_row, "TitleId", f"{achievement_id}_Title"
        )
        content_key, content_source, content_localized = _nte_text_reference(
            source_row, "ContentID", f"{achievement_id}_Content"
        )
        name = str(traditional_text.get(title_key) or "").strip()
        condition = str(traditional_text.get(content_key) or "").strip()
        if not name:
            unresolved_names += 1
        if not condition:
            unresolved_conditions += 1
        main_type = str(source_row.get("AchievementMainType") or "").split("::")[-1].strip()
        category = NTE_CATEGORY_NAMES.get(main_type, "")
        if not category:
            unresolved_categories += 1
            category = "未辨識分類"
        category_counts[category] = category_counts.get(category, 0) + 1

        rewards: list[dict[str, Any]] = []
        primary_reward = 0
        for reward in source_row.get("AwardInfo") if isinstance(source_row.get("AwardInfo"), list) else []:
            if not isinstance(reward, dict):
                continue
            item_id = str(_scalar(reward.get("ItemID")) or "").strip()
            amount = _as_int(reward.get("Amount"))
            if not item_id:
                continue
            rewards.append({"itemId": item_id, "amount": amount})
            reward_item_counts[item_id] = reward_item_counts.get(item_id, 0) + 1
            if item_id == "Annulith":
                primary_reward += amount
        if any(reward["itemId"] != "Annulith" for reward in rewards):
            extra_reward_rows += 1

        hidden = _as_bool(source_row.get("bIsHideNotAchieve"))
        hidden_count += 1 if hidden else 0
        raw = dict(source_row)
        raw["_tracker_text_resolution"] = {
            "titleKey": title_key,
            "contentKey": content_key,
            "titleSourceString": title_source,
            "contentSourceString": content_source,
            "titleLocalizedString": title_localized,
            "contentLocalizedString": content_localized,
            "traditionalNameResolved": bool(name),
            "traditionalConditionResolved": bool(condition),
        }
        raw["_tracker_rewards"] = rewards
        rows.append(_normalized_row(
            game_id="nte",
            achievement_id=achievement_id,
            name=name,
            condition=condition,
            category=category,
            source_order=source_order,
            source_id="nte_assets",
            version="版本待確認",
            reward=primary_reward,
            hidden=hidden,
            category_id=main_type,
            group_id=main_type,
            group_name=category,
            progress_value=_as_int(source_row.get("Amout"), 1),
            reward_id="Annulith" if primary_reward else "",
            raw=raw,
            provenance={
                "id": "primary_rows_key_case_sensitive",
                "name": "primary_localization_zh_hant" if name else "unresolved",
                "condition": "primary_localization_zh_hant" if condition else "unresolved",
                "category": "primary_achievement_main_type",
                "reward": "primary_award_info_annulith_display_full_list_preserved",
                "hidden": "primary_b_is_hide_not_achieve",
                "version": {"role": "pending", "source": "nte_assets_git_history"},
            },
        ))

    if invalid_ids:
        raise RepositorySourceError(
            "NTE_Assets 包含不符合共用安全格式的成就 ID，已停止更新。",
            code="invalid_achievement_ids",
            diagnostics={"invalid_count": len(invalid_ids), "samples": invalid_ids[:50]},
        )
    return ParsedCatalog(rows, {
        "achievement_rows": len(achievements),
        "eligible_achievement_rows": len(eligible_achievements),
        "parsed_rows": len(rows),
        "playstation_excluded_count": len(playstation_ids),
        "playstation_excluded_ids": sorted(playstation_ids),
        "host_flag_count": len(host_ids),
        "source_text_count": len(source_text),
        "traditional_text_count": len(traditional_text),
        "unresolved_names": unresolved_names,
        "unresolved_conditions": unresolved_conditions,
        "unresolved_categories": unresolved_categories,
        "translation_state": "partial_preserve_verified_snapshot" if unresolved_names or unresolved_conditions or unresolved_categories else "complete",
        "translation_coverage": {
            "name": round((len(rows) - unresolved_names) / max(1, len(rows)), 4),
            "condition": round((len(rows) - unresolved_conditions) / max(1, len(rows)), 4),
            "category": round((len(rows) - unresolved_categories) / max(1, len(rows)), 4),
        },
        "hidden_count": hidden_count,
        "category_count": len(category_counts),
        "category_counts": category_counts,
        "reward_item_counts": reward_item_counts,
        "extra_reward_rows": extra_reward_rows,
        "primary_reward_item": "Annulith",
        "image_processing": "disabled_by_product_scope",
    })


PARSERS = {
    "wuwa": parse_wuwa_bundle,
    "genshin": parse_genshin_bundle,
    "hsr": parse_hsr_bundle,
    "zzz": parse_zzz_bundle,
    "nte": parse_nte_bundle,
}



def parse_repository_bundle(bundle: FetchBundle) -> ParsedCatalog:
    parser = PARSERS[bundle.definition.game_id]
    parsed = parser(bundle.files)
    if len(parsed.rows) < bundle.definition.minimum_count:
        raise RepositorySourceError(
            f"解析後只有 {len(parsed.rows)} 筆，低於安全下限 {bundle.definition.minimum_count} 筆；已停止更新。",
            code="catalog_below_minimum",
            diagnostics={"parsed_count": len(parsed.rows), "minimum_count": bundle.definition.minimum_count, **parsed.diagnostics},
        )
    ids = [row["achievement_id"] for row in parsed.rows]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        raise RepositorySourceError(
            "主要來源包含重複成就 ID，已停止更新。",
            code="duplicate_achievement_ids",
            diagnostics={"duplicate_ids": duplicates[:50], "duplicate_count": len(duplicates)},
        )
    return parsed


def _valid_version(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text in {"未標示", "版本待確認", "待確認", "unknown", "Unknown"}:
        return ""
    match = re.search(r"\d+\.\d+(?:\.\d+)?", text)
    return match.group(0) if match else ""


def preserve_from_verified_catalog(
    primary_rows: Sequence[dict[str, Any]],
    verified_snapshot_rows: Sequence[dict[str, Any]],
    *,
    game_id: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    snapshot_by_id = {
        str(row.get("achievement_id") or row.get("id") or "").strip(): dict(row)
        for row in verified_snapshot_rows
        if str(row.get("achievement_id") or row.get("id") or "").strip()
    }
    primary_ids = {
        str(row.get("achievement_id") or row.get("id") or "").strip()
        for row in primary_rows
        if str(row.get("achievement_id") or row.get("id") or "").strip()
    }
    preserved_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    preserved_versions = 0
    preserved_unresolved_existing: list[dict[str, Any]] = []
    isolated: list[dict[str, Any]] = []
    safe_rows: list[dict[str, Any]] = []

    for source in primary_rows:
        row = dict(source)
        achievement_id = str(row.get("achievement_id") or row.get("id") or "").strip()
        snapshot = snapshot_by_id.get(achievement_id) or {}
        try:
            provenance = json.loads(row.get("provenance_json") or "{}") if isinstance(row.get("provenance_json"), str) else dict(row.get("provenance_json") or {})
        except (TypeError, json.JSONDecodeError):
            provenance = {}

        current_version = _valid_version(row.get("version"))
        snapshot_version = _valid_version(snapshot.get("version"))
        if not current_version and snapshot_version:
            row["version"] = snapshot_version
            provenance["version"] = {
                "role": "preservation",
                "source": "verified_catalog_snapshot",
                "reason": "preserve_existing_verified_version",
                "preserved_at": preserved_at,
            }
            preserved_versions += 1
        elif not current_version:
            row["version"] = "版本待確認"

        row["secondary_source_id"] = ""
        row["provenance_json"] = json.dumps(provenance, ensure_ascii=False, separators=(",", ":"), default=str)
        reasons: list[str] = []
        name_text = str(row.get("name") or "").strip()
        name_provenance = json.dumps(provenance.get("name") or "", ensure_ascii=False, default=str).casefold()
        verified_numeric_title = bool(re.fullmatch(r"\d{1,4}", name_text) and "textmap" in name_provenance)
        if not name_text or (_looks_like_unresolved_source_text(name_text) and not verified_numeric_title):
            reasons.append("name_unresolved")
        if not str(row.get("condition") or "").strip() or _looks_like_unresolved_source_text(row.get("condition")):
            reasons.append("condition_unresolved")
        if not str(row.get("category") or "").strip() or str(row.get("category") or "").strip() in {"未辨識分類", "【街機】未辨識分類"}:
            reasons.append("category_unresolved")
        if not _valid_version(row.get("version")):
            reasons.append("version_unresolved")
        if game_id == "wuwa" and row.get("_wuwa_historical_backfill"):
            reasons.append("historical_backfill_requires_review")
        reward_id = str(row.get("reward_id") or "").strip()
        if reward_id not in {"", "0", "-1"} and _as_int(row.get("reward")) <= 0:
            reasons.append("reward_unresolved")
        if game_id == "wuwa" and _as_int(row.get("reward")) <= 0 and "reward_unresolved" not in reasons:
            reasons.append("reward_unresolved")

        allow_pending_wuwa_version = game_id == "wuwa" and reasons == ["version_unresolved"]
        if reasons and not allow_pending_wuwa_version:
            if snapshot:
                preserved = dict(snapshot)
                preserved["achievement_id"] = achievement_id
                preserved["secondary_source_id"] = ""
                try:
                    preserved_provenance = json.loads(preserved.get("provenance_json") or "{}") if isinstance(preserved.get("provenance_json"), str) else dict(preserved.get("provenance_json") or {})
                except (TypeError, json.JSONDecodeError):
                    preserved_provenance = {}
                preserved_provenance["row"] = {
                    "role": "preservation",
                    "source": "verified_catalog_snapshot",
                    "reason": "primary_fields_unresolved",
                    "preserved_at": preserved_at,
                }
                preserved["provenance_json"] = json.dumps(preserved_provenance, ensure_ascii=False, separators=(",", ":"), default=str)
                safe_rows.append(preserved)
                preserved_unresolved_existing.append({
                    "achievement_id": achievement_id,
                    "name": str(row.get("name") or snapshot.get("name") or ""),
                    "condition": str(row.get("condition") or ""),
                    "version": str(row.get("version") or ""),
                    "category": str(row.get("category") or ""),
                    "reward": _as_int(row.get("reward")),
                    "reasons": reasons,
                })
                continue
            isolated_row = dict(row)
            isolated_row["achievement_id"] = achievement_id
            isolated_row["reasons"] = reasons
            isolated_row["source_item_id"] = achievement_id
            isolated_row["reward_id"] = reward_id
            isolated.append(isolated_row)
            continue
        safe_rows.append(row)

    preserved_snapshot_details: list[dict[str, Any]] = []
    for achievement_id in sorted(set(snapshot_by_id) - primary_ids, key=lambda value: int(value) if value.isdigit() else value):
        snapshot = dict(snapshot_by_id[achievement_id])
        snapshot["achievement_id"] = achievement_id
        snapshot["secondary_source_id"] = ""
        snapshot["_verified_snapshot_preserved"] = True
        try:
            provenance = json.loads(snapshot.get("provenance_json") or "{}") if isinstance(snapshot.get("provenance_json"), str) else dict(snapshot.get("provenance_json") or {})
        except (TypeError, json.JSONDecodeError):
            provenance = {}
        provenance["row"] = {
            "role": "preservation",
            "source": "verified_catalog_snapshot",
            "reason": "primary_row_unmatched",
            "preserved_at": preserved_at,
        }
        snapshot["provenance_json"] = json.dumps(provenance, ensure_ascii=False, separators=(",", ":"), default=str)
        safe_rows.append(snapshot)
        preserved_snapshot_details.append({
            "achievement_id": achievement_id,
            "name": str(snapshot.get("name") or ""),
            "condition": str(snapshot.get("condition") or ""),
            "version": str(snapshot.get("version") or ""),
            "category": str(snapshot.get("category") or ""),
            "source": str(snapshot.get("source") or "verified_catalog_snapshot"),
            "reason": "primary_row_unmatched",
        })

    return safe_rows, {
        "status": "ok" if not isolated else "partial",
        "mode": "primary_repository_with_verified_catalog_preservation",
        "version_authority": "primary_repository_history_and_verified_catalog_snapshot",
        "primary_count": len(primary_rows),
        "snapshot_count": len(snapshot_by_id),
        "matched_snapshot_count": len(primary_ids.intersection(snapshot_by_id)),
        "preserved_version_count": preserved_versions,
        "version_pending_count": sum(1 for row in safe_rows if row.get("version") == "版本待確認"),
        "preserved_snapshot_rows": len(preserved_snapshot_details),
        "preserved_snapshot_details": preserved_snapshot_details,
        "preserved_unresolved_existing_count": len(preserved_unresolved_existing),
        "preserved_unresolved_existing": preserved_unresolved_existing[:500],
        "isolated_count": len(isolated),
        "isolated_rows": isolated[:500],
        "safe_count": len(safe_rows),
    }


def source_cache_path(data_dir: Path, game_id: str) -> Path:
    return Path(data_dir) / "sources" / game_id / "repository-primary-cache.json"


def _normalize_candidate_source_order(rows: list[dict[str, Any]], *, source_id: str) -> int:
    normalized = 0
    normalized_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for row in rows:
        achievement_id = str(row.get("achievement_id") or "").strip()
        if not achievement_id.isdigit():
            continue
        official_order = int(achievement_id)
        current_order = _as_int(row.get("source_order"))
        if current_order == official_order:
            continue
        try:
            provenance = json.loads(row.get("provenance_json") or "{}") if isinstance(row.get("provenance_json"), str) else dict(row.get("provenance_json") or {})
        except (TypeError, json.JSONDecodeError):
            provenance = {}
        row["_source_order_before_official_normalization"] = current_order
        row["source_order"] = official_order
        provenance["source_order"] = {
            "role": "normalization",
            "source": source_id,
            "reason": "shared_catalog_order_uses_official_id",
            "previous_source_order": current_order,
            "official_id_order": official_order,
            "normalized_at": normalized_at,
        }
        row["provenance_json"] = json.dumps(provenance, ensure_ascii=False, separators=(",", ":"))
        normalized += 1
    return normalized


def _apply_nte_first_seen_versions(
    rows: list[dict[str, Any]],
    *,
    existing_rows: Sequence[dict[str, Any]],
    first_seen_by_id: Mapping[str, str],
) -> dict[str, Any]:
    existing_by_id = {
        str(row.get("achievement_id") or row.get("id") or "").strip(): dict(row)
        for row in existing_rows
        if str(row.get("achievement_id") or row.get("id") or "").strip()
    }
    resolved = 0
    preserved = 0
    unresolved: list[str] = []
    for row in rows:
        achievement_id = str(row.get("achievement_id") or "").strip()
        existing = existing_by_id.get(achievement_id) or {}
        exact = str(first_seen_by_id.get(achievement_id) or "").strip()
        previous_version = _valid_version(existing.get("version"))
        try:
            provenance = json.loads(row.get("provenance_json") or "{}") if isinstance(row.get("provenance_json"), str) else dict(row.get("provenance_json") or {})
        except (TypeError, json.JSONDecodeError):
            provenance = {}
        try:
            previous_provenance = json.loads(existing.get("provenance_json") or "{}") if isinstance(existing.get("provenance_json"), str) else dict(existing.get("provenance_json") or {})
        except (TypeError, json.JSONDecodeError):
            previous_provenance = {}
        if exact:
            exact_version = _valid_version(exact)
            row["version"] = ".".join(exact_version.split(".")[:2]) if exact_version else "版本待確認"
            provenance["version"] = {
                "role": "primary_history",
                "source": "nte_assets_git_history",
                "firstSeenVersion": exact,
                "versionSource": "git-history",
                "rule": "first_global_release_snapshot_where_achievement_row_id_exists",
            }
            resolved += 1
        elif previous_version:
            row["version"] = ".".join(previous_version.split(".")[:2])
            previous_version_provenance = previous_provenance.get("version")
            provenance["version"] = (
                dict(previous_version_provenance)
                if isinstance(previous_version_provenance, dict)
                else {
                    "role": "preservation",
                    "source": "verified_catalog_snapshot",
                    "versionSource": "git-history",
                }
            )
            preserved += 1
        else:
            row["version"] = "版本待確認"
            provenance["version"] = {
                "role": "unresolved",
                "source": "nte_assets_git_history",
                "versionSource": "git-history",
                "reason": "no_reliable_global_history_evidence",
            }
            unresolved.append(achievement_id)
        try:
            raw = json.loads(row.get("raw_json") or "{}") if isinstance(row.get("raw_json"), str) else dict(row.get("raw_json") or {})
        except (TypeError, json.JSONDecodeError):
            raw = {}
        raw["_tracker_version"] = dict(provenance["version"])
        row["raw_json"] = json.dumps(raw, ensure_ascii=False, separators=(",", ":"), default=str)
        row["provenance_json"] = json.dumps(provenance, ensure_ascii=False, separators=(",", ":"), default=str)
    return {
        "status": "ok" if not unresolved else ("partial" if resolved or preserved else "unavailable"),
        "version_source": "nte_assets_git_history",
        "resolved_count": resolved,
        "preserved_count": preserved,
        "unresolved_count": len(unresolved),
        "unresolved_ids": unresolved[:200],
    }


def _apply_wuwa_new_row_primary_defaults(
    rows: list[dict[str, Any]],
    *,
    source_ref: str,
    existing_ids: set[str],
    version_by_id: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source_version = _valid_version(source_ref)
    first_seen_by_id = {
        str(key or "").strip(): _valid_version(value)
        for key, value in dict(version_by_id or {}).items()
        if str(key or "").strip() and _valid_version(value)
    }
    reward_by_level = {1: 5, 2: 10, 3: 20}
    version_filled = 0
    reward_filled = 0
    historical_backfill = 0
    current_release = 0
    version_unresolved = 0
    filled_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for row in rows:
        achievement_id = str(row.get("achievement_id") or "").strip()
        if not achievement_id:
            continue
        is_existing = achievement_id in existing_ids
        try:
            provenance = json.loads(row.get("provenance_json") or "{}") if isinstance(row.get("provenance_json"), str) else dict(row.get("provenance_json") or {})
        except (TypeError, json.JSONDecodeError):
            provenance = {}
        first_seen_version = first_seen_by_id.get(achievement_id, "")
        if first_seen_version:
            row["version"] = first_seen_version
            provenance["version"] = {
                "role": "primary_branch_history",
                "source": "ww_data",
                "reason": "wuwa_github_first_seen_branch_version",
                "first_seen_ref": first_seen_version,
                "source_ref": source_ref,
                "supplemented_at": filled_at,
            }
            version_filled += 1
            if not is_existing and source_version and _version_less_than(first_seen_version, source_version):
                row["_wuwa_historical_backfill"] = True
                provenance["version"]["historical_backfill"] = True
                provenance["version"]["review_reason"] = "not_first_seen_in_current_source_ref"
                historical_backfill += 1
            elif not is_existing:
                current_release += 1
        elif not is_existing and not _valid_version(row.get("version")):
            row["_wuwa_version_unresolved_by_branch_history"] = True
            version_unresolved += 1
        level = _as_int(row.get("level"))
        inferred_reward = reward_by_level.get(level, 0)
        if not is_existing and _as_int(row.get("reward")) <= 0 and inferred_reward > 0:
            row["reward"] = inferred_reward
            provenance["reward"] = {
                "role": "primary_level_rule",
                "source": "ww_data",
                "reason": "wuwa_new_row_level_reward",
                "level": level,
                "supplemented_at": filled_at,
            }
            reward_filled += 1
        row["provenance_json"] = json.dumps(provenance, ensure_ascii=False, separators=(",", ":"))
    return {
        "source_ref_version": source_version,
        "version_filled": version_filled,
        "reward_filled": reward_filled,
        "historical_backfill_count": historical_backfill,
        "current_source_ref_count": current_release,
        "version_unresolved_count": version_unresolved,
    }


def _apply_hsr_new_row_primary_versions(
    rows: list[dict[str, Any]],
    *,
    existing_ids: set[str],
    version_by_id: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    first_seen_by_id = {
        str(key or "").strip(): _valid_version(value)
        for key, value in dict(version_by_id or {}).items()
        if str(key or "").strip() and _valid_version(value)
    }
    version_filled = 0
    version_unresolved = 0
    filled_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for row in rows:
        achievement_id = str(row.get("achievement_id") or "").strip()
        if not achievement_id:
            continue
        version = first_seen_by_id.get(achievement_id, "")
        if version:
            try:
                provenance = json.loads(row.get("provenance_json") or "{}") if isinstance(row.get("provenance_json"), str) else dict(row.get("provenance_json") or {})
            except (TypeError, json.JSONDecodeError):
                provenance = {}
            row["version"] = version
            provenance["version"] = {
                "role": "primary_repository_history",
                "source": "turn_based_game_data",
                "reason": "hsr_gitlab_first_seen_release_version",
                "first_seen_version": version,
                "supplemented_at": filled_at,
            }
            row["provenance_json"] = json.dumps(provenance, ensure_ascii=False, separators=(",", ":"))
            version_filled += 1
        elif achievement_id not in existing_ids and not _valid_version(row.get("version")):
            version_unresolved += 1
    return {
        "version_source": "turn_based_game_data_gitlab_release_history",
        "version_filled": version_filled,
        "version_unresolved_count": version_unresolved,
    }


def _apply_genshin_new_row_primary_versions(
    rows: list[dict[str, Any]],
    *,
    existing_ids: set[str],
    version_by_id: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    first_seen_by_id = {
        str(key or "").strip(): _valid_version(value)
        for key, value in dict(version_by_id or {}).items()
        if str(key or "").strip() and _valid_version(value)
    }
    version_filled = 0
    version_unresolved = 0
    filled_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for row in rows:
        achievement_id = str(row.get("achievement_id") or "").strip()
        if not achievement_id:
            continue
        version = first_seen_by_id.get(achievement_id, "")
        if version:
            try:
                provenance = json.loads(row.get("provenance_json") or "{}") if isinstance(row.get("provenance_json"), str) else dict(row.get("provenance_json") or {})
            except (TypeError, json.JSONDecodeError):
                provenance = {}
            row["version"] = version
            provenance["version"] = {
                "role": "primary_repository_history",
                "source": "anime_game_data",
                "reason": "genshin_gitlab_first_seen_release_version",
                "first_seen_version": version,
                "supplemented_at": filled_at,
            }
            row["provenance_json"] = json.dumps(provenance, ensure_ascii=False, separators=(",", ":"))
            version_filled += 1
        elif achievement_id not in existing_ids and not _valid_version(row.get("version")):
            version_unresolved += 1
    return {
        "version_source": "anime_game_data_gitlab_release_history",
        "version_filled": version_filled,
        "version_unresolved_count": version_unresolved,
    }


def _apply_zzz_new_row_primary_versions(
    rows: list[dict[str, Any]],
    *,
    existing_ids: set[str],
    version_by_id: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    first_seen_by_id = {
        str(key or "").strip(): _valid_version(value)
        for key, value in dict(version_by_id or {}).items()
        if str(key or "").strip() and _valid_version(value)
    }
    version_filled = 0
    version_unresolved = 0
    filled_at = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    for row in rows:
        achievement_id = str(row.get("achievement_id") or "").strip()
        if not achievement_id:
            continue
        version = first_seen_by_id.get(achievement_id, "")
        if version:
            try:
                provenance = json.loads(row.get("provenance_json") or "{}") if isinstance(row.get("provenance_json"), str) else dict(row.get("provenance_json") or {})
            except (TypeError, json.JSONDecodeError):
                provenance = {}
            row["version"] = version
            provenance["version"] = {
                "role": "primary_repository_history",
                "source": "zenless_data",
                "reason": "zzz_gitea_first_seen_release_version",
                "first_seen_version": version,
                "supplemented_at": filled_at,
            }
            row["provenance_json"] = json.dumps(provenance, ensure_ascii=False, separators=(",", ":"))
            version_filled += 1
        elif achievement_id not in existing_ids and not _valid_version(row.get("version")):
            version_unresolved += 1
    return {
        "version_source": "zenless_data_gitea_release_history",
        "version_filled": version_filled,
        "version_unresolved_count": version_unresolved,
    }


def write_source_cache(data_dir: Path, game_id: str, *, rows: Sequence[dict[str, Any]], metadata: Mapping[str, Any]) -> Path:
    path = source_cache_path(data_dir, game_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "source_architecture_version": SOURCE_ARCHITECTURE_VERSION,
        "game_id": game_id,
        "saved_at": int(time.time()),
        "metadata": dict(metadata),
        "rows": list(rows),
    }
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str), encoding="utf-8")
    temp.replace(path)
    return path


def prepare_repository_candidate(game_id: str, *, data_dir: Path, timeout: int = DEFAULT_TIMEOUT, verified_snapshot_rows: Sequence[dict[str, Any]] | None = None) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    definition = definition_for(game_id)
    bundle = fetch_repository_bundle(game_id, timeout=timeout)
    parsed = parse_repository_bundle(bundle)

    primary_rows = list(parsed.rows)
    existing_ids = {
        str(row.get("achievement_id") or row.get("id") or "").strip()
        for row in (verified_snapshot_rows or [])
        if str(row.get("achievement_id") or row.get("id") or "").strip()
    }
    primary_default_inference: dict[str, Any] = {
        "status": "not_applicable",
        "version_filled": 0,
        "version_unresolved_count": 0,
    }
    if game_id == "wuwa":
        primary_ids = {
            str(row.get("achievement_id") or "").strip()
            for row in primary_rows
            if str(row.get("achievement_id") or "").strip()
        }
        wuwa_first_seen_versions, wuwa_version_history = _resolve_wuwa_first_seen_versions(
            primary_ids,
            repository_url=definition.repository_url,
            current_ref=bundle.source_ref,
            timeout=timeout,
        )
        primary_default_inference = _apply_wuwa_new_row_primary_defaults(
            primary_rows,
            source_ref=bundle.source_ref,
            existing_ids=existing_ids,
            version_by_id=wuwa_first_seen_versions,
        )
        primary_default_inference["first_seen_version_resolution"] = wuwa_version_history
    elif game_id == "genshin":
        primary_ids = {
            str(row.get("achievement_id") or "").strip()
            for row in primary_rows
            if str(row.get("achievement_id") or "").strip()
        }
        genshin_first_seen_versions, genshin_version_history = _resolve_genshin_first_seen_versions(
            primary_ids,
            repository_url=definition.repository_url,
            current_ref=bundle.source_ref or "main",
            timeout=timeout,
        )
        primary_default_inference = _apply_genshin_new_row_primary_versions(
            primary_rows,
            existing_ids=existing_ids,
            version_by_id=genshin_first_seen_versions,
        )
        primary_default_inference["first_seen_version_resolution"] = genshin_version_history
    elif game_id == "hsr":
        primary_ids = {
            str(row.get("achievement_id") or "").strip()
            for row in primary_rows
            if str(row.get("achievement_id") or "").strip()
        }
        hsr_first_seen_versions, hsr_version_history = _resolve_hsr_first_seen_versions(
            primary_ids,
            repository_url=definition.repository_url,
            current_ref=bundle.source_ref or "main",
            timeout=timeout,
        )
        primary_default_inference = _apply_hsr_new_row_primary_versions(
            primary_rows,
            existing_ids=existing_ids,
            version_by_id=hsr_first_seen_versions,
        )
        primary_default_inference["first_seen_version_resolution"] = hsr_version_history
    elif game_id == "zzz":
        def is_arcade_row(row: Mapping[str, Any]) -> bool:
            try:
                tags = json.loads(str(row.get("tags_json") or "[]"))
            except (TypeError, json.JSONDecodeError):
                tags = []
            return isinstance(tags, list) and "街機成就" in {str(tag) for tag in tags}

        normal_ids = {
            str(row.get("achievement_id") or "").strip()
            for row in primary_rows
            if str(row.get("achievement_id") or "").strip()
            if not is_arcade_row(row)
        }
        arcade_ids = {
            str(row.get("achievement_id") or "").strip()
            for row in primary_rows
            if str(row.get("achievement_id") or "").strip()
            if is_arcade_row(row)
        }
        zzz_first_seen_versions, zzz_version_history = _resolve_zzz_first_seen_versions(
            normal_ids,
            arcade_ids,
            repository_url=definition.repository_url,
            current_ref=bundle.source_ref or "master",
            baseline_version="",
            timeout=timeout,
        )
        primary_default_inference = _apply_zzz_new_row_primary_versions(
            primary_rows,
            existing_ids=existing_ids,
            version_by_id=zzz_first_seen_versions,
        )
        primary_default_inference["first_seen_version_resolution"] = zzz_version_history
    elif game_id == "nte":
        new_primary_ids = {
            str(row.get("achievement_id") or "").strip()
            for row in primary_rows
            if str(row.get("achievement_id") or "").strip()
            and str(row.get("achievement_id") or "").strip() not in existing_ids
        }
        nte_first_seen_versions, nte_version_history = _resolve_nte_first_seen_versions(
            new_primary_ids,
            repository_url=definition.repository_url,
            timeout=timeout,
        )
        primary_default_inference = _apply_nte_first_seen_versions(
            primary_rows,
            existing_rows=verified_snapshot_rows or [],
            first_seen_by_id=nte_first_seen_versions,
        )
        primary_default_inference["first_seen_version_resolution"] = nte_version_history
    rows, catalog_preservation = preserve_from_verified_catalog(
        primary_rows,
        verified_snapshot_rows or [],
        game_id=game_id,
    )
    source_order_normalized_count = _normalize_candidate_source_order(rows, source_id=definition.primary_id)
    if len(rows) < definition.minimum_count:
        raise RepositorySourceError(
            f"完成安全隔離後只剩 {len(rows)} 筆，低於安全下限 {definition.minimum_count} 筆；已停止更新。",
            code="catalog_below_minimum_after_validation",
            diagnostics={
                "safe_count": len(rows), "minimum_count": definition.minimum_count,
                "catalog_preservation": catalog_preservation, "parser": parsed.diagnostics,
            },
        )
    for row in rows:
        row["source_ref"] = bundle.source_ref
    for row in catalog_preservation.get("isolated_rows") or []:
        row["source_ref"] = bundle.source_ref

    category_count = int(parsed.diagnostics.get("group_count") or parsed.diagnostics.get("series_count") or parsed.diagnostics.get("normal_group_count") or parsed.diagnostics.get("category_count") or 0)
    candidate_parsed_count = len(primary_rows)
    isolated_count = int(catalog_preservation.get("isolated_count") or 0)
    preserved_unresolved_count = int(catalog_preservation.get("preserved_unresolved_existing_count") or 0)
    unresolved_count = isolated_count + preserved_unresolved_count
    expected_observation_count = candidate_parsed_count
    matched_count = max(0, candidate_parsed_count - unresolved_count)
    missing_source_row_count = unresolved_count
    source_complete = unresolved_count == 0
    pairing_status = "ok" if source_complete else ("partial" if rows else "unresolved")
    official_unmatched_count = max(0, expected_observation_count - matched_count)
    cross_validation = {
        "pairing_status": pairing_status,
        "source_complete": source_complete,
        "primary_parsed_count": candidate_parsed_count,
        "source_reported_count": candidate_parsed_count,
        "missing_source_row_count": missing_source_row_count,
        "unmatched_detail_available": bool(catalog_preservation.get("isolated_rows")),
        "official_observations": expected_observation_count,
        "observation_count": expected_observation_count,
        "matched": matched_count,
        "official_unmatched_count": official_unmatched_count,
        "match_coverage": round(matched_count / max(1, expected_observation_count), 6),
        "match_methods": {"primary_official_id": matched_count},
        "category_count": category_count,
        "individual_content_entries": len(rows),
        "excluded_category_nodes": 0,
        "validation_mode": "primary_repository_history_with_verified_catalog_preservation",
        "catalog_preservation": catalog_preservation,
        "source_order_normalized_count": source_order_normalized_count,
    }
    source_conflicts: dict[str, list[dict[str, Any]]] = {}
    for item in catalog_preservation.get("isolated_rows") or []:
        achievement_id = str(item.get("achievement_id") or "")
        if achievement_id:
            source_conflicts.setdefault(achievement_id, []).append({
                "kind": "source_row_isolated",
                "message": "此來源列仍有無法安全確認的欄位，已隔離且不會寫入正式資料。",
                "reasons": list(item.get("reasons") or []),
            })
    for item in catalog_preservation.get("preserved_unresolved_existing") or []:
        achievement_id = str(item.get("achievement_id") or "")
        if achievement_id:
            source_conflicts.setdefault(achievement_id, []).append({
                "kind": "verified_snapshot_preserved",
                "message": "主要來源尚未能完整解析此既有欄位；本次保留目前正式值並等待後續確認。",
                "reasons": list(item.get("reasons") or []),
            })
    suspected_removed_details = [
        dict(item) for item in (catalog_preservation.get("preserved_snapshot_details") or [])
        if isinstance(item, dict) and str(item.get("achievement_id") or "").strip()
    ]
    suspected_removed_ids = [str(item["achievement_id"]) for item in suspected_removed_details]
    for item in suspected_removed_details:
        achievement_id = str(item.get("achievement_id") or "")
        source_conflicts.setdefault(achievement_id, []).append({
            "kind": "source_missing_from_primary",
            "message": "目前正式目錄仍有此成就，但最新主要來源未再列出；已列為疑似刪除並預設保留。",
            "reason": str(item.get("reason") or "primary_row_unmatched"),
        })

    metadata: dict[str, Any] = {
        "pipeline_version": PIPELINE_VERSION,
        "adapter_id": source_adapter_id(game_id),
        "fetch_status": "ok" if pairing_status == "ok" else ("incomplete" if pairing_status == "source_incomplete" else "degraded"),
        "source_mode": "remote_incomplete" if pairing_status == "source_incomplete" else "remote_repository",
        "purpose": "official_catalog",
        "source": definition.repository_url,
        "source_page": definition.repository_url,
        "source_name": definition.primary_name,
        "primary_source": {
            "id": definition.primary_id, "name": definition.primary_name, "url": definition.repository_url,
            "role": "primary", "mode": "remote_repository", "purpose": "official_catalog",
        },
        "source_ref": bundle.source_ref,
        "fetched_at": bundle.fetched_at,
        "count": len(rows),
        "file_manifest": bundle.manifests,
        "warnings": bundle.warnings,
        "parser_diagnostics": parsed.diagnostics,
        "primary_default_inference": primary_default_inference,
        "catalog_preservation": catalog_preservation,
        "cross_validation": cross_validation,
        "source_conflicts": source_conflicts,
        "suspected_removed_count": len(suspected_removed_ids),
        "suspected_removed_ids": suspected_removed_ids,
        "suspected_removed_details": suspected_removed_details,
        "primary_fields_authoritative": True,
        "version_authority": "primary_repository_history_then_verified_catalog_snapshot",
        "local_game_files_used": False,
        "guide_data_used": False,
        "source_complete": source_complete,
        "missing_source_row_count": missing_source_row_count,
        "requires_admin_confirmation": pairing_status != "ok",
        "diagnostic_preview": False,
        "apply_blocked": False,
        "apply_block_reason": "",
        "source_notice": {
            "kind": "primary_rows_isolated" if pairing_status != "ok" else "source_validated",
            "message": (
                f"主要來源有 {unresolved_count} 筆內容無法安全解析，已隔離或保留正式值；現有正式資料與版本不會被空值或錯誤欄位覆蓋。"
                if pairing_status != "ok"
                else "主要來源資料與版本歷史已完成安全驗證；既有已確認版本由正式資料快照保留。"
            ),
        },
    }
    cache_rows = [
        {
            key: value
            for key, value in row.items()
            if not str(key).startswith("_") and str(key) != "secondary_source_id"
        }
        for row in rows
    ]
    cache = write_source_cache(data_dir, game_id, rows=cache_rows, metadata=metadata)
    metadata["cache_file"] = cache.relative_to(Path(data_dir).parent).as_posix() if Path(data_dir).parent in cache.parents else cache.name
    source_payload = {
        "schema_version": 1,
        "source_architecture_version": SOURCE_ARCHITECTURE_VERSION,
        "game_id": game_id,
        "primary_source_id": definition.primary_id,
        "file_manifest": bundle.manifests,
        "parser_diagnostics": parsed.diagnostics,
        "catalog_preservation": catalog_preservation,
        "cross_validation": cross_validation,
    }
    return rows, metadata, source_payload

def test_repository_source(game_id: str, role: str, *, timeout: int = 15) -> dict[str, Any]:
    definition = definition_for(game_id)
    started = time.monotonic()
    if role == "primary":
        try:
            bundle = fetch_repository_bundle(game_id, timeout=timeout)
            parsed = PARSERS[game_id](bundle.files)
            return {
                "ok": True,
                "status": "ok",
                "source": definition.primary_name,
                "tested_url": definition.repository_url,
                "http_status": 200,
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "diagnostics": {"file_manifest": bundle.manifests, "parser": parsed.diagnostics, "parsed_count": len(parsed.rows)},
                "error": "",
            }
        except RepositorySourceError as exc:
            return {
                "ok": False,
                "status": "error",
                "source": definition.primary_name,
                "tested_url": definition.repository_url,
                "http_status": exc.diagnostics.get("http_status"),
                "elapsed_ms": int((time.monotonic() - started) * 1000),
                "diagnostics": exc.diagnostics,
                "error": str(exc),
                "error_code": exc.code,
            }
    if role == "fallback":
        return {"ok": True, "status": "ok", "source": "目前正式目錄（僅供故障保護）", "tested_url": "", "http_status": None, "elapsed_ms": 0, "diagnostics": {"note": "主要來源失敗時不會以空資料覆蓋，也不會自動用快取套用更新。"}, "error": ""}
    raise RepositorySourceError("來源角色無效。", code="invalid_source_role")
