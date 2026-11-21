from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Any


def _text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def _key(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _text(value)).casefold()
    return re.sub(r"[\s\-—–_·・,，。.!！?？:：;；'\"「」『』【】()（）]+", "", text)


def _issue_id(kind: str, *values: Any) -> str:
    raw = ":".join([kind, *[str(value or "") for value in values]])
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]


def scan_catalog(
    items: list[dict[str, Any]],
    *,
    progress_counts: dict[str, int] | None = None,
    relation_counts: dict[str, int] | None = None,
) -> dict[str, Any]:
    progress_counts = progress_counts or {}
    relation_counts = relation_counts or {}
    issues: list[dict[str, Any]] = []
    by_id: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    by_exact: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
    by_name: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    orders: dict[int, list[str]] = {}

    for index, item in enumerate(items, 1):
        achievement_id = _text(item.get("id") or item.get("achievement_id"))
        name = _text(item.get("name"))
        condition = _text(item.get("condition"))
        version = _text(item.get("version"))
        category = _text(item.get("category"))
        source_order = int(item.get("source_order") if item.get("source_order") is not None else item.get("sourceOrder") or 0)
        context = {
            "index": index,
            "achievement_id": achievement_id,
            "name": name,
            "progress_count": int(progress_counts.get(achievement_id, 0)),
            "relation_count": int(relation_counts.get(achievement_id, 0)),
        }
        if not achievement_id:
            issues.append({**context, "issue_id": _issue_id("missing_id", index), "kind": "missing_id", "level": "error", "risk": "blocked", "message": "缺少成就 ID。", "actions": ["manual_edit"]})
        if not name:
            issues.append({**context, "issue_id": _issue_id("missing_name", achievement_id, index), "kind": "missing_name", "level": "error", "risk": "blocked", "message": "缺少成就名稱。", "actions": ["manual_edit"]})
        if not condition:
            issues.append({**context, "issue_id": _issue_id("missing_condition", achievement_id), "kind": "missing_condition", "level": "warning", "risk": "needs_review", "message": "缺少達成條件。", "actions": ["manual_edit", "keep"]})
        if not version or version == "未標示":
            issues.append({**context, "issue_id": _issue_id("missing_version", achievement_id), "kind": "missing_version", "level": "warning", "risk": "needs_review", "message": "版本未辨識。", "actions": ["manual_edit", "keep"]})
        if not category or category == "未辨識分類":
            issues.append({**context, "issue_id": _issue_id("missing_category", achievement_id), "kind": "missing_category", "level": "warning", "risk": "needs_review", "message": "分類未辨識。", "actions": ["manual_edit", "keep"]})
        try:
            reward = int(item.get("reward", 0) or 0)
            if reward < 0 or reward > 1000:
                issues.append({**context, "issue_id": _issue_id("reward_range", achievement_id), "kind": "reward_range", "level": "warning", "risk": "needs_review", "message": f"獎勵數值異常：{reward}。", "actions": ["manual_edit", "keep"]})
        except Exception:
            issues.append({**context, "issue_id": _issue_id("reward_type", achievement_id), "kind": "reward_type", "level": "error", "risk": "blocked", "message": "獎勵不是數字。", "actions": ["manual_edit"]})
        if achievement_id:
            by_id.setdefault(achievement_id, []).append((index, item))
        if name and condition:
            by_exact.setdefault((_key(name), _key(condition)), []).append((index, item))
        if name:
            by_name.setdefault(_key(name), []).append((index, item))
        if source_order:
            orders.setdefault(source_order, []).append(achievement_id)

    for achievement_id, rows in by_id.items():
        if len(rows) <= 1:
            continue
        issues.append({
            "issue_id": _issue_id("duplicate_id", achievement_id),
            "kind": "duplicate_id",
            "level": "error",
            "risk": "blocked",
            "achievement_id": achievement_id,
            "name": _text(rows[0][1].get("name")),
            "indexes": [row[0] for row in rows],
            "message": f"相同成就 ID 出現 {len(rows)} 次。",
            "progress_count": int(progress_counts.get(achievement_id, 0)),
            "relation_count": int(relation_counts.get(achievement_id, 0)),
            "actions": ["merge_keep_first", "merge_keep_selected", "manual_edit"],
        })

    for duplicate_key, rows in by_exact.items():
        ids = [_text(row[1].get("id") or row[1].get("achievement_id")) for row in rows]
        if len(rows) <= 1 or len(set(ids)) <= 1:
            continue
        issues.append({
            "issue_id": _issue_id("exact_duplicate", *sorted(ids)),
            "kind": "exact_duplicate",
            "level": "warning",
            "risk": "needs_review",
            "achievement_id": ids[0],
            "related_ids": ids,
            "name": _text(rows[0][1].get("name")),
            "indexes": [row[0] for row in rows],
            "message": "成就名稱與達成條件完全相同，但使用不同 ID。",
            "progress_count": sum(int(progress_counts.get(value, 0)) for value in ids),
            "relation_count": sum(int(relation_counts.get(value, 0)) for value in ids),
            "actions": ["merge_keep_selected", "mark_legal_duplicate", "create_alias", "keep"],
        })

    for name_key, rows in by_name.items():
        if len(rows) <= 1:
            continue
        ids = [_text(row[1].get("id") or row[1].get("achievement_id")) for row in rows]
        conditions = {_key(row[1].get("condition")) for row in rows}
        if len(conditions) > 1:
            issues.append({
                "issue_id": _issue_id("same_name", *sorted(ids)),
                "kind": "same_name",
                "level": "info",
                "risk": "needs_review",
                "achievement_id": ids[0],
                "related_ids": ids,
                "name": _text(rows[0][1].get("name")),
                "indexes": [row[0] for row in rows],
                "message": "名稱相同但條件不同；可能是合法階段成就或互斥成就。",
                "progress_count": sum(int(progress_counts.get(value, 0)) for value in ids),
                "relation_count": sum(int(relation_counts.get(value, 0)) for value in ids),
                "actions": ["mark_legal_duplicate", "create_stage_group", "create_exclusive_group", "keep"],
            })

    for source_order, ids in orders.items():
        real_ids = [value for value in ids if value]
        if len(real_ids) > 1:
            issues.append({
                "issue_id": _issue_id("duplicate_order", source_order, *sorted(real_ids)),
                "kind": "duplicate_order",
                "level": "info",
                "risk": "needs_review",
                "achievement_id": real_ids[0],
                "related_ids": real_ids,
                "name": "",
                "message": f"排序值 {source_order} 由 {len(real_ids)} 個成就共用。",
                "progress_count": 0,
                "relation_count": 0,
                "actions": ["recalculate_order", "keep"],
            })

    # Low-cost similarity scan only inside the same first character bucket.
    buckets: dict[str, list[tuple[str, int, dict[str, Any]]]] = {}
    for index, item in enumerate(items, 1):
        name_key = _key(item.get("name"))
        if len(name_key) >= 4:
            buckets.setdefault(name_key[:1], []).append((name_key, index, item))
    seen_pairs: set[tuple[str, str]] = set()
    for rows in buckets.values():
        if len(rows) > 300:
            continue
        for left_pos, (left_key, left_index, left) in enumerate(rows):
            for right_key, right_index, right in rows[left_pos + 1:]:
                left_id = _text(left.get("id") or left.get("achievement_id"))
                right_id = _text(right.get("id") or right.get("achievement_id"))
                if not left_id or not right_id or left_id == right_id:
                    continue
                pair = tuple(sorted((left_id, right_id)))
                if pair in seen_pairs:
                    continue
                ratio = SequenceMatcher(None, left_key, right_key).ratio()
                if ratio < 0.94 or left_key == right_key:
                    continue
                seen_pairs.add(pair)
                issues.append({
                    "issue_id": _issue_id("similar_name", *pair),
                    "kind": "similar_name",
                    "level": "info",
                    "risk": "needs_review",
                    "achievement_id": left_id,
                    "related_ids": [left_id, right_id],
                    "name": _text(left.get("name")),
                    "indexes": [left_index, right_index],
                    "similarity": round(ratio, 4),
                    "message": f"名稱高度相似（{ratio:.0%}），請確認是否為改名或重複資料。",
                    "progress_count": int(progress_counts.get(left_id, 0)) + int(progress_counts.get(right_id, 0)),
                    "relation_count": int(relation_counts.get(left_id, 0)) + int(relation_counts.get(right_id, 0)),
                    "actions": ["merge_keep_selected", "create_alias", "mark_legal_duplicate", "keep"],
                })

    counts: dict[str, int] = {}
    risks: dict[str, int] = {"confirmed": 0, "needs_review": 0, "blocked": 0}
    for issue in issues:
        counts[issue["kind"]] = counts.get(issue["kind"], 0) + 1
        risks[issue.get("risk", "needs_review")] = risks.get(issue.get("risk", "needs_review"), 0) + 1
    return {
        "count": len(items),
        "issues": issues,
        "errors": sum(1 for issue in issues if issue.get("level") == "error"),
        "warnings": sum(1 for issue in issues if issue.get("level") == "warning"),
        "info": sum(1 for issue in issues if issue.get("level") == "info"),
        "by_kind": counts,
        "by_risk": risks,
    }


def repair_plan(items: list[dict[str, Any]], issues: list[dict[str, Any]], actions: dict[str, Any]) -> dict[str, Any]:
    rows = [dict(item) for item in items]
    by_id = {_text(item.get("id") or item.get("achievement_id")): item for item in rows}
    operations: list[dict[str, Any]] = []
    for issue in issues:
        issue_id = str(issue.get("issue_id") or "")
        decision = actions.get(issue_id)
        if not isinstance(decision, dict):
            continue
        action = str(decision.get("action") or "keep")
        if action in {"keep", "ignore"}:
            operations.append({"issue_id": issue_id, "action": action, "status": "no_change"})
            continue
        if action == "mark_legal_duplicate":
            operations.append({"issue_id": issue_id, "action": action, "status": "resolved_decision"})
            continue
        if action == "recalculate_order":
            for position, row in enumerate(rows, 1):
                row["sourceOrder"] = position
                row["source_order"] = position
            operations.append({"issue_id": issue_id, "action": action, "status": "planned", "affected": len(rows)})
            continue
        if action in {"merge_keep_first", "merge_keep_selected"}:
            related = [str(value) for value in issue.get("related_ids") or []]
            if issue.get("achievement_id") and issue.get("achievement_id") not in related:
                related.insert(0, str(issue.get("achievement_id")))
            keep_id = str(decision.get("keep_id") or (related[0] if related else ""))
            remove_ids = [value for value in related if value and value != keep_id]
            if not keep_id or keep_id not in by_id:
                operations.append({"issue_id": issue_id, "action": action, "status": "blocked", "reason": "keep_id_not_found"})
                continue
            if issue.get("kind") == "duplicate_id":
                kept = False
                compacted = []
                for row in rows:
                    row_id = _text(row.get("id") or row.get("achievement_id"))
                    if row_id != keep_id:
                        compacted.append(row)
                    elif not kept:
                        compacted.append(row)
                        kept = True
                rows = compacted
            else:
                rows = [row for row in rows if _text(row.get("id") or row.get("achievement_id")) not in remove_ids]
            operations.append({"issue_id": issue_id, "action": action, "status": "planned", "keep_id": keep_id, "remove_ids": remove_ids, "deduplicate_same_id": issue.get("kind") == "duplicate_id"})
            continue
        if action == "create_alias":
            alias_id = str(decision.get("alias_id") or (issue.get("related_ids") or [""])[-1])
            canonical_id = str(decision.get("keep_id") or decision.get("canonical_id") or issue.get("achievement_id") or "")
            if not alias_id or not canonical_id or alias_id == canonical_id or canonical_id not in by_id:
                operations.append({"issue_id": issue_id, "action": action, "status": "blocked", "reason": "invalid_alias_mapping"})
                continue
            operations.append({"issue_id": issue_id, "action": action, "status": "planned", "alias_id": alias_id, "canonical_id": canonical_id})
            continue
        if action in {"create_stage_group", "create_exclusive_group"}:
            member_ids = [str(value) for value in issue.get("related_ids") or [] if str(value)]
            if issue.get("achievement_id") and str(issue.get("achievement_id")) not in member_ids:
                member_ids.insert(0, str(issue.get("achievement_id")))
            member_ids = list(dict.fromkeys(member_ids))
            if len(member_ids) < 2:
                operations.append({"issue_id": issue_id, "action": action, "status": "blocked", "reason": "relation_requires_two_members"})
                continue
            relation_type = "stage" if action == "create_stage_group" else "exclusive"
            group_id = str(decision.get("group_id") or f"health-{relation_type}-{issue_id[:12]}")
            operations.append({"issue_id": issue_id, "action": action, "status": "planned", "relation_type": relation_type, "group_id": group_id, "member_ids": member_ids})
            continue
        if action == "manual_edit":
            achievement_id = str(decision.get("achievement_id") or issue.get("achievement_id") or "")
            row = by_id.get(achievement_id)
            changes = decision.get("changes") if isinstance(decision.get("changes"), dict) else {}
            if not row:
                operations.append({"issue_id": issue_id, "action": action, "status": "blocked", "reason": "achievement_not_found"})
                continue
            normalized_changes = dict(changes)
            if "sourceOrder" in normalized_changes and "source_order" not in normalized_changes:
                normalized_changes["source_order"] = normalized_changes.pop("sourceOrder")
            for key in ("name", "condition", "version", "category", "reward", "hidden", "source_order"):
                if key in normalized_changes:
                    row[key] = normalized_changes[key]
                    if key == "source_order":
                        row["sourceOrder"] = normalized_changes[key]
            operations.append({"issue_id": issue_id, "action": action, "status": "planned", "achievement_id": achievement_id, "changes": normalized_changes})
            continue
        operations.append({"issue_id": issue_id, "action": action, "status": "unsupported"})
    return {"items": rows, "operations": operations}
