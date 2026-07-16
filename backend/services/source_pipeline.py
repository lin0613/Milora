from __future__ import annotations

import re
import urllib.error
from typing import Any

PIPELINE_VERSION = "source-architecture-preview-generation-guard-v4"



def source_error_code(exc: BaseException) -> str:
    if isinstance(exc, urllib.error.HTTPError):
        return f"upstream_http_{int(exc.code)}"
    if isinstance(exc, urllib.error.URLError):
        reason = str(getattr(exc, "reason", "") or "").casefold()
        if "timed out" in reason or "timeout" in reason:
            return "upstream_timeout"
        return "upstream_connection_failed"
    value = str(exc or "").casefold()
    match = re.search(r"\b(502|503|504)\b", value)
    if match:
        return f"upstream_http_{match.group(1)}"
    if "timeout" in value or "timed out" in value or "budget_exhausted" in value:
        return "upstream_timeout"
    if "channel_not_found" in value:
        return "achievement_channel_not_found"
    if "no_content_entries" in value:
        return "achievement_channel_empty"
    if "parse_returned_no_rows" in value:
        return "official_parse_empty"
    return "official_source_unavailable"


def adapter_id(game_id: str) -> str:
    return {
        "hsr": "hsr_turn_based_game_data_gitlab_release_history_adapter_v2",
        "genshin": "genshin_anime_game_data2_adapter_parser_recovery_decision_control",
        "zzz": "zzz_zenless_data_gitea_release_history_adapter_v2",
        "wuwa": "wuwa_ww_data_adapter_parser_recovery_decision_control",
    }.get(str(game_id or ""), f"{game_id}_repository_adapter_parser_recovery_decision_control")


def common_metadata(
    game_id: str,
    *,
    fetch_status: str,
    source_mode: str,
    purpose: str = "official_catalog",
    error: str = "",
    error_code: str = "",
) -> dict[str, Any]:
    return {
        "pipeline_version": PIPELINE_VERSION,
        "adapter_id": adapter_id(game_id),
        "fetch_status": fetch_status,
        "source_mode": source_mode,
        "purpose": purpose,
        "error": error,
        "error_code": error_code,
    }
