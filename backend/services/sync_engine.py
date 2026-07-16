from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Iterable

from backend.services.catalog_sorting import sort_catalog_rows, sync_change_sort_key

SYNC_FIELDS = ("name", "condition", "version", "category", "reward", "hidden", "tags_json", "source_order")
PROTECTED_FIELDS = {"version", "category", "hidden", "source_order"}


def normalize_space(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def normalize_gender_template_text(value: Any) -> str:
    text = str(value or "")
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
    return normalize_space(text)


def semantic_comparison_text(value: Any) -> str:
    return comparison_text(normalize_gender_template_text(value)).replace("/", "").replace("／", "")


def comparison_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", normalize_space(value)).casefold()
    return re.sub(r"[\s\-—–_·・,，。.!！?？:：;；'\"「」『』【】()（）]+", "", text)


def row_fingerprint(rows: Iterable[dict[str, Any]]) -> str:
    value = [
        {"achievement_id": row.get("achievement_id"), **{field: row.get(field) for field in SYNC_FIELDS}}
        for row in sorted(rows, key=lambda item: str(item.get("achievement_id") or ""))
    ]
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    tags = row.get("tags_json")
    if not isinstance(tags, str):
        tags = json.dumps(row.get("tags") if isinstance(row.get("tags"), list) else [], ensure_ascii=False)
    achievement_id=normalize_space(row.get("achievement_id") or row.get("id"))
    return {
        "achievement_id": achievement_id,
        "internal_id": normalize_space(row.get("internal_id") or achievement_id),
        "official_source_id": normalize_space(row.get("official_source_id") or row.get("officialId") or achievement_id),
        "identity_match_status": normalize_space(row.get("identity_match_status")),
        "identity_match_basis": normalize_space(row.get("identity_match_basis")),
        "name": normalize_space(row.get("name")),
        "condition": normalize_space(row.get("condition")),
        "version": normalize_space(row.get("version")) or "未標示",
        "category": normalize_space(row.get("category")) or "未辨識分類",
        "reward": int(row.get("reward") or 0),
        "hidden": 1 if bool(row.get("hidden")) else 0,
        "tags_json": tags,
        "source": normalize_space(row.get("source")) or "official",
        "source_order": int(row.get("source_order") if row.get("source_order") is not None else row.get("sourceOrder") or 0),
    }


def _field_differences(current: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for field in SYNC_FIELDS:
        before = current.get(field)
        after = candidate.get(field)
        if field == "tags_json":
            try:
                before = json.dumps(json.loads(before or "[]"), ensure_ascii=False, sort_keys=True)
                after = json.dumps(json.loads(after or "[]"), ensure_ascii=False, sort_keys=True)
            except Exception:
                pass
        if before != after:
            equivalent = False
            difference_kind = "value_changed"
            if field in {"name", "condition"}:
                equivalent = semantic_comparison_text(before) == semantic_comparison_text(after)
                if equivalent:
                    difference_kind = "template_format_only"
            result.append(
                {
                    "field": field,
                    "before": before,
                    "after": after,
                    "protected": field in PROTECTED_FIELDS,
                    "default_selected": field not in PROTECTED_FIELDS and not equivalent,
                    "equivalent": equivalent,
                    "difference_kind": difference_kind,
                }
            )
    return result


def build_diff(
    current_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    *,
    progress_counts: dict[str, int] | None = None,
    relation_counts: dict[str, int] | None = None,
    override_ids: set[str] | None = None,
    source_conflicts: dict[str, list[dict[str, Any]]] | None = None,
    suspected_removed_ids: set[str] | None = None,
    game_id: str = "",
) -> dict[str, Any]:
    progress_counts = progress_counts or {}
    relation_counts = relation_counts or {}
    override_ids = override_ids or set()
    source_conflicts = source_conflicts or {}
    suspected_removed_ids = {str(value) for value in (suspected_removed_ids or set()) if str(value)}
    current_raw = {normalize_row(row)["achievement_id"]: dict(row) for row in current_rows if normalize_row(row)["achievement_id"]}
    candidate_raw_all = {normalize_row(row)["achievement_id"]: dict(row) for row in candidate_rows if normalize_row(row)["achievement_id"]}
    candidate_raw = {key: row for key, row in candidate_raw_all.items() if key not in suspected_removed_ids}
    current = {key: normalize_row(row) for key, row in current_raw.items()}
    candidate = {key: normalize_row(row) for key, row in candidate_raw.items()}
    changes: list[dict[str, Any]] = []
    summary = {
        "added": 0,
        "modified": 0,
        "removed": 0,
        "suspected_removed": 0,
        "unchanged": 0,
        "confirmed": 0,
        "needs_review": 0,
        "blocked": 0,
        "source_conflict": 0,
        "total_changes": 0,
        "safe_default": 0,
    }

    for achievement_id in sorted(set(current) | set(candidate)):
        old = current.get(achievement_id)
        new = candidate.get(achievement_id)
        kind = "unchanged"
        fields: list[dict[str, Any]] = []
        reasons: list[str] = []
        risk = "confirmed"
        default_selected = True
        if old is None and new is not None:
            kind = "added"
            fields = [{"field": field, "before": None, "after": new.get(field), "protected": False, "default_selected": True} for field in SYNC_FIELDS]
        elif old is not None and new is None:
            kind = "removed"
            risk = "needs_review"
            reasons.append("目前正式目錄仍有此成就，但最新主要來源未再列出；可能已刪除、停止實裝或來源暫時缺漏，刪除前必須由管理員確認。")
            default_selected = False
        elif old is not None and new is not None:
            fields = _field_differences(old, new)
            if fields:
                kind = "modified"
            else:
                summary["unchanged"] += 1
                continue

        progress_count = int(progress_counts.get(achievement_id, 0))
        relation_count = int(relation_counts.get(achievement_id, 0))
        has_override = achievement_id in override_ids
        conflicts = source_conflicts.get(achievement_id) or []

        if progress_count:
            risk = "needs_review"
            reasons.append(f"已有 {progress_count} 筆使用者完成紀錄。")
            default_selected = False
        if relation_count:
            risk = "needs_review"
            reasons.append(f"屬於 {relation_count} 個關聯成就設定。")
            default_selected = False
        if has_override:
            risk = "needs_review"
            reasons.append("已有管理員手動覆寫，預設保留現有內容。")
            default_selected = False
        protected_changes = [row["field"] for row in fields if row.get("protected")]
        template_only = bool(fields) and all(row.get("difference_kind") == "template_format_only" for row in fields)
        if template_only:
            risk = "needs_review"
            reasons.append("目前值與來源值語意相同，僅性別文字模板或分隔格式不同。")
            default_selected = False
        if protected_changes:
            risk = "needs_review"
            reasons.append("涉及受保護欄位：" + "、".join(protected_changes))
            default_selected = False
        if conflicts:
            risk = "needs_review"
            reasons.append("主要來源與輔助來源存在欄位差異。")
            default_selected = False
            summary["source_conflict"] += 1
        if not achievement_id:
            risk = "blocked"
            reasons.append("缺少穩定成就 ID。")
            default_selected = False
        if new and (not new.get("name") or not new.get("category")):
            risk = "blocked"
            reasons.append("候選資料缺少必要欄位。")
            default_selected = False

        identity_status = str((new or old or {}).get("identity_match_status") or "").strip()
        identity_basis = str((new or old or {}).get("identity_match_basis") or "").strip()
        if identity_status == "ambiguous_new_identity":
            risk = "blocked"
            reasons.append("WW_Data 官方 ID 對應到多筆既有鳴潮成就，必須先由管理員完成身分配對。")
            default_selected = False
        elif risk != "blocked" and (
            identity_status == "needs_review"
            or identity_basis in {"exact_name_condition_category", "exact_name_condition"}
        ):
            risk = "needs_review"
            reasons.append("WW_Data 官方 ID 是依名稱、條件與分類推定配對；套用前必須由管理員確認。")
            default_selected = False

        change_id = hashlib.sha1(f"{kind}:{achievement_id}".encode("utf-8")).hexdigest()[:20]
        item = {
            "change_id": change_id,
            "achievement_id": achievement_id,
            "internal_id": (new or old or {}).get("internal_id", achievement_id),
            "official_source_id": (new or old or {}).get("official_source_id", achievement_id),
            "display_id": (new or old or {}).get("official_source_id", achievement_id),
            "identity_match_status": (new or old or {}).get("identity_match_status", ""),
            "identity_match_basis": (new or old or {}).get("identity_match_basis", ""),
            "name": (new or old or {}).get("name", ""),
            "type": kind,
            "risk": risk,
            "status": risk,
            "default_selected": default_selected,
            "fields": fields,
            "reasons": reasons,
            "current": old,
            "candidate": new,
            "progress_count": progress_count,
            "relation_count": relation_count,
            "has_admin_override": has_override,
            "source_conflicts": conflicts,
            "source_absence": ({
                "suspected_removed": True,
                "reason": "primary_row_unmatched" if achievement_id in suspected_removed_ids else "candidate_row_missing",
                "preserved_snapshot": achievement_id in suspected_removed_ids,
            } if kind == "removed" else {}),
            "changed_fields": [row.get("field") for row in fields],
            "template_format_only": template_only,
            "category": (new or old or {}).get("category", ""),
            "group_name": str((candidate_raw.get(achievement_id) or current_raw.get(achievement_id) or {}).get("group_name") or (candidate_raw.get(achievement_id) or current_raw.get(achievement_id) or {}).get("groupName") or ""),
            "version": (new or old or {}).get("version", ""),
            "reward": int((new or old or {}).get("reward") or 0),
            "hidden": bool((new or old or {}).get("hidden")),
            "tags_json": (new or old or {}).get("tags_json", "[]"),
            "source": (new or old or {}).get("source", ""),
        }
        changes.append(item)
        summary[kind] += 1
        if kind == "removed":
            summary["suspected_removed"] += 1
        summary[risk] += 1
        if default_selected:
            summary["safe_default"] += 1

    changes.sort(key=lambda row: sync_change_sort_key(game_id, row))
    summary["total_changes"] = summary["added"] + summary["modified"] + summary["removed"]
    return {
        "current_count": len(current),
        "candidate_count": len(candidate),
        "summary": summary,
        "changes": changes,
    }



def default_selection_decisions(changes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return every safe default decision without pagination truncation.

    The administrator UI renders changes page by page, but the requested
    default is global: every safe difference and every safe field is selected
    before the first page is shown. Blocked/review-only/protected differences
    remain unselected.
    """
    result: list[dict[str, Any]] = []
    for change in changes:
        if not change.get("default_selected") or change.get("risk") == "blocked":
            continue
        change_id = str(change.get("change_id") or "")
        if not change_id or change.get("type") == "removed":
            continue
        fields = [
            str(field.get("field") or "")
            for field in (change.get("fields") or [])
            if field.get("default_selected") and str(field.get("field") or "") in SYNC_FIELDS
        ]
        fields = [field for field in fields if field]
        # A candidate decision without fields would be a false-positive success.
        if change.get("type") != "added" and not fields:
            continue
        if change.get("type") == "added" and not fields:
            fields = list(SYNC_FIELDS)
        result.append({
            "change_id": change_id,
            "selected": True,
            "action": "candidate_all",
            "fields": fields,
            "reason": "",
        })
    return result

def apply_decisions(
    current_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    changes: list[dict[str, Any]],
    selected_change_ids: set[str],
    decisions: dict[str, Any] | None = None,
    game_id: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    decisions = decisions or {}
    current = {normalize_row(row)["achievement_id"]: normalize_row(row) for row in current_rows if normalize_row(row)["achievement_id"]}
    candidate = {normalize_row(row)["achievement_id"]: normalize_row(row) for row in candidate_rows if normalize_row(row)["achievement_id"]}
    by_id = {str(row.get("change_id") or ""): row for row in changes}
    final = dict(current)
    summary: dict[str, Any] = {
        "added": 0, "modified": 0, "removed": 0, "selected": 0, "field_updates": 0,
        "recorded_no_action": 0, "pending_review": 0, "legal_difference": 0,
        "admin_overrides": 0, "unchanged_selected": 0, "field_update_counts": {},
        "applied_changes": [], "recorded_decisions": [],
    }

    no_change_actions = {"keep", "ignore", "record_no_action", "pending_review", "legal_difference"}
    for change_id in selected_change_ids:
        change = by_id.get(change_id)
        if not change or change.get("risk") == "blocked":
            continue
        achievement_id = str(change.get("achievement_id") or "")
        kind = str(change.get("type") or "")
        decision = decisions.get(change_id) if isinstance(decisions.get(change_id), dict) else {}
        action = str(decision.get("action") or "candidate")
        reason = normalize_space(decision.get("reason"))
        summary["selected"] += 1
        if action in no_change_actions:
            if action in {"keep", "ignore", "record_no_action"}:
                summary["recorded_no_action"] += 1
            elif action == "pending_review":
                summary["pending_review"] += 1
            elif action == "legal_difference":
                summary["legal_difference"] += 1
            summary["recorded_decisions"].append({
                "change_id": change_id, "achievement_id": achievement_id, "action": action,
                "fields": [], "reason": reason, "data_changed": False,
            })
            continue
        if kind == "removed":
            if action in {"remove", "candidate", "candidate_all"}:
                existed = achievement_id in final
                final.pop(achievement_id, None)
                if existed:
                    summary["removed"] += 1
                else:
                    summary["unchanged_selected"] += 1
                summary["applied_changes"].append({"change_id": change_id, "achievement_id": achievement_id, "action": action, "fields": ["__remove__"]})
            continue
        new = candidate.get(achievement_id)
        if not new:
            summary["unchanged_selected"] += 1
            continue
        if kind == "added":
            final[achievement_id] = new
            summary["added"] += 1
            summary["field_updates"] += len(SYNC_FIELDS)
            for field in SYNC_FIELDS:
                summary["field_update_counts"][field] = int(summary["field_update_counts"].get(field, 0)) + 1
            summary["applied_changes"].append({"change_id": change_id, "achievement_id": achievement_id, "action": action, "fields": list(SYNC_FIELDS)})
            continue
        old = dict(final.get(achievement_id) or new)
        fields = decision.get("fields")
        if action == "candidate_all":
            fields = [row["field"] for row in change.get("fields") or []]
        elif action == "fill_blank":
            requested = fields if isinstance(fields, list) and fields else [row["field"] for row in change.get("fields") or []]
            fields = [field for field in requested if field in SYNC_FIELDS and old.get(field) in (None, "", 0, "未標示", "未辨識分類", "[]")]
        elif not isinstance(fields, list):
            fields = [row["field"] for row in change.get("fields") or [] if row.get("default_selected")]
        fields = [str(field) for field in fields if field in SYNC_FIELDS]
        if action in {"candidate", "admin_override"} and not fields:
            raise ValueError(f"成就 {achievement_id} 未選擇任何可套用欄位。")
        actually_changed: list[str] = []
        for field in fields:
            value = new.get(field)
            if old.get(field) != value:
                old[field] = value
                actually_changed.append(field)
                summary["field_updates"] += 1
                summary["field_update_counts"][field] = int(summary["field_update_counts"].get(field, 0)) + 1
        if actually_changed:
            old["source"] = new.get("source") or old.get("source") or "official"
            final[achievement_id] = old
            summary["modified"] += 1
            if action == "admin_override":
                summary["admin_overrides"] += 1
            summary["applied_changes"].append({"change_id": change_id, "achievement_id": achievement_id, "action": action, "fields": actually_changed})
        else:
            summary["unchanged_selected"] += 1
        summary["recorded_decisions"].append({
            "change_id": change_id, "achievement_id": achievement_id, "action": action,
            "fields": fields, "reason": reason, "data_changed": bool(actually_changed),
        })

    rows = sort_catalog_rows(game_id, final.values())
    summary["total_changes"] = summary["added"] + summary["modified"] + summary["removed"]
    return rows, summary
