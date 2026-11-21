from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from typing import Any, Iterable

DERIVED_RELATION_FIELDS = {
    "choiceGroup",
    "choiceGroupSize",
    "isChoiceGroup",
    "relationGroup",
    "relationGroupSize",
    "relationType",
    "stageOrder",
}

RELATION_TYPES = {"stage", "exclusive"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _issue(
    section: str,
    code: str,
    severity: str,
    risk: str,
    title: str,
    message: str,
    *,
    relation_type: str = "",
    group_id: str = "",
    achievement_id: str = "",
    user_id: str = "",
    evidence: dict[str, Any] | None = None,
    actions: list[str] | None = None,
) -> dict[str, Any]:
    evidence = evidence or {}
    identity = {
        "section": section,
        "code": code,
        "relation_type": relation_type,
        "group_id": group_id,
        "achievement_id": achievement_id,
        "user_id": user_id,
        "evidence": evidence,
    }
    return {
        "id": f"rel-{_hash(identity)[:24]}",
        "section": section,
        "code": code,
        "severity": severity,
        "risk": risk,
        "title": title,
        "message": message,
        "relation_type": relation_type,
        "group_id": group_id,
        "achievement_id": achievement_id,
        "user_id": user_id,
        "evidence": evidence,
        "actions": actions or ["review"],
    }


def _raw_member_ids(group: dict[str, Any]) -> list[str]:
    values = group.get("achievement_ids")
    if not isinstance(values, list):
        return []
    return [_text(value) for value in values if _text(value)]


def expected_relation_state(
    documents: dict[str, dict[str, Any]],
    catalog_ids: set[str],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Return canonical relation rows, derived metadata, and structural issues.

    The function never silently removes duplicate members. Raw input is inspected
    first, while canonical rows use the first occurrence only so previews remain
    deterministic.
    """
    issues: list[dict[str, Any]] = []
    expected_rows: list[dict[str, Any]] = []
    metadata: dict[str, dict[str, Any]] = {}
    global_membership: dict[str, tuple[str, str]] = {}
    group_id_owners: dict[str, str] = {}

    for file_type in ("stage", "exclusive"):
        document = documents.get(file_type) or {}
        groups = document.get("groups")
        if not isinstance(groups, list):
            issues.append(_issue(
                "structure", "groups_not_array", "error", "blocked",
                "關聯群組格式錯誤", f"{file_type} 關聯檔的 groups 不是陣列。",
                relation_type=file_type, actions=["repair_document_structure"],
            ))
            groups = []
        seen_group_ids: set[str] = set()
        for index, group in enumerate(groups, 1):
            if not isinstance(group, dict):
                issues.append(_issue(
                    "structure", "group_not_object", "error", "blocked",
                    "關聯群組格式錯誤", f"{file_type} 第 {index} 組不是物件。",
                    relation_type=file_type, evidence={"index": index}, actions=["remove_invalid_group"],
                ))
                continue
            group_id = _text(group.get("id"))
            declared_type = _text(group.get("type") or file_type).lower()
            name = _text(group.get("name"))
            basis = _text(group.get("basis"))
            raw_members = _raw_member_ids(group)

            if not group_id:
                issues.append(_issue(
                    "structure", "missing_group_id", "error", "blocked",
                    "缺少群組 ID", f"{file_type} 第 {index} 組沒有群組 ID。",
                    relation_type=file_type, evidence={"index": index}, actions=["assign_group_id"],
                ))
                group_id = f"__missing__:{file_type}:{index}"
            elif group_id in seen_group_ids:
                issues.append(_issue(
                    "structure", "duplicate_group_id", "error", "blocked",
                    "同類型群組 ID 重複", f"{file_type} 群組 ID「{group_id}」重複。",
                    relation_type=file_type, group_id=group_id, actions=["rename_group_id", "merge_relation_groups"],
                ))
            seen_group_ids.add(group_id)

            previous_owner = group_id_owners.get(group_id)
            if previous_owner and previous_owner != file_type:
                issues.append(_issue(
                    "structure", "cross_type_group_id_conflict", "error", "blocked",
                    "階段型與互斥型使用相同群組 ID",
                    f"群組 ID「{group_id}」同時存在於 {previous_owner} 與 {file_type}。",
                    relation_type=file_type, group_id=group_id,
                    evidence={"other_type": previous_owner}, actions=["rename_group_id", "merge_relation_groups"],
                ))
            group_id_owners[group_id] = file_type

            if declared_type not in RELATION_TYPES:
                issues.append(_issue(
                    "structure", "invalid_declared_type", "error", "blocked",
                    "群組類型無效", f"群組「{group_id}」宣告的類型「{declared_type}」無效。",
                    relation_type=file_type, group_id=group_id,
                    evidence={"declared_type": declared_type}, actions=["normalize_group_type"],
                ))
            elif declared_type != file_type:
                issues.append(_issue(
                    "structure", "file_type_mismatch", "error", "blocked",
                    "群組檔案與類型不一致",
                    f"群組「{group_id}」放在 {file_type} 檔案，但 type 為 {declared_type}。",
                    relation_type=file_type, group_id=group_id,
                    evidence={"declared_type": declared_type, "file_type": file_type}, actions=["normalize_group_type", "move_group_to_type"],
                ))

            counts: dict[str, int] = defaultdict(int)
            for member in raw_members:
                counts[member] += 1
            duplicate_members = sorted(member for member, count in counts.items() if count > 1)
            for member in duplicate_members:
                issues.append(_issue(
                    "structure", "duplicate_member_in_group", "error", "blocked",
                    "群組內成員重複",
                    f"群組「{group_id}」內成就「{member}」出現 {counts[member]} 次。",
                    relation_type=file_type, group_id=group_id, achievement_id=member,
                    evidence={"occurrences": counts[member]}, actions=["remove_duplicate_member"],
                ))

            unique_members: list[str] = []
            seen_members: set[str] = set()
            for member in raw_members:
                if member in seen_members:
                    continue
                seen_members.add(member)
                unique_members.append(member)
            if len(unique_members) < 2:
                issues.append(_issue(
                    "structure", "too_few_members", "error", "blocked",
                    "關聯群組成員不足", f"群組「{group_id}」至少需要 2 項不同成就。",
                    relation_type=file_type, group_id=group_id,
                    evidence={"member_count": len(unique_members)}, actions=["add_relation_member", "remove_invalid_group"],
                ))

            if not name:
                issues.append(_issue(
                    "content", "missing_group_name", "info", "needs_review",
                    "群組沒有顯示名稱", f"群組「{group_id}」尚未填寫群組名稱。",
                    relation_type=file_type, group_id=group_id, actions=["set_group_name", "mark_legal_exception"],
                ))
            if not basis:
                issues.append(_issue(
                    "content", "missing_group_basis", "warning", "needs_review",
                    "群組缺少判定依據",
                    f"群組「{group_id}」沒有記錄官方來源或管理員判定依據，無法驗證內容是否屬於同一系列。",
                    relation_type=file_type, group_id=group_id,
                    actions=["set_group_basis", "mark_legal_exception"],
                ))

            size = len(unique_members)
            for order, member in enumerate(unique_members, 1):
                if member not in catalog_ids:
                    issues.append(_issue(
                        "structure", "missing_catalog_member", "error", "blocked",
                        "關聯成就不在正式目錄",
                        f"群組「{group_id}」引用不存在的成就「{member}」。",
                        relation_type=file_type, group_id=group_id, achievement_id=member,
                        actions=["replace_relation_member", "remove_invalid_member"],
                    ))
                previous = global_membership.get(member)
                if previous and previous != (file_type, group_id):
                    issues.append(_issue(
                        "structure", "multiple_relation_memberships", "error", "blocked",
                        "成就同時屬於多個關聯群組",
                        f"成就「{member}」同時屬於 {previous[0]} 群組「{previous[1]}」與 {file_type} 群組「{group_id}」。",
                        relation_type=file_type, group_id=group_id, achievement_id=member,
                        evidence={"previous_type": previous[0], "previous_group_id": previous[1]},
                        actions=["choose_relation_group", "move_relation_member"],
                    ))
                else:
                    global_membership[member] = (file_type, group_id)
                expected_rows.append({
                    "group_id": group_id,
                    "achievement_id": member,
                    "relation_type": file_type,
                    "stage_order": order if file_type == "stage" else 0,
                    "group_name": name,
                    "basis": basis,
                })
                metadata[member] = {
                    "relationGroup": group_id,
                    "relationGroupSize": size,
                    "relationType": file_type,
                    "stageOrder": order if file_type == "stage" else 0,
                    "choiceGroup": group_id if file_type == "exclusive" else "",
                    "choiceGroupSize": size if file_type == "exclusive" else 0,
                    "isChoiceGroup": file_type == "exclusive",
                }
    return expected_rows, metadata, issues


def validate_relation_state(
    *,
    game_id: str,
    documents: dict[str, dict[str, Any]],
    catalog_items: list[dict[str, Any]],
    database_rows: list[dict[str, Any]],
    progress_rows: list[dict[str, Any]],
    exception_fingerprints: set[str] | None = None,
) -> dict[str, Any]:
    exception_fingerprints = exception_fingerprints or set()
    catalog_by_id = {
        _text(item.get("id") or item.get("achievement_id")): item
        for item in catalog_items
        if _text(item.get("id") or item.get("achievement_id"))
    }
    expected_rows, expected_metadata, issues = expected_relation_state(documents, set(catalog_by_id))

    expected_keyed = {
        (row["relation_type"], row["group_id"], row["achievement_id"]): int(row["stage_order"])
        for row in expected_rows
    }
    actual_keyed: dict[tuple[str, str, str], int] = {}
    for row in database_rows:
        key = (_text(row.get("relation_type")), _text(row.get("group_id")), _text(row.get("achievement_id")))
        actual_keyed[key] = int(row.get("stage_order") or 0)

    for key, order in sorted(expected_keyed.items()):
        if key not in actual_keyed:
            relation_type, group_id, achievement_id = key
            issues.append(_issue(
                "storage", "json_row_missing_in_database", "error", "blocked",
                "JSON 關聯尚未寫入資料庫",
                f"{relation_type} 群組「{group_id}」的成就「{achievement_id}」只存在於 JSON。",
                relation_type=relation_type, group_id=group_id, achievement_id=achievement_id,
                actions=["sync_json_to_database"],
            ))
        elif actual_keyed[key] != order:
            relation_type, group_id, achievement_id = key
            issues.append(_issue(
                "storage", "stage_order_mismatch", "error", "blocked",
                "階段順序在 JSON 與資料庫不一致",
                f"群組「{group_id}」成就「{achievement_id}」的 JSON 順序為 {order}，資料庫為 {actual_keyed[key]}。",
                relation_type=relation_type, group_id=group_id, achievement_id=achievement_id,
                evidence={"json_stage_order": order, "database_stage_order": actual_keyed[key]},
                actions=["sync_json_to_database", "sync_database_to_json"],
            ))
    for key, order in sorted(actual_keyed.items()):
        if key not in expected_keyed:
            relation_type, group_id, achievement_id = key
            issues.append(_issue(
                "storage", "database_row_missing_in_json", "error", "blocked",
                "資料庫關聯未登記於 JSON",
                f"{relation_type} 群組「{group_id}」的成就「{achievement_id}」只存在於資料庫。",
                relation_type=relation_type, group_id=group_id, achievement_id=achievement_id,
                evidence={"database_stage_order": order}, actions=["sync_database_to_json", "sync_json_to_database"],
            ))

    # Derived metadata is optional in source catalogs, but when present it must be
    # an exact projection of the canonical relation documents.
    for achievement_id, item in catalog_by_id.items():
        expected = expected_metadata.get(achievement_id, {
            "relationGroup": "", "relationGroupSize": 0, "relationType": "", "stageOrder": 0,
            "choiceGroup": "", "choiceGroupSize": 0, "isChoiceGroup": False,
        })
        present = {field for field in DERIVED_RELATION_FIELDS if field in item}
        mismatches = {
            field: {"current": item.get(field), "expected": expected[field]}
            for field in present
            if item.get(field) != expected[field]
        }
        if mismatches:
            issues.append(_issue(
                "derived", "derived_fields_mismatch", "warning", "needs_review",
                "關聯衍生欄位與正式關聯資料不一致",
                f"成就「{achievement_id}」有 {len(mismatches)} 個關聯衍生欄位需要重建。",
                achievement_id=achievement_id, evidence={"mismatches": mismatches},
                actions=["rebuild_derived_fields"],
            ))

    rows_by_group: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in expected_rows:
        rows_by_group[(row["relation_type"], row["group_id"])].append(row)
    progress_by_user: dict[str, set[str]] = defaultdict(set)
    completed_at: dict[tuple[str, str], int] = {}
    for row in progress_rows:
        user_id = _text(row.get("user_id"))
        achievement_id = _text(row.get("achievement_id"))
        if user_id and achievement_id:
            progress_by_user[user_id].add(achievement_id)
            completed_at[(user_id, achievement_id)] = int(row.get("completed_at") or 0)

    for (relation_type, group_id), members in rows_by_group.items():
        member_ids = [row["achievement_id"] for row in sorted(members, key=lambda value: (value["stage_order"], value["achievement_id"]))]
        if relation_type == "exclusive":
            for user_id, completed in progress_by_user.items():
                selected = [member for member in member_ids if member in completed]
                if len(selected) > 1:
                    issues.append(_issue(
                        "progress", "exclusive_progress_conflict", "error", "high",
                        "使用者同時完成互斥群組多項成就",
                        f"使用者「{user_id}」在互斥群組「{group_id}」完成了 {len(selected)} 項成就，必須由管理員決定保留哪一項。",
                        relation_type=relation_type, group_id=group_id, user_id=user_id,
                        evidence={
                            "completed_achievement_ids": selected,
                            "completed_at": {member: completed_at.get((user_id, member), 0) for member in selected},
                        },
                        actions=["keep_exclusive_progress", "mark_legal_exception"],
                    ))
        else:
            for user_id, completed in progress_by_user.items():
                completed_orders = [index for index, member in enumerate(member_ids, 1) if member in completed]
                if not completed_orders:
                    continue
                highest = max(completed_orders)
                missing_prior = [member_ids[index - 1] for index in range(1, highest) if member_ids[index - 1] not in completed]
                if missing_prior:
                    issues.append(_issue(
                        "progress", "stage_progress_gap", "warning", "high",
                        "使用者存在階段跳階進度",
                        f"使用者「{user_id}」已完成群組「{group_id}」後續階段，但缺少 {len(missing_prior)} 個前置階段。",
                        relation_type=relation_type, group_id=group_id, user_id=user_id,
                        evidence={"missing_prior_ids": missing_prior, "completed_orders": completed_orders, "member_ids": member_ids},
                        actions=["fill_prior_stage_progress", "remove_later_stage_progress", "mark_legal_exception"],
                    ))

    for issue in issues:
        fingerprint = _hash({
            "code": issue["code"], "relation_type": issue.get("relation_type"), "group_id": issue.get("group_id"),
            "achievement_id": issue.get("achievement_id"), "user_id": issue.get("user_id"), "evidence": issue.get("evidence"),
        })[:40]
        issue["fingerprint"] = fingerprint
        issue["state"] = "合法例外" if fingerprint in exception_fingerprints else "待處理"

    active_issues = [issue for issue in issues if issue["fingerprint"] not in exception_fingerprints]
    sections: dict[str, dict[str, int]] = {}
    for section in ("structure", "storage", "derived", "progress", "content"):
        values = [issue for issue in active_issues if issue["section"] == section]
        sections[section] = {
            "total": len(values),
            "errors": sum(1 for issue in values if issue["severity"] == "error"),
            "warnings": sum(1 for issue in values if issue["severity"] == "warning"),
            "info": sum(1 for issue in values if issue["severity"] == "info"),
        }
    summary = {
        "valid": not any(issue["severity"] == "error" for issue in active_issues),
        "issue_count": len(active_issues),
        "error_count": sum(1 for issue in active_issues if issue["severity"] == "error"),
        "warning_count": sum(1 for issue in active_issues if issue["severity"] == "warning"),
        "info_count": sum(1 for issue in active_issues if issue["severity"] == "info"),
        "legal_exception_count": len(issues) - len(active_issues),
        "json_relation_rows": len(expected_rows),
        "database_relation_rows": len(database_rows),
        "relation_groups": len(rows_by_group),
        "derived_field_issues": sum(1 for issue in active_issues if issue["section"] == "derived"),
        "progress_conflicts": sum(1 for issue in active_issues if issue["section"] == "progress"),
    }
    state_hash = _hash({
        "documents": documents,
        "database_rows": database_rows,
        "catalog_relation_fields": {
            achievement_id: {field: item.get(field) for field in DERIVED_RELATION_FIELDS if field in item}
            for achievement_id, item in catalog_by_id.items()
        },
        "progress_rows": progress_rows,
    })
    return {
        "game_id": game_id,
        "summary": summary,
        "sections": sections,
        "issues": active_issues,
        "all_issues": issues,
        "expected_rows": expected_rows,
        "expected_metadata": expected_metadata,
        "state_hash": state_hash,
    }
