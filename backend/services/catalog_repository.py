from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable, Iterable

CatalogRow = dict[str, Any]
RowTransform = Callable[[dict[str, Any], int], dict[str, Any]]
RowsTransform = Callable[[list[CatalogRow]], list[CatalogRow]]
RowsValidator = Callable[[list[CatalogRow]], None]


def read_catalog_payload(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if not path.exists():
        return {}, []
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(payload, dict):
        raw = payload.get("items")
        metadata = dict(payload)
    elif isinstance(payload, list):
        raw = payload
        metadata = {}
    else:
        raise ValueError(f"Unsupported catalog payload: {path}")
    if not isinstance(raw, list):
        raise ValueError(f"Catalog payload is missing items: {path}")
    return metadata, [dict(item) for item in raw if isinstance(item, dict)]


def normalize_catalog_rows(
    path: Path,
    *,
    game_id: str,
    minimum_count: int,
    default_source: str,
    version_by_id: dict[str, str] | None = None,
    row_transform: RowTransform | None = None,
    rows_transform: RowsTransform | None = None,
    validator: RowsValidator | None = None,
    require_condition: bool = False,
) -> list[CatalogRow]:
    metadata, raw_rows = read_catalog_payload(path)
    payload_source = str(metadata.get("source") or "").strip()
    versions = version_by_id or {}
    rows: list[CatalogRow] = []
    for index, source in enumerate(raw_rows):
        item = row_transform(dict(source), index) if row_transform else dict(source)
        achievement_id = str(item.get("id") or item.get("achievement_id") or "").strip()
        if not achievement_id.isdigit():
            raise ValueError(f"{game_id} achievement id must be a numeric official id: {achievement_id or 'empty'}")
        name = str(item.get("title") or item.get("name") or "").strip()
        condition = str(item.get("condition") or item.get("description") or item.get("desc") or item.get("hide_desc") or "").strip()
        if not achievement_id or not name or (require_condition and not condition):
            continue
        try:
            reward = int(item.get("reward") or 0)
        except (TypeError, ValueError):
            reward = 0
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        rows.append(
            {
                "achievement_id": achievement_id,
                "name": name,
                "condition": condition,
                "version": str(item.get("version") or versions.get(achievement_id) or "未標示").strip(),
                "category": str(item.get("category") or "未辨識分類").strip(),
                "reward": reward,
                "hidden": 1 if item.get("hidden") or item.get("hide") else 0,
                "tags_json": json.dumps(tags, ensure_ascii=False),
                "source": str(item.get("source") or payload_source or default_source).strip(),
                "source_order": int(achievement_id),
            }
        )
    if rows_transform:
        rows = rows_transform(rows)
    if len(rows) < max(1, int(minimum_count)):
        raise ValueError(f"{game_id} catalog count is below safety threshold: {len(rows)} < {minimum_count}")
    if len({str(row["achievement_id"]) for row in rows}) != len(rows):
        raise ValueError(f"{game_id} catalog contains duplicate achievement ids")
    if validator:
        validator(rows)
    return rows


def replace_catalog_rows(
    db: sqlite3.Connection,
    *,
    game_id: str,
    rows: Iterable[CatalogRow],
    updated_at: int,
    preserve_sources: tuple[str, ...] = ("manual", "admin"),
) -> tuple[int, int]:
    values = list(rows)
    placeholders = ",".join("?" for _ in preserve_sources)
    db.execute(
        f"delete from game_catalog_items where game_id=? and lower(source) not in ({placeholders})",
        (game_id, *preserve_sources),
    )
    db.executemany(
        """insert into game_catalog_items(
            game_id,achievement_id,name,condition,version,category,reward,hidden,tags_json,source,source_order,updated_at
        ) values(?,?,?,?,?,?,?,?,?,?,?,?)
        on conflict(game_id,achievement_id) do nothing""",
        [
            (
                game_id,
                row["achievement_id"],
                row["name"],
                row["condition"],
                row["version"],
                row["category"],
                int(row.get("reward") or 0),
                1 if row.get("hidden") else 0,
                row.get("tags_json") or "[]",
                row.get("source") or "catalog",
                int(row.get("source_order") or 0),
                updated_at,
            )
            for row in values
        ],
    )
    return len(values), len({str(row["achievement_id"]) for row in values})
