from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from backend.core.paths import PROJECTS_DIR, SITE_DIR

REGISTRY_FILE = SITE_DIR / "game-manifest.json"

_DEFAULT_PROJECTS: list[dict[str, Any]] = [
    {
        "id": "wuwa", "name": "鳴潮", "subtitle": "成就紀錄器", "route": "/_projects/wuwa/index.html",
        "enabled": True, "iconEndpoint": "", "achievementPointLabel": "星聲",
        "minimumCatalogCount": 800, "catalogFile": "data/catalogs/wuwa/achievements.json", "relationsDir": "data/relations/wuwa",
        "features": {"hiddenAchievements": True, "relations": True, "officialSync": True},
        "sourcePolicy": {
            "preserveFields": ["hidden", "category", "source_order", "raw"],
            "reviewOnConflict": True, "reviewOnRemoval": True, "protectProgress": True, "protectRelations": True,
            "primary": {"id": "ww_data", "name": "Arikatsu/WutheringWaves_Data（WW_Data）", "url": "https://github.com/Arikatsu/WutheringWaves_Data", "role": "primary", "mode": "remote_repository", "purpose": "official_catalog", "trustedFields": ["achievement_id", "name", "condition", "category", "reward", "hidden", "source_order", "level", "next_link"]},
            "secondary": {"id": "kuro_official_wiki", "name": "鳴潮既有官方來源", "url": "https://wiki.kurobbs.com/mc/item/1220879855033786368", "role": "secondary", "mode": "remote_reference", "purpose": "cross_validation", "trustedFields": ["version"]},
            "fallback": {"id": "verified_catalog_snapshot", "name": "目前正式目錄（僅供故障保護）", "url": "", "role": "fallback", "mode": "protected_snapshot", "automaticApply": False},
        },
    },
    {
        "id": "hsr", "name": "崩壞：星穹鐵道", "subtitle": "成就紀錄器", "route": "/_projects/hsr/index.html",
        "enabled": True, "iconEndpoint": "", "achievementPointLabel": "星瓊",
        "minimumCatalogCount": 1200, "catalogFile": "data/catalogs/hsr/achievements.json", "relationsDir": "data/relations/hsr",
        "features": {"hiddenAchievements": True, "relations": True, "officialSync": True},
        "sourcePolicy": {
            "preserveFields": ["hidden", "category", "source_order", "raw"],
            "reviewOnConflict": True, "reviewOnRemoval": True, "protectProgress": True, "protectRelations": True,
            "primary": {"id": "turn_based_game_data", "name": "Dimbreath/TurnBasedGameData", "url": "https://gitlab.com/Dimbreath/turnbasedgamedata", "role": "primary", "mode": "remote_repository", "purpose": "official_catalog", "trustedFields": ["achievement_id", "name", "condition", "category", "reward", "hidden", "source_order", "progress"]},
            "secondary": {"id": "stardb_hsr", "name": "StarDB 崩鐵成就資料", "url": "https://stardb.gg/zh-tw/achievement-tracker", "role": "secondary", "mode": "remote_reference", "purpose": "cross_validation", "trustedFields": ["version"]},
            "fallback": {"id": "verified_catalog_snapshot", "name": "目前正式目錄（僅供故障保護）", "url": "", "role": "fallback", "mode": "protected_snapshot", "automaticApply": False},
        },
    },
    {
        "id": "genshin", "name": "原神", "subtitle": "成就紀錄器", "route": "/_projects/genshin/index.html",
        "enabled": True, "iconEndpoint": "", "achievementPointLabel": "原石",
        "minimumCatalogCount": 1200, "catalogFile": "data/catalogs/genshin/achievements.json", "relationsDir": "data/relations/genshin",
        "features": {"hiddenAchievements": True, "relations": True, "officialSync": True},
        "sourcePolicy": {
            "preserveFields": ["hidden", "category", "source_order", "raw"],
            "reviewOnConflict": True, "reviewOnRemoval": True, "protectProgress": True, "protectRelations": True,
            "primary": {"id": "anime_game_data", "name": "Dimbreath/animegamedata2", "url": "https://gitlab.com/Dimbreath/animegamedata2", "role": "primary", "mode": "remote_repository", "purpose": "official_catalog", "trustedFields": ["achievement_id", "name", "condition", "category", "reward", "hidden", "source_order", "progress"]},
            "secondary": {"id": "stardb_genshin", "name": "StarDB 原神成就資料", "url": "https://stardb.gg/zh-tw/genshin/achievement-tracker", "role": "secondary", "mode": "remote_reference", "purpose": "cross_validation", "trustedFields": ["version"]},
            "fallback": {"id": "verified_catalog_snapshot", "name": "目前正式目錄（僅供故障保護）", "url": "", "role": "fallback", "mode": "protected_snapshot", "automaticApply": False},
        },
    },
    {
        "id": "zzz", "name": "絕區零", "subtitle": "成就紀錄器", "route": "/_projects/zzz/index.html",
        "enabled": True, "iconEndpoint": "", "achievementPointLabel": "菲林",
        "minimumCatalogCount": 600, "catalogFile": "data/catalogs/zzz/achievements.json", "relationsDir": "data/relations/zzz",
        "features": {"hiddenAchievements": True, "relations": True, "officialSync": True},
        "sourcePolicy": {
            "preserveFields": ["hidden", "category", "source_order", "raw"],
            "reviewOnConflict": True, "reviewOnRemoval": True, "protectProgress": True, "protectRelations": True,
            "primary": {"id": "zenless_data", "name": "Dimbreath/ZenlessData", "url": "https://git.mero.moe/dimbreath/ZenlessData", "role": "primary", "mode": "remote_repository", "purpose": "official_catalog", "trustedFields": ["achievement_id", "name", "condition", "category", "reward", "hidden", "source_order", "progress"]},
            "secondary": {"id": "stardb_zzz", "name": "StarDB 絕區零成就資料", "url": "https://stardb.gg/zh-tw/zzz/achievement-tracker", "role": "secondary", "mode": "remote_reference", "purpose": "cross_validation", "trustedFields": ["version"]},
            "fallback": {"id": "verified_catalog_snapshot", "name": "目前正式目錄（僅供故障保護）", "url": "", "role": "fallback", "mode": "protected_snapshot", "automaticApply": False},
        },
    },
    {
        "id": "hna", "name": "崩壞：因緣精靈", "subtitle": "成就紀錄器｜尚未開放", "route": "/_projects/hna/index.html",
        "enabled": False, "placeholder": True, "iconEndpoint": "",
        "features": {"placeholder": True, "officialSync": False},
    },
    {
        "id": "coming-soon", "name": "敬請期待", "subtitle": "", "route": "",
        "enabled": False, "iconEndpoint": "",
    },
]


def _merge_project(default: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(default)
    for key, value in custom.items():
        if key == "sourcePolicy" and isinstance(value, dict):
            policy = merged.setdefault("sourcePolicy", {})
            for source_key, source_value in value.items():
                policy[source_key] = source_value
        else:
            merged[key] = value
    return merged


def load_registry() -> dict[str, Any]:
    defaults = {row["id"]: deepcopy(row) for row in _DEFAULT_PROJECTS}
    try:
        value = json.loads(REGISTRY_FILE.read_text(encoding="utf-8-sig"))
        projects = value.get("projects") if isinstance(value, dict) else None
        if not isinstance(projects, list):
            raise ValueError("game-manifest.json is missing projects")
        merged_projects: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in projects:
            if not isinstance(row, dict):
                continue
            game_id = str(row.get("id") or "").strip()
            if not game_id:
                continue
            seen.add(game_id)
            merged_projects.append(_merge_project(defaults.get(game_id, {"id": game_id}), row))
        for game_id, row in defaults.items():
            if game_id not in seen:
                merged_projects.append(row)
        return {
            "schemaVersion": max(5, int(value.get("schemaVersion") or 0)),
            "defaultGame": str(value.get("defaultGame") or "wuwa"),
            "projects": merged_projects,
        }
    except Exception:
        return {
            "schemaVersion": 5,
            "defaultGame": "wuwa",
            "projects": [deepcopy(project) for project in _DEFAULT_PROJECTS],
        }


def enabled_projects() -> list[dict[str, Any]]:
    return [row for row in load_registry().get("projects", []) if row.get("enabled")]


def get_game_config(game_id: str) -> dict[str, Any] | None:
    value = str(game_id or "").strip()
    return next((row for row in enabled_projects() if str(row.get("id") or "") == value), None)


def get_project_route_config(project_id: str) -> dict[str, Any] | None:
    value = str(project_id or "").strip()
    if not value:
        return None
    for row in load_registry().get("projects", []):
        if str(row.get("id") or "").strip() == value and (row.get("enabled") or row.get("placeholder")):
            return row
    return None


def get_source_policy(game_id: str) -> dict[str, Any]:
    config = get_game_config(game_id) or {}
    policy = config.get("sourcePolicy")
    return deepcopy(policy) if isinstance(policy, dict) else {}


def resolve_game_index(game_id: str) -> Path | None:
    if not game_id or any(ch not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for ch in game_id):
        return None
    project = get_project_route_config(game_id)
    if not project:
        return None
    index_file = PROJECTS_DIR / game_id / "index.html"
    return index_file if index_file.exists() else None
