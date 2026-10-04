"""Optional, version-verified localization; never mutates the primary catalog."""
from __future__ import annotations

import json
import re
import urllib.parse
from typing import Any, Callable, Mapping, Sequence

LANGUAGE_FILES = {
    "en": "TextMap/TextMap_MediumEN.json",
    "ja": "TextMap/TextMap_MediumJP.json",
    "zh-Hans": "TextMap/TextMap_MediumCHS.json",
}
GITLAB_PROJECT = "Dimbreath/animegamedata2"
FIELDS = ("name", "condition", "category")


def attach_localizations(rows: Sequence[dict[str, Any]], overlay: Mapping[str, Any]) -> None:
    """Attach optional display metadata to candidate rows, not primary fields."""
    for row in rows:
        key = str(row.get("official_source_id") or row.get("achievement_id") or "")
        values = (overlay.get("items") or {}).get(key)
        if not values:
            continue
        raw = row.get("raw_json") or {}
        raw = json.loads(raw) if isinstance(raw, str) else dict(raw)
        raw["_tracker_localizations"] = values
        raw["_tracker_localization_commit"] = overlay["source_commit"]
        raw["_tracker_localization_base"] = {field: row.get(field) or "" for field in FIELDS}
        row["raw_json"] = json.dumps(raw, ensure_ascii=False, separators=(",", ":"))


def public_localizations(raw: Any, current: Mapping[str, Any]) -> dict[str, dict[str, str]]:
    """Do not expose raw source data or stale translations of overridden fields."""
    # Import at call time: sync_engine also uses this module. Match precisely
    # the core sync normalization, without relaxing real text changes.
    from backend.services.sync_engine import normalize_space
    try:
        raw = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
        if not re.fullmatch(r"[0-9a-f]{40}", str(raw.get("_tracker_localization_commit") or "")):
            return {}
        base = raw.get("_tracker_localization_base") or {}
        result = {}
        for language in LANGUAGE_FILES:
            values = (raw.get("_tracker_localizations") or {}).get(language) or {}
            translated = {field: values[field] for field in FIELDS
                          if field in base and normalize_space(base[field]) == normalize_space(current.get(field))
                          and isinstance(values.get(field), str) and values[field].strip()}
            # Complete NTE/ZZZ rewards carry source IDs. Keep reward translations
            # inside the existing localization diff/apply path, not a side save.
            reward_ids = {str(reward.get('itemId') or '') for reward in raw.get('_tracker_rewards', [])
                          if isinstance(reward, dict)}
            names = values.get('rewardNames')
            if reward_ids and isinstance(names, dict):
                safe_names = {item_id: name.strip()[:200] for item_id, name in names.items()
                              if item_id in reward_ids and isinstance(name, str) and name.strip()}
                if safe_names:
                    translated['rewardNames'] = safe_names
            if translated:
                result[language] = translated
        return result
    except (ValueError, TypeError, AttributeError):
        return {}


def localization_fallback(values: Mapping[str, Mapping[str, str]], language: str,
                          original: Mapping[str, str]) -> dict[str, str]:
    """Fallback per field, not per whole achievement; do not translate authored data."""
    result = {}
    for field in FIELDS:
        result[field] = ""
        for code in dict.fromkeys((language, "zh-Hant", "zh-Hans")):
            value = (values.get(code) or {}).get(field)
            if code == "zh-Hant" and not str(value or "").strip():
                value = original.get(field)
            if isinstance(value, str) and value.strip():
                result[field] = value
                break
    return result


def localization_update_count(current: Sequence[Mapping[str, Any]], candidate: Sequence[Mapping[str, Any]]) -> int:
    """Count display-text updates separately from the core achievement diff."""
    existing = {str(row.get("achievement_id") or ""): row for row in current}
    count = 0
    for row in candidate:
        previous = existing.get(str(row.get("achievement_id") or ""))
        if previous is None:
            continue  # New achievements already have a core diff entry.
        values = public_localizations(row.get("raw_json"), row)
        if values and values != public_localizations(previous.get("raw_json"), previous):
            count += 1
    return count


def localization_preview_samples(current, candidate, limit=20):
    existing = {str(row.get("achievement_id") or ""): row for row in current}
    samples = []
    for row in candidate:
        previous = existing.get(str(row.get("achievement_id") or ""))
        if previous is None:
            continue
        values = public_localizations(row.get("raw_json"), row)
        if values and values != public_localizations(previous.get("raw_json"), previous):
            samples.append({"id": str(row["achievement_id"]), "name": row.get("name", ""), "localizations": values})
            if len(samples) >= limit:
                break
    return samples


def build_genshin_localizations(rows: Sequence[Mapping[str, Any]], groups: Any,
                               detected_fields: Mapping[str, str],
                               language_maps: Mapping[str, Any], *, commit: str) -> dict[str, Any]:
    from backend.services.game_data_sources import (
        _build_text_map, _resolve_text_with_status, _substitute_named_source_template,
        _looks_like_unresolved_source_text, _unwrap_rows, _text_key,
    )
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Localization requires an immutable source commit")
    group_rows = _unwrap_rows(groups)
    group_id = detected_fields.get("goal_id", "")
    group_name = detected_fields.get("goal_name", "")
    # The primary Genshin parser treats omitted semantic group IDs as zero.
    group_keys = {_text_key(r.get(group_id, 0) if group_id in {"id", "Id", "goalId", "GoalId"}
                           else r.get(group_id)): r.get(group_name)
                  for r in group_rows} if group_id and group_name else {}
    maps = {code: _build_text_map(payload) for code, payload in language_maps.items() if code in LANGUAGE_FILES}
    items: dict[str, Any] = {}
    coverage = {code: {field: 0 for field in FIELDS} for code in maps}
    for row in rows:
        aid = str(row.get("official_source_id") or row.get("achievement_id") or "")
        raw = json.loads(str(row.get("raw_json") or "{}"))
        keys = raw.get("_tracker_detected_fields") or {}
        # Only fields identified by the existing Traditional-Chinese parser.
        references = {"name": raw.get(keys.get("name", "")),
                      "condition": raw.get(keys.get("description", "")),
                      "category": group_keys.get(_text_key(raw.get(keys.get("goal_reference", "")))
                                                or str(row.get("group_id") or row.get("category_id") or ""))}
        localized = {}
        for code, text_map in maps.items():
            values = {}
            for field, reference in references.items():
                text, resolved = _resolve_text_with_status(reference, text_map)
                if not resolved:
                    continue
                text, template_ok, _ = _substitute_named_source_template(text, raw)
                if template_ok and text and not _looks_like_unresolved_source_text(text):
                    values[field] = text
                    coverage[code][field] += 1
            if values:
                localized[code] = values
        if aid and localized:
            items[aid] = localized
    return {"schema_version": 1, "game_id": "genshin", "source_commit": commit,
            "items": items, "coverage": coverage}


def fetch_genshin_localizations(bundle: Any, parsed: Any, *, timeout: int = 15,
                               request_json: Callable[[str], Any] | None = None) -> tuple[dict[str, Any], list[str]]:
    """Optional isolated fetch. Failures are returned, never raised into sync."""
    from backend.services.game_data_sources import _request_bytes, _decode_json
    def request(url: str) -> Any:
        if request_json:
            return request_json(url)
        raw, _ = _request_bytes(url, timeout=timeout, attempts=1, max_bytes=96 * 1024 * 1024)
        return _decode_json(raw, url=url)
    warnings: list[str] = []
    try:
        if bundle.definition.game_id != "genshin" or bundle.definition.repository_url != "https://gitlab.com/" + GITLAB_PROJECT:
            raise ValueError("Unsupported localization repository")
        ref = urllib.parse.quote(str(bundle.source_ref), safe="")
        metadata = request(f"https://gitlab.com/api/v4/projects/{urllib.parse.quote(GITLAB_PROJECT, safe='')}/repository/commits/{ref}")
        commit = str(metadata.get("id") or "").lower()
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Source commit was not resolved")
        base = f"https://gitlab.com/{GITLAB_PROJECT}/-/raw/{commit}/"
        # Verify all files which determine localized text against the exact bundle
        # already fetched by the normal sync. Never switch its branch or ID parser.
        for key in ("achievements", "groups", "textmap"):
            manifest = next((m for m in bundle.manifests if m.get("key") == key), None)
            path = str((manifest or {}).get("path") or "")
            if not path or ".." in path or not path.endswith(".json") or ":" in path:
                raise ValueError("Missing verified source path: " + key)
            if request(base + path) != bundle.files.get(key):
                raise ValueError("Source changed during fetch: " + key)
        language_maps = {}
        for language, path in LANGUAGE_FILES.items():
            try:
                language_maps[language] = request(base + path)
            except Exception as exc:
                warnings.append(f"{language} 成就翻譯未取得（{type(exc).__name__}）；保留原文備援。")
        overlay = build_genshin_localizations(parsed.rows, bundle.files["groups"],
                    parsed.diagnostics.get("detected_fields") or {}, language_maps, commit=commit)
        for language, counts in overlay["coverage"].items():
            for field, count in counts.items():
                if count < len(parsed.rows):
                    warnings.append(f"{language} {field} 翻譯缺少 {len(parsed.rows)-count} 筆；使用逐欄位原文備援。")
        return overlay, warnings
    except Exception as exc:
        return {}, [f"原神多語言來源版本無法確認（{type(exc).__name__}）；略過翻譯，不影響原本成就同步。"]
