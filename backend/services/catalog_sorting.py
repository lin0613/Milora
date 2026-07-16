from __future__ import annotations

import json
import re
from typing import Any, Iterable

_NUMERIC_ID = re.compile(r"^\d+$")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _tags(row: dict[str, Any]) -> list[str]:
    value = row.get("tags")
    if isinstance(value, (list, tuple, set)):
        return [_text(item) for item in value if _text(item)]
    raw = row.get("tags_json")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = []
        if isinstance(parsed, list):
            return [_text(item) for item in parsed if _text(item)]
    return []


def is_zzz_arcade(row: dict[str, Any] | None) -> bool:
    """Return whether a ZZZ catalog/change row belongs to arcade achievements.

    The marker is intentionally redundant because rows can originate from the
    formal catalog, a source candidate, a sync diff, or an administrator
    override.  Any verified arcade marker is sufficient; no ID range is
    hard-coded.
    """
    if not isinstance(row, dict):
        return False
    if row.get("arcade") is True or row.get("is_arcade") is True:
        return True
    category = _text(row.get("category") or row.get("group_name") or row.get("groupName"))
    if category.startswith("【街機】") or category.startswith("街機"):
        return True
    if any(tag in {"街機", "街機成就"} or tag.startswith("街機") for tag in _tags(row)):
        return True
    source_details = row.get("sourceDetails") or row.get("source_details")
    if isinstance(source_details, dict):
        provenance = source_details.get("provenance")
        if isinstance(provenance, dict) and provenance.get("arcade") is True:
            return True
    provenance = row.get("provenance") or row.get("provenance_json")
    if isinstance(provenance, str):
        try:
            provenance = json.loads(provenance)
        except Exception:
            provenance = {}
    return isinstance(provenance, dict) and provenance.get("arcade") is True


def achievement_id_value(row: dict[str, Any] | None) -> str:
    if not isinstance(row, dict):
        return ""
    return _text(
        row.get("achievement_id")
        or row.get("id")
        or row.get("official_source_id")
        or row.get("officialId")
        or row.get("display_id")
    )


def official_id_sort_key(value: Any) -> tuple[int, int, str]:
    text = _text(value)
    if _NUMERIC_ID.fullmatch(text):
        return (0, int(text), text)
    return (1, 2**63 - 1, text.casefold())


def catalog_sort_key(game_id: str, row: dict[str, Any] | None) -> tuple[Any, ...]:
    """Shared achievement ordering.

    All games retain numeric official-ID ordering.  ZZZ adds one leading bucket:
    normal achievements first, arcade achievements second.  IDs inside each
    bucket remain ascending numeric official IDs.
    """
    game = _text(game_id).lower()
    bucket = 1 if game == "zzz" and is_zzz_arcade(row) else 0
    return (bucket, *official_id_sort_key(achievement_id_value(row)))


def sort_catalog_rows(game_id: str, rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((dict(row) for row in rows), key=lambda row: catalog_sort_key(game_id, row))


def sync_change_sort_key(game_id: str, change: dict[str, Any]) -> tuple[Any, ...]:
    basis = change.get("candidate") if isinstance(change.get("candidate"), dict) else None
    if basis is None:
        basis = change.get("current") if isinstance(change.get("current"), dict) else None
    merged = dict(basis or {})
    for key in ("achievement_id", "category", "group_name", "tags_json", "arcade"):
        if key in change and key not in merged:
            merged[key] = change.get(key)
    return catalog_sort_key(game_id, merged)
