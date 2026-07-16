from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Website
SITE_DIR = ROOT / "site"
PROJECTS_DIR = SITE_DIR / "_projects"
ASSETS_DIR = SITE_DIR / "assets"
GAME_ASSETS_DIR = ASSETS_DIR / "games"
HUB_INDEX = SITE_DIR / "index.html"
ACCOUNT_INDEX = PROJECTS_DIR / "account" / "index.html"
ADMIN_INDEX = PROJECTS_DIR / "admin" / "index.html"

# Runtime state
DATA_DIR = ROOT / "data"
LOG_DIR = ROOT / "logs"
BACKUP_DIR = ROOT / "backups"
OUTBOX_DIR = DATA_DIR / "outbox"

# Structured game data
CATALOGS_DIR = DATA_DIR / "catalogs"
RELATIONS_DIR = DATA_DIR / "relations"
SOURCES_DIR = DATA_DIR / "sources"
REPORTS_DIR = DATA_DIR / "reports"


def game_catalog_file(game_id: str) -> Path:
    return CATALOGS_DIR / game_id / "achievements.json"


def game_relation_file(game_id: str, relation_type: str) -> Path:
    filenames = {
        "stage": "stage-groups.json",
        "exclusive": "exclusive-groups.json",
    }
    try:
        filename = filenames[relation_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported relation type: {relation_type}") from exc
    return RELATIONS_DIR / game_id / filename


def game_source_dir(game_id: str) -> Path:
    return SOURCES_DIR / game_id



def game_icon_file(game_id: str) -> Path:
    return GAME_ASSETS_DIR / game_id / "icon.png"


# Canonical catalog paths
WUWA_CATALOG_FILE = game_catalog_file("wuwa")
HSR_CATALOG_FILE = game_catalog_file("hsr")
GENSHIN_CATALOG_FILE = game_catalog_file("genshin")
ZZZ_CATALOG_FILE = game_catalog_file("zzz")

# Canonical relation paths
WUWA_STAGE_GROUPS_FILE = game_relation_file("wuwa", "stage")
WUWA_CHOICE_GROUPS_FILE = game_relation_file("wuwa", "exclusive")
HSR_STAGE_GROUPS_FILE = game_relation_file("hsr", "stage")
HSR_CHOICE_GROUPS_FILE = game_relation_file("hsr", "exclusive")
GENSHIN_STAGE_GROUPS_FILE = game_relation_file("genshin", "stage")
GENSHIN_CHOICE_GROUPS_FILE = game_relation_file("genshin", "exclusive")
ZZZ_STAGE_GROUPS_FILE = game_relation_file("zzz", "stage")
ZZZ_CHOICE_GROUPS_FILE = game_relation_file("zzz", "exclusive")

# Wuthering Waves sources
WUWA_SOURCE_DIR = game_source_dir("wuwa")
CACHE_FILE = WUWA_SOURCE_DIR / "raw-official-achievements.json"
META_FILE = WUWA_SOURCE_DIR / "sync-info.json"
OFFICIAL_ZH_TW_FILE = WUWA_SOURCE_DIR / "official-zh-tw-text.json"
# Honkai: Star Rail sources
HSR_SOURCE_DIR = game_source_dir("hsr")
HSR_OFFICIAL_ORDER_FILE = HSR_SOURCE_DIR / "official-order.json"
HSR_OFFICIAL_REWARD_FILE = HSR_SOURCE_DIR / "official-rewards.json"
HSR_ACHIEVEMENTS_CACHE_FILE = HSR_SOURCE_DIR / "hoyowiki-official-achievements.json"
HSR_ACHIEVEMENTS_FALLBACK_CACHE_FILE = HSR_SOURCE_DIR / "field-fallback.json"
HSR_ACHIEVEMENTS_METADATA_CACHE_FILE = HSR_SOURCE_DIR / "achievement-metadata.json"
# Static game images. These are the single source of truth for every page/API.
GAME_ICON_FILES = {
    game_id: game_icon_file(game_id)
    for game_id in ("wuwa", "hsr", "genshin", "zzz", "hna")
}


def ensure_runtime_directories() -> None:
    for folder in (
        DATA_DIR,
        LOG_DIR,
        BACKUP_DIR,
        OUTBOX_DIR,
        CATALOGS_DIR,
        RELATIONS_DIR,
        SOURCES_DIR,
        REPORTS_DIR,
        GAME_ASSETS_DIR,
    ):
        folder.mkdir(parents=True, exist_ok=True)
