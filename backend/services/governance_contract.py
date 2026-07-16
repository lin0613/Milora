from __future__ import annotations

from typing import Any

# Single source of truth for every achievement-governance action exposed by the
# scanner, API and administrator UI.  Keeping the contract in one module stops
# the three layers from silently drifting apart again.
ACTION_SPECS: dict[str, dict[str, Any]] = {
    "keep": {"label": "保留目前資料（接受現況）", "risk": "none", "decision_only": True, "completion_type": "accepted_current"},
    "review": {"label": "送入待確認", "risk": "none", "decision_only": True, "completion_type": "pending_review"},
    "ignore_once": {"label": "本次忽略", "risk": "none", "decision_only": True, "completion_type": "ignored_once"},
    "keep_pending": {"label": "保留進度並待確認", "risk": "none", "decision_only": True, "completion_type": "pending_review"},
    "mark_legal_exception": {"label": "標記為合法例外", "risk": "normal", "decision_only": True, "completion_type": "legal_exception"},
    "manual_edit": {"label": "手動修正欄位", "risk": "normal"},
    "merge_fields": {"label": "合併為同一成就", "risk": "high"},
    "keep_selected": {"label": "保留指定成就並合併其餘項目", "risk": "high"},
    "create_alias": {"label": "建立 ID 別名", "risk": "normal"},
    "delete_alias": {"label": "刪除失效別名", "risk": "normal"},
    "remove_alias": {"label": "移除成就別名", "risk": "normal"},
    "break_alias_cycle": {"label": "中斷別名循環", "risk": "high"},
    "flatten_alias_chain": {"label": "壓平別名鏈", "risk": "normal"},
    "repair_alias": {"label": "修復別名指向", "risk": "normal"},
    "repair_historical_id": {"label": "修復歷史 ID", "risk": "high"},
    "transfer_progress": {"label": "轉移使用者進度", "risk": "high"},
    "delete_orphan_progress": {"label": "刪除孤立進度", "risk": "high"},
    "delete_orphan_identity": {"label": "刪除孤立永久身分", "risk": "normal"},
    "delete_orphan_source_mapping": {"label": "刪除孤立來源對照", "risk": "normal"},
    "recalculate_order": {"label": "依官方 ID 重新計算排序", "risk": "normal"},
    "normalize_hidden": {"label": "正規化隱藏狀態", "risk": "normal"},
    "normalize_tags": {"label": "正規化標籤", "risk": "normal"},
    "register_field": {"label": "登記為正式欄位", "risk": "normal"},
    "keep_unknown_field": {"label": "保留為來源中繼欄位", "risk": "normal"},
    "map_unknown_field": {"label": "映射到既有欄位", "risk": "high"},
    "remove_unknown_fields": {"label": "移除未登記欄位", "risk": "high"},
    "normalize_stage_order": {"label": "修正階段順序", "risk": "normal"},
    "deduplicate_relation_group": {"label": "移除關聯重複成員", "risk": "normal"},
    "delete_relation_group": {"label": "刪除無效關聯群組", "risk": "high"},
    "remove_relation_member": {"label": "移除無效關聯成員", "risk": "high"},
    "replace_relation_member": {"label": "替換關聯成員", "risk": "high"},
    "add_relation_member": {"label": "新增關聯成員", "risk": "normal"},
    "create_stage_group": {"label": "建立階段型關聯群組", "risk": "high"},
    "create_exclusive_group": {"label": "建立互斥型關聯群組", "risk": "high"},
    "choose_relation_group": {"label": "選擇唯一關聯群組", "risk": "high"},
    "delete_override": {"label": "刪除孤立管理員覆寫", "risk": "normal"},
    "transfer_override": {"label": "轉移管理員覆寫", "risk": "high"},
    "sync_json_to_database": {"label": "以 JSON 同步資料庫", "risk": "high"},
    "sync_database_to_json": {"label": "以資料庫重建 JSON", "risk": "high"},
    "archive_database_row": {"label": "封存僅存在資料庫的成就列", "risk": "high"},
    "restore_catalog_item": {"label": "恢復正式成就資料", "risk": "high"},
    "source_fill": {"label": "以已保存來源資料補齊欄位", "risk": "normal"},
    "resync_source": {"label": "轉交官方來源同步重新確認", "risk": "none", "decision_only": True, "completion_type": "pending_review"},
}

SUPPORTED_ACTIONS = frozenset(ACTION_SPECS)
HIGH_RISK_ACTIONS = frozenset(name for name, spec in ACTION_SPECS.items() if spec.get("risk") == "high")
DECISION_ONLY_ACTIONS = frozenset(name for name, spec in ACTION_SPECS.items() if spec.get("decision_only"))

# Old scanner actions that were never implemented are mapped to an explicit,
# supported path rather than being shown as an operation that will later fail.
ACTION_ALIASES = {
    "restore_backup": "review",
}


def canonical_action(name: Any) -> str:
    value = str(name or "").strip()
    value = ACTION_ALIASES.get(value, value)
    return value if value in SUPPORTED_ACTIONS else "review"


def normalize_suggested_actions(actions: list[Any] | tuple[Any, ...] | None) -> list[str]:
    normalized: list[str] = ["keep"]
    for raw in actions or ["review"]:
        action = canonical_action(raw)
        if action not in normalized:
            normalized.append(action)
    if len(normalized) == 1:
        normalized.append("review")
    return normalized


UNIVERSAL_DECISION_ACTIONS = frozenset({
    "keep", "review", "ignore_once", "mark_legal_exception",
})


def allowed_actions_for_issue(suggested_actions: list[Any] | tuple[Any, ...] | None) -> frozenset[str]:
    """Return the only actions the backend may accept for one issue.

    The scanner remains authoritative for data-changing operations. Universal
    decision-only actions are always available, but an arbitrary repair action
    can no longer be injected directly through the API.
    """
    normalized = {canonical_action(value) for value in (suggested_actions or [])}
    normalized.update(UNIVERSAL_DECISION_ACTIONS)
    return frozenset(value for value in normalized if value in SUPPORTED_ACTIONS)


def action_public_payload() -> dict[str, dict[str, Any]]:
    payload: dict[str, dict[str, Any]] = {}
    for name, spec in ACTION_SPECS.items():
        value = dict(spec)
        value.setdefault("completion_type", "verified_repair")
        payload[name] = value
    return payload
