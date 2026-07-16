from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any, Iterable

from backend.services.governance_contract import HIGH_RISK_ACTIONS, normalize_suggested_actions

ALLOWED_ITEM_FIELDS = {
    "id", "achievement_id", "name", "condition", "version", "category", "reward",
    "hidden", "tags", "source", "sourceOrder", "source_order", "source_id",
    "official_id", "arcade", "is_deleted", "game_id", "tags_json",
    "is_override", "override_updated_at",
    # Source and matching metadata are registered system fields. They may be persisted by
    # remote adapters, but are not part of the public achievement presentation model.
    "content_id", "raw_id", "source_url", "source_page", "source_name", "source_mode",
    "source_purpose", "source_version", "source_category", "source_meta", "updated_at",
    "official_name", "official_condition", "match_method", "match_confidence",
    # Canonical relation metadata projected from relation JSON / SQLite.
    "choiceGroup", "choiceGroupSize", "isChoiceGroup", "relationGroup",
    "relationGroupSize", "relationType", "stageOrder",
}


def text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").replace("\u00a0", " ")).strip()


def normalized(value: Any) -> str:
    value = unicodedata.normalize("NFKC", text(value)).casefold()
    return re.sub(r"[\s\-—–_·・,，。.!！?？:：;；'\"「」『』【】()（）]+", "", value)


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def issue_fingerprint(kind: str, game_id: str, entity_ids: Iterable[str], evidence: Any) -> str:
    return stable_hash({
        "kind": kind,
        "game_id": game_id,
        "entities": sorted({text(v) for v in entity_ids if text(v)}),
        "evidence": evidence,
    })[:40]


def make_issue(
    game_id: str,
    kind: str,
    severity: str,
    risk: str,
    title: str,
    message: str,
    entity_ids: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
    suggested_actions: list[str] | None = None,
    progress_count: int = 0,
    relation_count: int = 0,
    auto_fixable: bool = False,
) -> dict[str, Any]:
    entity_ids = [text(v) for v in (entity_ids or []) if text(v)]
    evidence = evidence or {}
    fingerprint = issue_fingerprint(kind, game_id, entity_ids, evidence)
    actions = normalize_suggested_actions(suggested_actions)
    return {
        "fingerprint": fingerprint,
        "kind": kind,
        "severity": severity,
        "risk": risk,
        "title": title,
        "message": message,
        "entity_ids": entity_ids,
        "evidence": evidence,
        "suggested_actions": actions,
        "progress_count": int(progress_count or 0),
        "relation_count": int(relation_count or 0),
        "auto_fixable": bool(auto_fixable),
    }


def _item_id(item: dict[str, Any]) -> str:
    return text(item.get("id") or item.get("achievement_id"))


def _source_order(item: dict[str, Any]) -> int | None:
    value = item.get("source_order") if item.get("source_order") is not None else item.get("sourceOrder")
    try:
        return int(value)
    except Exception:
        return None


def _canonical_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "achievement_id": _item_id(item),
        "name": text(item.get("name")),
        "condition": text(item.get("condition")),
        "version": text(item.get("version")),
        "category": text(item.get("category")),
        "reward": item.get("reward"),
        "hidden": item.get("hidden"),
        "source": text(item.get("source")),
        "source_order": _source_order(item),
        "tags": item.get("tags") if isinstance(item.get("tags"), list) else [],
    }


def scan_governance(
    *,
    game_id: str,
    catalog_items: list[dict[str, Any]],
    database_items: list[dict[str, Any]],
    progress_rows: list[dict[str, Any]],
    relation_rows: list[dict[str, Any]],
    aliases: list[dict[str, Any]],
    overrides: list[dict[str, Any]],
    deleted_rows: list[dict[str, Any]],
    minimum_catalog_count: int = 1,
    similarity_threshold: float = 0.94,
    registered_fields: set[str] | None = None,
    identity_rows: list[dict[str, Any]] | None = None,
    source_id_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    registered_fields = {text(value) for value in (registered_fields or set()) if text(value)}
    effective_allowed_fields = ALLOWED_ITEM_FIELDS | registered_fields
    catalog_ids: list[str] = [_item_id(item) for item in catalog_items]
    catalog_id_set = {value for value in catalog_ids if value}
    progress_counts: dict[str, int] = defaultdict(int)
    for row in progress_rows:
        progress_counts[text(row.get("achievement_id"))] += 1
    relation_counts: dict[str, int] = defaultdict(int)
    for row in relation_rows:
        relation_counts[text(row.get("achievement_id"))] += 1
    identity_rows = identity_rows or []
    source_id_rows = source_id_rows or []

    # Basic field and type validation.
    id_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    exact_rows: dict[tuple[str, str], list[str]] = defaultdict(list)
    name_rows: dict[str, list[str]] = defaultdict(list)
    condition_rows: dict[str, list[str]] = defaultdict(list)
    order_rows: dict[int, list[str]] = defaultdict(list)
    source_ids: dict[str, list[str]] = defaultdict(list)
    unknown_field_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, item in enumerate(catalog_items, 1):
        achievement_id = _item_id(item)
        name = text(item.get("name"))
        condition = text(item.get("condition"))
        version = text(item.get("version"))
        category = text(item.get("category"))
        context = [achievement_id] if achievement_id else [f"row:{index}"]
        if not achievement_id:
            issues.append(make_issue(game_id, "missing_id", "error", "blocked", "缺少成就 ID", f"第 {index} 筆成就沒有 ID。", context, {"index": index}, ["manual_edit"], auto_fixable=False))
        if not name:
            issues.append(make_issue(game_id, "missing_name", "error", "blocked", "缺少成就名稱", f"第 {index} 筆成就沒有名稱。", context, {"index": index}, ["manual_edit"]))
        if not condition:
            issues.append(make_issue(game_id, "missing_condition", "warning", "needs_review", "缺少達成條件", f"成就 {achievement_id or index} 沒有達成條件。", context, {"index": index}, ["manual_edit", "source_fill", "ignore_once"]))
        if not version or version in {"未標示", "未辨識"}:
            issues.append(make_issue(game_id, "missing_version", "warning", "needs_review", "版本未辨識", f"成就 {achievement_id or index} 沒有可用版本。", context, {"index": index}, ["manual_edit", "source_fill", "ignore_once"]))
        elif not re.fullmatch(r"\d+(?:\.\d+){0,3}|未標示|未辨識", version):
            issues.append(make_issue(game_id, "invalid_version", "warning", "needs_review", "版本格式異常", f"版本「{version}」不符合預期格式。", context, {"version": version}, ["manual_edit", "ignore_once"]))
        if not category or category == "未辨識分類":
            issues.append(make_issue(game_id, "missing_category", "warning", "needs_review", "分類未辨識", f"成就 {achievement_id or index} 沒有可用分類。", context, {"index": index}, ["manual_edit", "source_fill", "ignore_once"]))
        try:
            reward = int(item.get("reward", 0))
            if reward < 0 or reward > 100000:
                raise ValueError
        except Exception:
            issues.append(make_issue(game_id, "invalid_reward", "error", "blocked", "獎勵數值異常", f"成就 {achievement_id or index} 的獎勵不是合法數值。", context, {"reward": item.get("reward")}, ["manual_edit"]))
        if not isinstance(item.get("hidden", False), bool):
            issues.append(make_issue(game_id, "invalid_hidden", "warning", "needs_review", "隱藏狀態格式異常", f"成就 {achievement_id or index} 的 hidden 不是布林值。", context, {"hidden": item.get("hidden")}, ["normalize_hidden", "manual_edit"], auto_fixable=True))
        if item.get("tags") is not None and not isinstance(item.get("tags"), list):
            issues.append(make_issue(game_id, "invalid_tags", "warning", "needs_review", "標籤格式異常", f"成就 {achievement_id or index} 的標籤不是陣列。", context, {"tags": item.get("tags")}, ["normalize_tags", "manual_edit"], auto_fixable=True))
        unknown = sorted(set(item) - effective_allowed_fields)
        for field in unknown:
            rows = unknown_field_rows[field]
            if len(rows) < 20:
                rows.append({
                    "achievement_id": achievement_id or f"row:{index}",
                    "name": name,
                    "value": item.get(field),
                })
            # Store an occurrence marker after the sample limit without copying large values.
            elif len(rows) == 20:
                rows.append({"achievement_id": "__more__", "name": "", "value": None})
        if achievement_id:
            id_rows[achievement_id].append(item)
        if name and condition and achievement_id:
            exact_rows[(normalized(name), normalized(condition))].append(achievement_id)
        if name and achievement_id:
            name_rows[normalized(name)].append(achievement_id)
        if condition and achievement_id:
            condition_rows[normalized(condition)].append(achievement_id)
        order = _source_order(item)
        if order is None:
            issues.append(make_issue(game_id, "missing_order", "warning", "needs_review", "排序值缺少或無效", f"成就 {achievement_id or index} 沒有合法排序值。", context, {"source_order": item.get("sourceOrder", item.get("source_order"))}, ["recalculate_order", "manual_edit"], auto_fixable=True))
        else:
            order_rows[order].append(achievement_id)
        sid = text(item.get("source_id") or item.get("official_id"))
        if sid and achievement_id:
            source_ids[sid].append(achievement_id)

    # Unknown fields are reported once per field instead of once per achievement. This
    # prevents one remote metadata key from creating thousands of duplicate governance rows.
    for field in sorted(unknown_field_rows):
        occurrence_ids = [
            _item_id(item) or f"row:{index}"
            for index, item in enumerate(catalog_items, 1)
            if field in item
        ]
        samples = [row for row in unknown_field_rows[field] if row.get("achievement_id") != "__more__"]
        grouped_issue = make_issue(
            game_id,
            "unknown_field_group",
            "info",
            "needs_review",
            f"未登記欄位：{field}",
            f"欄位「{field}」出現在 {len(occurrence_ids)} 項成就；請先查看值範例，再決定登記、映射、保留或批次移除。",
            occurrence_ids[:100],
            {
                "field": field,
                "occurrence_count": len(occurrence_ids),
                "sample_items": samples,
                "entity_list_truncated": len(occurrence_ids) > 100,
                "classification": "unregistered",
            },
            ["register_field", "map_unknown_field", "keep_unknown_field", "remove_unknown_fields", "review"],
            sum(progress_counts[aid] for aid in occurrence_ids),
            sum(relation_counts[aid] for aid in occurrence_ids),
        )
        # The issue identity is field-level. Samples and occurrence counts remain evidence,
        # but do not create a brand-new issue whenever one achievement value changes.
        grouped_issue["fingerprint"] = issue_fingerprint("unknown_field_group", game_id, [field], {"field": field})
        issues.append(grouped_issue)

    if len(catalog_items) < max(1, int(minimum_catalog_count or 1)):
        issues.append(make_issue(game_id, "catalog_count_below_minimum", "error", "blocked", "成就總數低於安全門檻", f"目前 {len(catalog_items)} 項，安全門檻為 {minimum_catalog_count} 項。", [], {"count": len(catalog_items), "minimum": minimum_catalog_count}, ["restore_backup", "resync_source"]))

    for achievement_id, rows in id_rows.items():
        if len(rows) > 1:
            issues.append(make_issue(game_id, "duplicate_id", "error", "blocked", "成就 ID 重複", f"ID {achievement_id} 出現 {len(rows)} 次。", [achievement_id], {"occurrences": len(rows)}, ["merge_fields", "keep_selected", "manual_edit"], progress_counts[achievement_id], relation_counts[achievement_id]))
    for key, ids in exact_rows.items():
        unique = list(dict.fromkeys(ids))
        if len(unique) > 1:
            issues.append(make_issue(game_id, "exact_duplicate", "warning", "needs_review", "名稱與條件完全重複", "多個不同 ID 的名稱與條件完全相同。", unique, {"normalized_name": key[0], "normalized_condition": key[1]}, ["merge_fields", "create_alias", "mark_legal_exception"], sum(progress_counts[x] for x in unique), sum(relation_counts[x] for x in unique)))
    for key, ids in name_rows.items():
        unique = list(dict.fromkeys(ids))
        if len(unique) > 1:
            conditions = {normalized(next((row.get("condition") for row in catalog_items if _item_id(row) == aid), "")) for aid in unique}
            if len(conditions) > 1:
                issues.append(make_issue(game_id, "same_name_different_condition", "info", "needs_review", "同名但條件不同", "可能為階段型、互斥型或官方刻意重名成就。", unique, {"normalized_name": key}, ["create_stage_group", "create_exclusive_group", "mark_legal_exception", "merge_fields"], sum(progress_counts[x] for x in unique), sum(relation_counts[x] for x in unique)))
    for key, ids in condition_rows.items():
        unique = list(dict.fromkeys(ids))
        if len(unique) > 1:
            names = {normalized(next((row.get("name") for row in catalog_items if _item_id(row) == aid), "")) for aid in unique}
            if len(names) > 1:
                issues.append(make_issue(game_id, "same_condition_different_name", "info", "needs_review", "條件相同但名稱不同", "可能是改名、翻譯差異或重複資料。", unique, {"normalized_condition": key}, ["merge_fields", "create_alias", "mark_legal_exception"], sum(progress_counts[x] for x in unique), sum(relation_counts[x] for x in unique)))
    for order, ids in order_rows.items():
        unique = [x for x in ids if x]
        if len(unique) > 1:
            issues.append(make_issue(game_id, "duplicate_order", "info", "needs_review", "排序值重複", f"排序值 {order} 被 {len(unique)} 項成就共用。", unique, {"source_order": order}, ["recalculate_order", "keep"], auto_fixable=True))
    for sid, ids in source_ids.items():
        unique = list(dict.fromkeys(ids))
        if len(unique) > 1:
            issues.append(make_issue(game_id, "duplicate_source_id", "error", "blocked", "官方來源 ID 重複", f"來源 ID {sid} 對應多個正式成就。", unique, {"source_id": sid}, ["merge_fields", "manual_edit"]))

    # Similar names in small buckets.
    buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for item in catalog_items:
        aid, n = _item_id(item), normalized(item.get("name"))
        if aid and len(n) >= 4:
            buckets[n[:1]].append((aid, n))
    for rows in buckets.values():
        if len(rows) > 350:
            continue
        for i, (left_id, left_name) in enumerate(rows):
            for right_id, right_name in rows[i + 1:]:
                if left_name == right_name:
                    continue
                ratio = SequenceMatcher(None, left_name, right_name).ratio()
                if ratio >= similarity_threshold:
                    issues.append(make_issue(game_id, "similar_name", "info", "needs_review", "名稱高度相似", f"名稱相似度 {ratio:.0%}，請確認是否為改名或重複。", [left_id, right_id], {"similarity": round(ratio, 4)}, ["merge_fields", "create_alias", "mark_legal_exception"], progress_counts[left_id] + progress_counts[right_id], relation_counts[left_id] + relation_counts[right_id]))

    # JSON and SQLite consistency.
    json_by_id = {_item_id(row): _canonical_item(row) for row in catalog_items if _item_id(row)}
    db_by_id = {text(row.get("achievement_id") or row.get("id")): _canonical_item(row) for row in database_items if text(row.get("achievement_id") or row.get("id"))}
    for aid in sorted(set(json_by_id) - set(db_by_id)):
        issues.append(make_issue(game_id, "json_only", "error", "blocked", "JSON 有資料但資料庫沒有", f"成就 {aid} 尚未寫入 SQLite。", [aid], {"json": json_by_id[aid]}, ["sync_json_to_database"], progress_counts[aid], relation_counts[aid], auto_fixable=True))
    for aid in sorted(set(db_by_id) - set(json_by_id)):
        issues.append(make_issue(game_id, "database_only", "error", "blocked", "資料庫有資料但 JSON 沒有", f"成就 {aid} 只存在 SQLite。", [aid], {"database": db_by_id[aid]}, ["sync_database_to_json", "archive_database_row"], progress_counts[aid], relation_counts[aid]))
    for aid in sorted(set(json_by_id) & set(db_by_id)):
        differences = {key: {"json": json_by_id[aid][key], "database": db_by_id[aid][key]} for key in json_by_id[aid] if json_by_id[aid][key] != db_by_id[aid].get(key)}
        if differences:
            issues.append(make_issue(game_id, "json_database_mismatch", "warning", "needs_review", "JSON 與資料庫內容不一致", f"成就 {aid} 有 {len(differences)} 個欄位不一致。", [aid], {"differences": differences}, ["sync_json_to_database", "sync_database_to_json", "manual_edit"], progress_counts[aid], relation_counts[aid]))

    # Progress and deletion consistency.
    for aid, count in progress_counts.items():
        if aid not in catalog_id_set:
            issues.append(make_issue(game_id, "orphan_progress", "error", "blocked", "使用者進度指向不存在成就", f"成就 ID {aid} 有 {count} 筆進度，但正式目錄不存在。", [aid], {"progress_count": count}, ["repair_historical_id", "transfer_progress", "restore_catalog_item", "keep_pending"], count, 0))
    deleted_ids = {text(row.get("achievement_id")) for row in deleted_rows}
    for aid in sorted(deleted_ids):
        if progress_counts.get(aid):
            issues.append(make_issue(game_id, "deleted_with_progress", "warning", "needs_review", "隱藏或刪除成就仍有完成進度", f"成就 {aid} 已標記刪除，但仍有 {progress_counts[aid]} 筆完成進度。", [aid], {"progress_count": progress_counts[aid]}, ["restore_catalog_item", "transfer_progress", "keep"], progress_counts[aid], relation_counts[aid]))

    # Permanent identity/source mappings must not outlive their formal catalog row.
    identity_ids = {text(row.get("internal_id")) for row in identity_rows if text(row.get("internal_id"))}
    source_rows_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_id_rows:
        source_rows_by_id[text(row.get("internal_id"))].append(dict(row))
    for row in identity_rows:
        aid = text(row.get("internal_id"))
        if aid and aid not in catalog_id_set:
            mappings = source_rows_by_id.get(aid, [])
            issues.append(make_issue(
                game_id, "orphan_identity", "error", "blocked",
                "永久身分指向不存在成就",
                f"永久身分 {aid} 已沒有正式成就列，但仍保留 {len(mappings)} 筆來源 ID 對照。",
                [aid], {"identity": dict(row), "source_id_count": len(mappings), "source_ids": mappings[:20]},
                ["delete_orphan_identity", "restore_catalog_item"], progress_counts[aid], relation_counts[aid],
            ))
    for aid, mappings in sorted(source_rows_by_id.items()):
        if aid and aid not in identity_ids:
            issues.append(make_issue(
                game_id, "orphan_source_mapping", "error", "blocked",
                "來源 ID 對照缺少永久身分",
                f"成就 {aid} 有 {len(mappings)} 筆來源 ID 對照，但永久身分不存在。",
                [aid], {"source_id_count": len(mappings), "source_ids": mappings[:20]},
                ["delete_orphan_source_mapping", "review"], progress_counts[aid], relation_counts[aid],
            ))

    # Relations.
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    membership: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for row in relation_rows:
        relation_type = text(row.get("relation_type") or "exclusive")
        group_id = text(row.get("group_id"))
        aid = text(row.get("achievement_id"))
        groups[(relation_type, group_id)].append(row)
        if aid:
            membership[aid].append((relation_type, group_id))
        if aid and aid not in catalog_id_set:
            issues.append(make_issue(game_id, "orphan_relation", "error", "blocked", "關聯指向不存在成就", f"群組 {group_id} 指向不存在的成就 {aid}。", [aid], {"relation_type": relation_type, "group_id": group_id}, ["remove_relation_member", "replace_relation_member"], progress_counts[aid], 1))
    for (relation_type, group_id), rows in groups.items():
        ids = [text(row.get("achievement_id")) for row in rows if text(row.get("achievement_id"))]
        if len(ids) < 2:
            issues.append(make_issue(game_id, "relation_too_small", "warning", "needs_review", "關聯群組成員不足", f"{relation_type} 群組 {group_id} 少於兩個成員。", ids, {"relation_type": relation_type, "group_id": group_id}, ["delete_relation_group", "add_relation_member"]))
        if len(ids) != len(set(ids)):
            issues.append(make_issue(game_id, "duplicate_relation_member", "warning", "needs_review", "關聯群組成員重複", f"群組 {group_id} 有重複成員。", ids, {"relation_type": relation_type, "group_id": group_id}, ["deduplicate_relation_group"], auto_fixable=True))
        if relation_type == "stage":
            orders = [int(row.get("stage_order") or 0) for row in rows]
            expected = list(range(1, len(rows) + 1))
            if sorted(orders) != expected:
                issues.append(make_issue(game_id, "invalid_stage_order", "warning", "needs_review", "階段順序不連續或重複", f"階段群組 {group_id} 的順序應為 1 到 {len(rows)}。", ids, {"group_id": group_id, "orders": orders}, ["normalize_stage_order"], relation_count=len(ids), auto_fixable=True))
    for aid, memberships in membership.items():
        stage_groups = sorted({group for typ, group in memberships if typ == "stage"})
        exclusive_groups = sorted({group for typ, group in memberships if typ == "exclusive"})
        if len(stage_groups) > 1 or len(exclusive_groups) > 1:
            issues.append(make_issue(game_id, "multiple_relation_groups", "warning", "needs_review", "成就同時屬於多個同類關聯群組", f"成就 {aid} 存在重複關聯歸屬。", [aid], {"stage_groups": stage_groups, "exclusive_groups": exclusive_groups}, ["choose_relation_group", "mark_legal_exception"], progress_counts[aid], len(memberships)))

    # Aliases.
    alias_map = {text(row.get("alias_id")): text(row.get("canonical_id")) for row in aliases if text(row.get("alias_id"))}
    for alias, canonical in alias_map.items():
        if alias == canonical:
            issues.append(make_issue(game_id, "alias_self_reference", "error", "blocked", "別名指向自己", f"別名 {alias} 指向自己。", [alias], {"canonical_id": canonical}, ["delete_alias"], progress_counts[alias]))
        if canonical not in catalog_id_set:
            issues.append(make_issue(game_id, "alias_dangling", "error", "blocked", "別名指向不存在成就", f"別名 {alias} 指向不存在的 {canonical}。", [alias, canonical], {"canonical_id": canonical}, ["repair_alias", "delete_alias"], progress_counts[alias]))
        visited: list[str] = []
        current = alias
        while current in alias_map and current not in visited:
            visited.append(current)
            current = alias_map[current]
        if current in visited:
            cycle = visited[visited.index(current):] + [current]
            issues.append(make_issue(game_id, "alias_cycle", "error", "blocked", "成就 ID 別名形成循環", " → ".join(cycle), cycle, {"cycle": cycle}, ["break_alias_cycle"]))
        elif len(visited) > 1:
            issues.append(make_issue(game_id, "alias_chain", "info", "needs_review", "成就 ID 別名尚未壓平", f"別名鏈長度為 {len(visited)}，可直接指向最終 ID {current}。", visited + [current], {"chain": visited + [current]}, ["flatten_alias_chain"], auto_fixable=True))
        if alias in catalog_id_set:
            issues.append(make_issue(game_id, "alias_source_still_exists", "warning", "needs_review", "別名來源 ID 仍存在正式目錄", f"{alias} 已是別名，但正式目錄仍保留同 ID 成就。", [alias, canonical], {"canonical_id": canonical}, ["merge_fields", "remove_alias", "mark_legal_exception"], progress_counts[alias], relation_counts[alias]))

    # Overrides referencing missing rows.
    for row in overrides:
        aid = text(row.get("achievement_id"))
        if aid and aid not in catalog_id_set:
            issues.append(make_issue(game_id, "orphan_override", "warning", "needs_review", "管理員修改指向不存在成就", f"管理員修改 {aid} 找不到正式成就。", [aid], {"override": dict(row)}, ["restore_catalog_item", "delete_override", "transfer_override"]))

    by_severity = {name: sum(1 for i in issues if i["severity"] == name) for name in ("error", "warning", "info")}
    by_risk = {name: sum(1 for i in issues if i["risk"] == name) for name in ("blocked", "needs_review", "safe")}
    by_kind: dict[str, int] = defaultdict(int)
    for issue in issues:
        by_kind[issue["kind"]] += 1
    return {
        "catalog_count": len(catalog_items),
        "database_count": len(database_items),
        "progress_count": len(progress_rows),
        "relation_count": len(relation_rows),
        "alias_count": len(aliases),
        "override_count": len(overrides),
        "issues": issues,
        "by_severity": by_severity,
        "by_risk": by_risk,
        "by_kind": dict(by_kind),
        "rule_count": 40,
    }


def summarize_plan(actions: list[dict[str, Any]], issues_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    affected_ids: set[str] = set()
    progress_count = 0
    relation_count = 0
    high_risk = 0
    for action in actions:
        issue = issues_by_id.get(str(action.get("issue_id") or ""), {})
        affected_ids.update(issue.get("entity_ids") or [])
        progress_count += int(issue.get("progress_count") or 0)
        relation_count += int(issue.get("relation_count") or 0)
        if str(action.get("action") or "") in HIGH_RISK_ACTIONS:
            high_risk += 1
    return {
        "action_count": len(actions),
        "affected_achievement_count": len(affected_ids),
        "affected_progress_count": progress_count,
        "affected_relation_count": relation_count,
        "high_risk_action_count": high_risk,
        "requires_confirmation": high_risk > 0,
        "confirmation_text": "CONFIRM GOVERNANCE" if high_risk > 0 else "",
    }
