from __future__ import annotations

import json
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Iterable

from backend.core.paths import (
    DATA_DIR,
    WUWA_CATALOG_FILE,
    WUWA_CHOICE_GROUPS_FILE,
    WUWA_STAGE_GROUPS_FILE,
    game_catalog_file,
)

from backend.services.catalog_sorting import catalog_sort_key

WUWA_OFFICIAL_ID_MIGRATION = "2026-06-26-wuwa-official-id-primary-key-v1"
OFFICIAL_ID_LIFECYCLE_REPAIR = "2026-06-26-official-id-lifecycle-fix-v1"
LEGACY_WUWA_ID_PATTERN = re.compile(r"成就-[0-9a-fA-F]+")
OFFICIAL_ID_PATTERN = re.compile(r"^[0-9]+$")
GAMES = ("wuwa", "hsr", "genshin", "zzz")




ACTIVE_WUWA_ID_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("game_catalog_items", "achievement_id", "game_id='wuwa'"),
    ("game_progress", "achievement_id", "game_id='wuwa'"),
    ("progress", "achievement_id", "1=1"),
    ("game_achievement_choice_groups", "achievement_id", "game_id='wuwa'"),
    ("game_achievement_overrides", "achievement_id", "game_id='wuwa'"),
    ("game_achievement_reports", "achievement_id", "game_id='wuwa'"),
    ("game_achievement_revisions", "achievement_id", "game_id='wuwa'"),
    ("game_deleted_achievements", "achievement_id", "game_id='wuwa'"),
    ("game_featured_achievements", "achievement_id", "game_id='wuwa'"),
    ("source_sync_decisions", "achievement_id", "game_id='wuwa'"),
    ("game_catalog_source_records", "achievement_id", "game_id='wuwa'"),
    ("game_catalog_source_records", "official_source_id", "game_id='wuwa'"),
    ("achievement_overrides", "achievement_id", "1=1"),
    ("achievement_reports", "achievement_id", "1=1"),
    ("achievement_revisions", "achievement_id", "1=1"),
    ("deleted_achievements", "achievement_id", "1=1"),
    ("featured_achievements", "achievement_id", "1=1"),
)

def sanitize_legacy_id_display(value: Any) -> Any:
    """Hide retired Wuwa hash IDs in administrator-facing historical text."""
    if not isinstance(value, str):
        return value
    return LEGACY_WUWA_ID_PATTERN.sub("舊站內 ID（已停用）", value)

def _legacy_active_reference_count(db: sqlite3.Connection) -> tuple[int, list[str]]:
    total = 0
    samples: list[str] = []
    for table, column, where in ACTIVE_WUWA_ID_COLUMNS:
        if not _table_exists(db, table):
            continue
        columns = {str(row[1]) for row in db.execute(f'pragma table_info("{table}")').fetchall()}
        if column not in columns:
            continue
        rows = db.execute(
            f'select "{column}" from "{table}" where ({where}) and "{column}" like ?',
            ("%成就-%",),
        ).fetchall()
        total += len(rows)
        for row in rows[: max(0, 5 - len(samples))]:
            samples.append(f"{table}.{column}={row[0]}")
    return total, samples

def repair_official_id_lifecycle_artifacts(db: sqlite3.Connection, timestamp: int) -> dict[str, Any]:
    """Repair compatibility artifacts left after the 1.7.0 official-ID migration.

    Historical prose may mention a retired hash ID, but it must never block startup.
    Saved previews are executable state, so previews containing a retired identifier
    are invalidated. Remaining historical prose is anonymized for display and search.
    """
    preview_deleted = 0
    scan_preview_deleted = 0
    if _table_exists(db, "game_sync_previews"):
        preview_deleted = int(db.execute(
            """delete from game_sync_previews
            where game_id='wuwa' and (candidate_json like ? or source_payload_json like ? or metadata_json like ? or diff_json like ?)""",
            ("%成就-%",) * 4,
        ).rowcount or 0)
    if _table_exists(db, "catalog_scan_previews"):
        scan_preview_deleted = int(db.execute(
            "delete from catalog_scan_previews where game_id='wuwa' and (items_json like ? or result_json like ?)",
            ("%成就-%", "%成就-%"),
        ).rowcount or 0)

    # The migration is idempotent. It deliberately sanitizes historical prose only
    # after executable preview state has been invalidated.
    text_cells_rewritten = _replace_all_legacy_text_in_database(db, {})
    file_cleanup = _migrate_wuwa_files({})
    active_count, samples = _legacy_active_reference_count(db)
    if active_count:
        raise RuntimeError(
            f"鳴潮仍有 {active_count} 個現行資料欄位使用舊站內 ID。範例：{', '.join(samples)}"
        )
    details = {
        "preview_deleted": preview_deleted,
        "scan_preview_deleted": scan_preview_deleted,
        "historical_text_cells_rewritten": text_cells_rewritten,
        "file_cleanup": file_cleanup,
        "active_legacy_reference_count": active_count,
    }
    if _table_exists(db, "schema_migrations"):
        db.execute(
            "insert or replace into schema_migrations(name,applied_at,details_json) values(?,?,?)",
            (OFFICIAL_ID_LIFECYCLE_REPAIR, timestamp, json.dumps(details, ensure_ascii=False)),
        )
    return details


def official_id_number(value: Any) -> int:
    text = str(value or "").strip()
    if not OFFICIAL_ID_PATTERN.fullmatch(text):
        raise ValueError(f"官方成就 ID 必須是純數字：{text or '空白'}")
    return int(text)


def official_id_sort_key(value: Any) -> tuple[int, str]:
    text = str(value or "").strip()
    return official_id_number(text), text


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _json_write_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + f".{os.getpid()}.{uuid.uuid4().hex}.tmp-official-id")
    try:
        temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def _cache_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("rows", "items", "achievements", "records"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, dict)]
    return []


def _add_mapping(mapping: dict[str, str], reverse: dict[str, str], legacy: Any, official: Any, basis: str) -> None:
    old = str(legacy or "").strip()
    new = str(official or "").strip()
    if not LEGACY_WUWA_ID_PATTERN.fullmatch(old) or not OFFICIAL_ID_PATTERN.fullmatch(new):
        return
    previous = mapping.get(old)
    if previous and previous != new:
        raise RuntimeError(f"鳴潮舊 ID 對應衝突：{old} 同時對應 {previous} 與 {new}（{basis}）。")
    reverse_old = reverse.get(new)
    if reverse_old and reverse_old != old:
        raise RuntimeError(f"鳴潮官方 ID 對應衝突：{new} 同時對應 {reverse_old} 與 {old}（{basis}）。")
    mapping[old] = new
    reverse[new] = old


def load_wuwa_legacy_to_official_map(db: sqlite3.Connection) -> dict[str, str]:
    """Build the one-time legacy-to-official mapping from existing verified evidence.

    No permanent migration map is shipped.  The old repository cache already stores
    the one-to-one identity evidence produced by the previous release.  The updater
    consumes that evidence once, validates total coverage, migrates every reference,
    and then removes the legacy identity evidence from active files and tables.
    """
    mapping: dict[str, str] = {}
    reverse: dict[str, str] = {}

    cache_path = DATA_DIR / "sources" / "wuwa" / "repository-primary-cache.json"
    if cache_path.exists():
        payload = _json_load(cache_path)
        for row in _cache_rows(payload):
            official = row.get("achievement_id") or row.get("id")
            provenance = row.get("provenance_json")
            if isinstance(provenance, str):
                try:
                    provenance = json.loads(provenance or "{}")
                except json.JSONDecodeError:
                    provenance = {}
            if not isinstance(provenance, dict):
                provenance = {}
            bridge = provenance.get("identity_bridge") if isinstance(provenance.get("identity_bridge"), dict) else {}
            _add_mapping(mapping, reverse, bridge.get("legacy_id"), official, "repository_cache")
            _add_mapping(mapping, reverse, row.get("internal_id") or row.get("_auxiliary_achievement_id"), official, "repository_row")

    # Existing confirmed mappings provide an additional independent source for rows
    # that were already re-keyed by the previous hotfix.
    if _table_exists(db, "achievement_source_ids"):
        for row in db.execute(
            "select source_id,internal_id from achievement_source_ids where game_id='wuwa' and source_name='ww_data'"
        ).fetchall():
            _add_mapping(mapping, reverse, row["internal_id"], row["source_id"], "database_source_mapping")

    if _table_exists(db, "game_catalog_source_records"):
        for row in db.execute(
            "select achievement_id,official_source_id from game_catalog_source_records where game_id='wuwa'"
        ).fetchall():
            _add_mapping(mapping, reverse, row["achievement_id"], row["official_source_id"], "catalog_source_record")

    # A saved preview may contain the final official ID even when an older cache was
    # partially written.  Only numeric IDs are accepted and all mappings remain one-to-one.
    if _table_exists(db, "game_sync_previews"):
        for row in db.execute("select candidate_json from game_sync_previews where game_id='wuwa'").fetchall():
            try:
                candidates = json.loads(row["candidate_json"] or "[]")
            except json.JSONDecodeError:
                continue
            for candidate in candidates if isinstance(candidates, list) else []:
                if not isinstance(candidate, dict):
                    continue
                _add_mapping(
                    mapping,
                    reverse,
                    candidate.get("internal_id") or candidate.get("achievement_id"),
                    candidate.get("official_source_id"),
                    "saved_preview",
                )

    # Historical aliases are not retained after migration, but their old IDs may
    # still appear in progress or audit snapshots.  Resolve them through the current
    # canonical row so every legacy token can be removed safely.
    if _table_exists(db, "achievement_id_aliases"):
        aliases = db.execute(
            "select alias_id,canonical_id from achievement_id_aliases where game_id='wuwa'"
        ).fetchall()
        for row in aliases:
            canonical = str(row["canonical_id"] or "")
            official = mapping.get(canonical)
            if official:
                mapping[str(row["alias_id"])] = official

    return mapping


def _table_exists(db: sqlite3.Connection, table: str) -> bool:
    return db.execute("select 1 from sqlite_master where type='table' and name=?", (table,)).fetchone() is not None


def _replace_legacy_text(value: str, mapping: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        # Any historical token that is not a live achievement ID is intentionally
        # anonymized.  It cannot remain an active identifier after this migration.
        return mapping.get(match.group(0), "已移除舊站內ID")

    return LEGACY_WUWA_ID_PATTERN.sub(repl, value)


def _sanitize_json_value(value: Any, mapping: dict[str, str], *, remove_identity_evidence: bool = False) -> Any:
    if isinstance(value, list):
        return [_sanitize_json_value(item, mapping, remove_identity_evidence=remove_identity_evidence) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        dropped = {
            "legacy_combined_id",
            "legacy_id",
            "internal_id",
            "internalId",
            "identity_bridge",
            "identityMatchStatus",
            "identityMatchBasis",
            "identityMatchConfidence",
            "_auxiliary_achievement_id",
            "_auxiliary_match_method",
            "_auxiliary_match_confidence",
        }
        for key, item in value.items():
            if remove_identity_evidence and str(key) in dropped:
                continue
            new_key = _replace_legacy_text(str(key), mapping)
            result[new_key] = _sanitize_json_value(item, mapping, remove_identity_evidence=remove_identity_evidence)
        return result
    if isinstance(value, str):
        return _replace_legacy_text(value, mapping)
    return value


def _snapshot_files(paths: Iterable[Path]) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in paths if path.exists() and path.is_file()}


def _restore_files(snapshot: dict[Path, bytes]) -> None:
    for path, content in snapshot.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)


def _migrate_wuwa_files(mapping: dict[str, str]) -> dict[str, int]:
    paths = [WUWA_CATALOG_FILE, WUWA_STAGE_GROUPS_FILE, WUWA_CHOICE_GROUPS_FILE]
    source_dir = DATA_DIR / "sources" / "wuwa"
    if source_dir.exists():
        paths.extend(path for path in source_dir.rglob("*") if path.is_file() and path.suffix.casefold() in {".json", ".tsv", ".txt"})
    snapshots = _snapshot_files(paths)
    changed = 0
    try:
        if WUWA_CATALOG_FILE.exists():
            payload = _json_load(WUWA_CATALOG_FILE)
            items = payload.get("items") if isinstance(payload, dict) else payload
            if not isinstance(items, list):
                raise RuntimeError("鳴潮正式目錄缺少 items，無法執行官方 ID 遷移。")
            seen: set[str] = set()
            for item in items:
                if not isinstance(item, dict):
                    continue
                old = str(item.get("id") or item.get("achievement_id") or "").strip()
                new = mapping.get(old, old)
                official_id_number(new)
                if new in seen:
                    raise RuntimeError(f"鳴潮官方 ID 重複：{new}")
                seen.add(new)
                item["id"] = new
                item.pop("achievement_id", None)
                item["officialId"] = new
                item["sourceOrder"] = int(new)
                details = item.get("sourceDetails")
                if isinstance(details, dict):
                    details = _sanitize_json_value(details, mapping, remove_identity_evidence=True)
                    details["officialId"] = new
                    details["primary"] = "ww_data"
                    item["sourceDetails"] = details
            items.sort(key=lambda row: official_id_sort_key(row.get("id") if isinstance(row, dict) else ""))
            payload = _sanitize_json_value(payload, mapping, remove_identity_evidence=True)
            _json_write_atomic(WUWA_CATALOG_FILE, payload)
            changed += 1

        for relation_path in (WUWA_STAGE_GROUPS_FILE, WUWA_CHOICE_GROUPS_FILE):
            if not relation_path.exists():
                continue
            payload = _sanitize_json_value(_json_load(relation_path), mapping, remove_identity_evidence=True)
            groups = payload.get("groups") if isinstance(payload, dict) else None
            if not isinstance(groups, list):
                raise RuntimeError(f"鳴潮關聯檔格式錯誤：{relation_path.name}")
            for group in groups:
                if not isinstance(group, dict):
                    continue
                ids = [str(value).strip() for value in group.get("achievement_ids") or []]
                if any(not OFFICIAL_ID_PATTERN.fullmatch(value) for value in ids):
                    raise RuntimeError(f"鳴潮關聯群組仍包含非官方 ID：{group.get('id')}")
                group["achievement_ids"] = ids
            _json_write_atomic(relation_path, payload)
            changed += 1

        if source_dir.exists():
            for path in sorted(source_dir.rglob("*")):
                if not path.is_file() or path in {WUWA_CATALOG_FILE, WUWA_STAGE_GROUPS_FILE, WUWA_CHOICE_GROUPS_FILE}:
                    continue
                if path.suffix.casefold() == ".json":
                    payload = _sanitize_json_value(_json_load(path), mapping, remove_identity_evidence=True)
                    if path.name == "repository-primary-cache.json" and isinstance(payload, dict):
                        rows = payload.get("rows")
                        if isinstance(rows, list):
                            for row in rows:
                                if not isinstance(row, dict):
                                    continue
                                official = str(row.get("achievement_id") or row.get("id") or "").strip()
                                if OFFICIAL_ID_PATTERN.fullmatch(official):
                                    row["source_order"] = int(official)
                                    row.pop("internal_id", None)
                    _json_write_atomic(path, payload)
                    changed += 1
                elif path.suffix.casefold() in {".tsv", ".txt"}:
                    text = _replace_legacy_text(path.read_text(encoding="utf-8-sig", errors="replace"), mapping)
                    path.write_text(text, encoding="utf-8")
                    changed += 1
    except Exception:
        _restore_files(snapshots)
        raise
    return {"files_rewritten": changed, "files_snapshotted": len(snapshots)}


def _update_id_column(db: sqlite3.Connection, table: str, column: str, mapping: dict[str, str], where: str = "", params: tuple[Any, ...] = ()) -> int:
    if not _table_exists(db, table):
        return 0
    changed = 0
    suffix = f" where {where}" if where else ""
    rows = db.execute(f'select rowid as _migration_rowid,"{column}" from "{table}"{suffix}', params).fetchall()
    for row in rows:
        old = str(row[column] or "")
        new = mapping.get(old)
        if new and new != old:
            db.execute(f'update "{table}" set "{column}"=? where rowid=?', (new, row["_migration_rowid"]))
            changed += 1
    return changed


def _migrate_progress_table(db: sqlite3.Connection, table: str, mapping: dict[str, str], *, shared: bool) -> int:
    if not _table_exists(db, table):
        return 0
    clause = "where game_id='wuwa'" if shared else ""
    rows = db.execute(f"select user_id,achievement_id,completed_at from {table} {clause}").fetchall()
    changed = 0
    for row in rows:
        old = str(row["achievement_id"] or "")
        new = mapping.get(old)
        if not new or new == old:
            continue
        if shared:
            existing = db.execute(
                "select completed_at from game_progress where game_id='wuwa' and user_id=? and achievement_id=?",
                (row["user_id"], new),
            ).fetchone()
            if existing:
                completed = min(int(existing["completed_at"] or row["completed_at"] or 0), int(row["completed_at"] or existing["completed_at"] or 0))
                db.execute("update game_progress set completed_at=? where game_id='wuwa' and user_id=? and achievement_id=?", (completed, row["user_id"], new))
            else:
                db.execute("insert into game_progress(game_id,user_id,achievement_id,completed_at) values('wuwa',?,?,?)", (row["user_id"], new, row["completed_at"]))
            db.execute("delete from game_progress where game_id='wuwa' and user_id=? and achievement_id=?", (row["user_id"], old))
        else:
            existing = db.execute("select completed_at from progress where user_id=? and achievement_id=?", (row["user_id"], new)).fetchone()
            if existing:
                completed = min(int(existing["completed_at"] or row["completed_at"] or 0), int(row["completed_at"] or existing["completed_at"] or 0))
                db.execute("update progress set completed_at=? where user_id=? and achievement_id=?", (completed, row["user_id"], new))
            else:
                db.execute("insert into progress(user_id,achievement_id,completed_at) values(?,?,?)", (row["user_id"], new, row["completed_at"]))
            db.execute("delete from progress where user_id=? and achievement_id=?", (row["user_id"], old))
        changed += 1
    return changed


def _replace_all_legacy_text_in_database(db: sqlite3.Connection, mapping: dict[str, str]) -> int:
    changed = 0
    tables = [row[0] for row in db.execute("select name from sqlite_master where type='table' and name not like 'sqlite_%'").fetchall()]
    for table in tables:
        columns = [
            row[1]
            for row in db.execute(f'pragma table_info("{table}")').fetchall()
            if str(row[2] or "").upper().startswith(("TEXT", "CHAR", "VARCHAR")) or not str(row[2] or "")
        ]
        if not columns:
            continue
        select_cols = ",".join(f'"{column}"' for column in columns)
        try:
            rows = db.execute(f'select rowid as _migration_rowid,{select_cols} from "{table}"').fetchall()
        except sqlite3.OperationalError:
            continue
        for row in rows:
            updates: dict[str, str] = {}
            for column in columns:
                value = row[column]
                if not isinstance(value, str) or "成就-" not in value:
                    continue
                replacement = _replace_legacy_text(value, mapping)
                if replacement != value:
                    updates[column] = replacement
            if not updates:
                continue
            assignments = ",".join(f'"{column}"=?' for column in updates)
            db.execute(f'update "{table}" set {assignments} where rowid=?', (*updates.values(), row["_migration_rowid"]))
            changed += len(updates)
    return changed


def migrate_wuwa_to_official_ids(db: sqlite3.Connection, timestamp: int) -> dict[str, Any]:
    """One-time migration from generated Wuwa IDs to WW_Data numeric IDs."""
    marker = db.execute("select details_json from schema_migrations where name=?", (WUWA_OFFICIAL_ID_MIGRATION,)).fetchone()
    current_ids = [str(row[0]) for row in db.execute("select achievement_id from game_catalog_items where game_id='wuwa'").fetchall()]
    if not current_ids:
        raise RuntimeError("鳴潮正式目錄為空，不能執行官方 ID 遷移。")
    old_ids = [value for value in current_ids if LEGACY_WUWA_ID_PATTERN.fullmatch(value)]
    official_ids = [value for value in current_ids if OFFICIAL_ID_PATTERN.fullmatch(value)]
    if len(old_ids) not in {0, len(current_ids)}:
        raise RuntimeError(f"鳴潮 ID 處於混合狀態：舊 ID {len(old_ids)}、官方 ID {len(official_ids)}。為避免重複，已停止遷移。")

    if old_ids:
        mapping = load_wuwa_legacy_to_official_map(db)
        missing = sorted(set(old_ids) - set(mapping))
        if missing:
            raise RuntimeError(f"鳴潮有 {len(missing)} 筆舊 ID 缺少 WW_Data 官方 ID；遷移已停止。範例：{', '.join(missing[:5])}")
        official_for_catalog = [mapping[value] for value in old_ids]
        if len(set(official_for_catalog)) != len(official_for_catalog):
            raise RuntimeError("鳴潮官方 ID 對應不是一對一，遷移已停止。")

        progress_before = int(db.execute("select count(*) from game_progress where game_id='wuwa'").fetchone()[0])
        relation_before = int(db.execute("select count(*) from game_achievement_choice_groups where game_id='wuwa'").fetchone()[0])
        catalog_before = len(current_ids)

        # Source records reference the catalog with a foreign key.  Snapshot and
        # remove them before changing the catalog primary key, then reinsert with
        # the official ID as both primary key and source ID.
        source_records = [dict(row) for row in db.execute("select * from game_catalog_source_records where game_id='wuwa'").fetchall()]
        db.execute("delete from game_catalog_source_records where game_id='wuwa'")

        for old in old_ids:
            new = mapping[old]
            db.execute(
                "update game_catalog_items set achievement_id=?,source_order=?,updated_at=? where game_id='wuwa' and achievement_id=?",
                (new, int(new), timestamp, old),
            )

        _migrate_progress_table(db, "game_progress", mapping, shared=True)
        _migrate_progress_table(db, "progress", mapping, shared=False)

        shared_tables = (
            "game_achievement_choice_groups",
            "game_achievement_overrides",
            "game_achievement_reports",
            "game_achievement_revisions",
            "game_deleted_achievements",
            "game_featured_achievements",
            "source_sync_decisions",
        )
        for table in shared_tables:
            _update_id_column(db, table, "achievement_id", mapping, "game_id='wuwa'")
        for table in ("achievement_overrides", "achievement_reports", "achievement_revisions", "deleted_achievements", "featured_achievements"):
            _update_id_column(db, table, "achievement_id", mapping)

        for row in source_records:
            old = str(row.get("achievement_id") or "")
            new = mapping.get(old, old)
            official_id_number(new)
            db.execute(
                """insert into game_catalog_source_records(
                game_id,achievement_id,category_id,group_id,group_name,progress_value,level,next_link,reward_id,
                primary_source_id,secondary_source_id,source_ref,raw_json,provenance_json,updated_at,official_source_id)
                values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    "wuwa", new, row.get("category_id") or "", row.get("group_id") or "", row.get("group_name") or "",
                    int(row.get("progress_value") or 0), int(row.get("level") or 0), row.get("next_link") or "",
                    row.get("reward_id") or "", row.get("primary_source_id") or "ww_data", row.get("secondary_source_id") or "",
                    row.get("source_ref") or "", _replace_legacy_text(str(row.get("raw_json") or "{}"), mapping),
                    _replace_legacy_text(str(row.get("provenance_json") or "{}"), mapping), timestamp, new,
                ),
            )

        # Major key migration invalidates pre-migration previews.  They are deleted
        # rather than translated so an administrator cannot accidentally apply a
        # decision created against the old key space.
        db.execute("delete from game_sync_previews where game_id='wuwa'")
        db.execute("delete from catalog_scan_previews where game_id='wuwa'")

        # Wuwa no longer participates in the internal identity bridge.  The official
        # numeric ID is now the catalog primary key and every business reference.
        db.execute("delete from achievement_source_ids where game_id='wuwa'")
        db.execute("delete from achievement_identities where game_id='wuwa'")
        db.execute("delete from achievement_id_aliases where game_id='wuwa'")

        text_cells = _replace_all_legacy_text_in_database(db, mapping)
        files = _migrate_wuwa_files(mapping)

        progress_after = int(db.execute("select count(*) from game_progress where game_id='wuwa'").fetchone()[0])
        relation_after = int(db.execute("select count(*) from game_achievement_choice_groups where game_id='wuwa'").fetchone()[0])
        catalog_after = int(db.execute("select count(*) from game_catalog_items where game_id='wuwa'").fetchone()[0])
        if (catalog_before, progress_before, relation_before) != (catalog_after, progress_after, relation_after):
            raise RuntimeError(
                "鳴潮官方 ID 遷移前後數量不一致："
                f"成就 {catalog_before}->{catalog_after}、進度 {progress_before}->{progress_after}、關聯 {relation_before}->{relation_after}。"
            )
        details = {
            "catalog_count": catalog_after,
            "progress_count": progress_after,
            "relation_count": relation_after,
            "mapped_count": len(old_ids),
            "legacy_identity_rows": 0,
            "legacy_alias_rows": 0,
            "text_cells_rewritten": text_cells,
            **files,
        }
        db.execute(
            "insert or replace into schema_migrations(name,applied_at,details_json) values(?,?,?)",
            (WUWA_OFFICIAL_ID_MIGRATION, timestamp, json.dumps(details, ensure_ascii=False)),
        )
        lifecycle = repair_official_id_lifecycle_artifacts(db, timestamp)
        return {"already_applied": False, **details, "lifecycle_repair": lifecycle}

    # Already migrated: enforce cleanup and verify that no bridge rows return on a
    # later startup.  This also handles full packages prepared with the new model.
    if len(official_ids) != len(current_ids):
        invalid = [value for value in current_ids if not OFFICIAL_ID_PATTERN.fullmatch(value)]
        raise RuntimeError(f"鳴潮正式目錄包含非官方 ID：{', '.join(invalid[:5])}")
    db.execute("delete from achievement_source_ids where game_id='wuwa'")
    db.execute("delete from achievement_identities where game_id='wuwa'")
    db.execute("delete from achievement_id_aliases where game_id='wuwa'")
    if not marker:
        details = {"catalog_count": len(current_ids), "mapped_count": 0, "already_official": True}
        db.execute(
            "insert into schema_migrations(name,applied_at,details_json) values(?,?,?)",
            (WUWA_OFFICIAL_ID_MIGRATION, timestamp, json.dumps(details, ensure_ascii=False)),
        )
    lifecycle = repair_official_id_lifecycle_artifacts(db, timestamp)
    return {"already_applied": True, "catalog_count": len(current_ids), "lifecycle_repair": lifecycle}


def normalize_all_game_official_order(db: sqlite3.Connection, timestamp: int) -> dict[str, int]:
    """Keep sourceOrder equal to the official numeric ID and normalize display order.

    ZZZ uses one display bucket before the numeric key: normal achievements first,
    arcade achievements second.  Other games remain pure numeric-ID order.
    """
    counts: dict[str, int] = {}
    for game_id in GAMES:
        rows = db.execute("select achievement_id from game_catalog_items where game_id=?", (game_id,)).fetchall()
        invalid = [str(row["achievement_id"]) for row in rows if not OFFICIAL_ID_PATTERN.fullmatch(str(row["achievement_id"] or ""))]
        if invalid:
            raise RuntimeError(f"{game_id} 有 {len(invalid)} 筆非數字官方 ID，不能建立正式排序。範例：{', '.join(invalid[:5])}")
        for row in rows:
            achievement_id = str(row["achievement_id"])
            db.execute(
                "update game_catalog_items set source_order=?,updated_at=? where game_id=? and achievement_id=? and source_order<>?",
                (int(achievement_id), timestamp, game_id, achievement_id, int(achievement_id)),
            )
        path = game_catalog_file(game_id)
        if path.exists():
            payload = _json_load(path)
            items = payload.get("items") if isinstance(payload, dict) else payload
            if not isinstance(items, list):
                raise RuntimeError(f"{game_id} 正式目錄缺少 items。")
            for item in items:
                if not isinstance(item, dict):
                    continue
                achievement_id = str(item.get("id") or item.get("achievement_id") or "").strip()
                official_id_number(achievement_id)
                item["sourceOrder"] = int(achievement_id)
            items.sort(key=lambda item: catalog_sort_key(game_id, item if isinstance(item, dict) else {}))
            _json_write_atomic(path, payload)
        counts[game_id] = len(rows)
    return counts


def verify_official_id_model(db: sqlite3.Connection) -> dict[str, Any]:
    result: dict[str, Any] = {"games": {}}
    for game_id in GAMES:
        rows = db.execute("select achievement_id,source_order from game_catalog_items where game_id=?", (game_id,)).fetchall()
        invalid = [str(row["achievement_id"]) for row in rows if not OFFICIAL_ID_PATTERN.fullmatch(str(row["achievement_id"] or ""))]
        order_mismatch = [str(row["achievement_id"]) for row in rows if OFFICIAL_ID_PATTERN.fullmatch(str(row["achievement_id"] or "")) and int(row["source_order"] or 0) != int(row["achievement_id"])]
        if invalid or order_mismatch:
            raise RuntimeError(f"{game_id} 官方 ID 模型驗證失敗：非數字 {len(invalid)}、排序不一致 {len(order_mismatch)}。")
        result["games"][game_id] = {"count": len(rows), "invalid_ids": 0, "order_mismatch": 0}

    legacy_db, legacy_samples = _legacy_active_reference_count(db)
    if legacy_db:
        raise RuntimeError(
            f"鳴潮仍有 {legacy_db} 個現行資料欄位使用舊站內 ID。範例：{', '.join(legacy_samples)}"
        )
    active_preview_legacy = 0
    if _table_exists(db, "game_sync_previews"):
        active_preview_legacy = int(db.execute(
            """select count(*) from game_sync_previews where game_id='wuwa'
            and (candidate_json like ? or source_payload_json like ? or metadata_json like ? or diff_json like ?)""",
            ("%成就-%",) * 4,
        ).fetchone()[0])
    if active_preview_legacy:
        raise RuntimeError(f"鳴潮仍有 {active_preview_legacy} 份舊 ID 同步預覽，必須先作廢。")
    for table in ("achievement_identities", "achievement_source_ids", "achievement_id_aliases"):
        if _table_exists(db, table):
            count = int(db.execute(f"select count(*) from {table} where game_id='wuwa'").fetchone()[0])
            if count:
                raise RuntimeError(f"鳴潮仍保留 {table} 身分橋接資料：{count} 筆。")
    result["wuwa_legacy_active_references"] = 0
    result["wuwa_legacy_preview_rows"] = 0
    result["wuwa_identity_bridge_rows"] = 0
    return result
