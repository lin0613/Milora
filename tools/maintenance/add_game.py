from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "site/game-manifest.json"
TEMPLATE = ROOT / "site/_projects/game-template/index.html"


def load_items(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = value.get("items") if isinstance(value, dict) else value
    if not isinstance(rows, list) or not rows:
        raise ValueError("Catalog must contain a non-empty items list")
    ids = [str(row.get("id") or row.get("achievement_id") or "").strip() for row in rows if isinstance(row, dict)]
    if len(ids) != len(rows) or not all(ids) or len(ids) != len(set(ids)):
        raise ValueError("Catalog ids must be non-empty and unique")
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Register a new game using the shared catalog, API and frontend template")
    parser.add_argument("--id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--icon", required=True, type=Path)
    parser.add_argument("--point-label", default="點")
    parser.add_argument("--primary-name", default="Manual official source")
    parser.add_argument("--primary-url", default="")
    args = parser.parse_args()
    game_id = args.id.strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,39}", game_id):
        raise ValueError("Game id must be 2-40 lowercase ASCII characters")
    rows = load_items(args.catalog.resolve())
    if not args.icon.is_file():
        raise FileNotFoundError(args.icon)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    projects = manifest.setdefault("projects", [])
    if any(str(row.get("id")) == game_id for row in projects):
        raise ValueError(f"Game already exists: {game_id}")
    project = {
        "id": game_id,
        "name": args.name.strip(),
        "subtitle": "成就紀錄器",
        "route": f"/_projects/{game_id}/index.html",
        "enabled": True,
        "iconEndpoint": f"/assets/games/{game_id}/icon.png",
        "achievementPointLabel": args.point_label.strip() or "點",
        "minimumCatalogCount": len(rows),
        "catalogFile": f"data/catalogs/{game_id}/achievements.json",
        "relationsDir": f"data/relations/{game_id}",
        "features": {"hiddenAchievements": True, "relations": True, "officialSync": True},
        "sourcePolicy": {
            "preserveFields": ["version", "hidden", "category", "source_order"],
            "reviewOnConflict": True,
            "reviewOnRemoval": True,
            "protectProgress": True,
            "protectRelations": True,
            "primary": {"id": f"{game_id}_official", "name": args.primary_name, "url": args.primary_url, "role": "primary", "mode": "remote_reference", "purpose": "official_reference", "trustedFields": ["name", "condition", "version", "category", "reward", "hidden"]},
            "secondary": None,
            "fallback": {"id": "bundled_catalog", "name": "已驗證的本機目錄快照", "url": "", "role": "fallback", "mode": "local"},
        },
    }
    projects.append(project)
    manifest["schemaVersion"] = max(4, int(manifest.get("schemaVersion") or 0))
    catalog_dir = ROOT / "data/catalogs" / game_id
    relation_dir = ROOT / "data/relations" / game_id
    source_dir = ROOT / "data/sources" / game_id
    page_dir = ROOT / "site/_projects" / game_id
    icon_dir = ROOT / "site/assets/games" / game_id
    for folder in (catalog_dir, relation_dir, source_dir, page_dir, icon_dir):
        folder.mkdir(parents=True, exist_ok=False)
    payload = json.loads(args.catalog.read_text(encoding="utf-8-sig"))
    if isinstance(payload, list):
        payload = {"schema_version": 1, "game_id": game_id, "source": f"{game_id}-catalog", "count": len(payload), "items": payload}
    else:
        payload["game_id"] = game_id
        payload["count"] = len(rows)
    (catalog_dir / "achievements.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    empty = {"schema_version": 1, "game_id": game_id, "groups": []}
    for name in ("stage-groups.json", "exclusive-groups.json"):
        (relation_dir / name).write_text(json.dumps(empty, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (page_dir / "index.html").write_text(TEMPLATE.read_text(encoding="utf-8").replace('data-game-id="GAME_ID"', f'data-game-id="{game_id}"'), encoding="utf-8")
    shutil.copy2(args.icon, icon_dir / "icon.png")
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "game_id": game_id, "catalog_count": len(rows), "next": "Run init_db and verify_installation.cmd"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
