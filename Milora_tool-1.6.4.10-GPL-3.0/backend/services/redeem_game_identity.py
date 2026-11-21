"""Transactional identity changes for redeem games, not achievement game IDs."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


SCHEMA_SQL = """create table if not exists redeem_game_aliases (
 old_game_id text primary key,
 game_id text not null references redeem_games(game_id) on delete cascade,
 identity_game_id text not null,
 created_at integer not null
)"""


class RenameError(ValueError):
    def __init__(self, message: str, status_code: int = 409):
        super().__init__(message)
        self.status_code = status_code


def alias_metadata(db: sqlite3.Connection, games: list[dict]) -> dict[str, str]:
    by_id = {game["game_id"]: game for game in games}
    for game in games:
        game["identity_game_id"] = game["game_id"]
    aliases = {}
    for row in db.execute("select * from redeem_game_aliases order by created_at,old_game_id"):
        if row["game_id"] in by_id:
            aliases[row["old_game_id"]] = row["game_id"]
            by_id[row["game_id"]]["identity_game_id"] = row["identity_game_id"]
    return aliases


def resolve_alias(db: sqlite3.Connection, game_id: str) -> str:
    row = db.execute("select game_id from redeem_game_aliases where old_game_id=?", (game_id,)).fetchone()
    return row["game_id"] if row else game_id


def _hash(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


def _key(value: str, old: str, new: str) -> str:
    game, separator, code = value.partition("|")
    return new + separator + code if separator and game == old else value


def _references(value, old: str, new: str):
    """Change typed identity fields only; never replace codes, rewards or prose."""
    if isinstance(value, list):
        return [_references(item, old, new) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in {"game_id", "default_game_id"} and item == old:
            result[key] = new
        elif key == "game_ids" and isinstance(item, list):
            result[key] = [new if game == old else game for game in item]
        elif key == "keys" and isinstance(item, list):
            result[key] = [_key(key_value, old, new) for key_value in item]
        else:
            result[key] = _references(item, old, new)
    return result


def _state(value: dict, old: str, new: str) -> dict:
    return {_key(key, old, new): _references(row, old, new) for key, row in value.items()}


def _batch_plans(db, old, new, state_reader, code_columns):
    linked = {row[0] for row in db.execute("select distinct batch_id from redeem_import_items where game_id=?", (old,))}
    plans = []
    for batch in db.execute("select * from redeem_import_batches"):
        relevant = batch["default_game_id"] == old or batch["id"] in linked
        try:
            originals = [json.loads(batch[field] or "{}") for field in ("summary_json", "plan_json", "snapshot_json")]
            if not all(isinstance(value, dict) for value in originals):
                raise ValueError("invalid import snapshot")
        except (ValueError, TypeError):
            if relevant:
                raise RenameError("相關匯入快照無法解析，已取消遊戲 ID 更名。") from None
            continue
        mapped = [_references(value, old, new) for value in originals]
        if not relevant and originals == mapped:
            continue
        summary, plan, snapshot = originals
        keys = list(plan.get("keys") or [])
        before = {str(row.get("game_id") or "") + "|" + str(row.get("code") or "").strip():
                  {column: row.get(column) for column in code_columns}
                  for row in snapshot.get("before") or []}
        pre_state = {key: before.get(key) for key in sorted(set(keys))}
        pre_hash = batch["pre_state_hash"]
        if pre_hash:
            if _hash(pre_state) != pre_hash:
                raise RenameError("相關匯入快照的安全指紋不一致，已取消遊戲 ID 更名。")
            pre_hash = _hash(_state(pre_state, old, new))
        post_hash = batch["post_state_hash"]
        if post_hash:
            current = state_reader(db, keys)
            # An already-stale rollback must stay stale, never rebaseline to current data.
            if _hash(current) == post_hash:
                post_hash = _hash(_state(current, old, new))
        plans.append((batch["id"], new if batch["default_game_id"] == old else batch["default_game_id"],
                      *[json.dumps(value, ensure_ascii=False) for value in mapped], pre_hash, post_hash))
    return plans


def _notification_link(link: str, old: str, new: str) -> str:
    parts = urlsplit(link)
    if parts.scheme or parts.netloc or parts.path not in {"/redeem", "/redeem/"}:
        return link
    query = parse_qsl(parts.query, keep_blank_values=True)
    mapped = [(key, new if key == "game" and value == old else value) for key, value in query]
    return urlunsplit(parts._replace(query=urlencode(mapped))) if query != mapped else link


def rename_game(db: sqlite3.Connection, old: str, new: str, *, stamp: int,
                state_reader, code_columns) -> dict[str, int]:
    """Use the caller's write transaction; exceptions must roll the whole operation back."""
    if not db.in_transaction or not db.execute("pragma foreign_keys").fetchone()[0]:
        raise RenameError("遊戲 ID 更名必須在外鍵保護的寫入交易內執行。")
    if not db.execute("select 1 from redeem_games where game_id=?", (old,)).fetchone():
        raise RenameError("找不到兌換碼遊戲，請重新整理。", 404)
    if old == new:
        return {}
    if db.execute("select 1 from redeem_games where game_id=?", (new,)).fetchone():
        raise RenameError("兌換碼遊戲 ID 已存在，請使用其他 ID。")
    alias = db.execute("select game_id from redeem_game_aliases where old_game_id=?", (new,)).fetchone()
    if alias and alias[0] != old:
        raise RenameError("此 ID 已保留給其他遊戲的舊連結，不能使用。")
    if db.execute("select 1 from manual_content_localizations where resource_type='redeem_game' and game_id=?", (new,)).fetchone():
        raise RenameError("目標 ID 已有翻譯資料，為避免覆蓋已取消更名。")
    allowed = {("redeem_servers", "game_id"), ("redeem_codes", "game_id"),
               ("redeem_notification_preferences", "game_id"), ("redeem_game_aliases", "game_id")}
    for table in db.execute("select name from sqlite_master where type='table'").fetchall():
        quoted = '"' + table[0].replace('"', '""') + '"'
        for foreign in db.execute("pragma foreign_key_list(" + quoted + ")"):
            if foreign[2] == "redeem_games" and (table[0], foreign[3]) not in allowed:
                raise RenameError("偵測到尚未支援的兌換碼遊戲關聯，更名已取消，請先更新維護程式。")
    identities = {row[0] for row in db.execute("select identity_game_id from redeem_game_aliases where game_id=?", (old,))}
    if len(identities) > 1:
        raise RenameError("遊戲舊 ID 對照不一致，已取消更名。")
    identity = next(iter(identities), old)
    batches = _batch_plans(db, old, new, state_reader, code_columns)
    messages = [(row["id"], _notification_link(row["link"] or "", old, new), row["link"])
                for row in db.execute("select id,link from message_center_items where item_type='notification' and link like '/redeem%'")]
    counts = {}
    db.execute("""insert into redeem_games(game_id,name,display_order,enabled,note,created_by,updated_by,created_at,updated_at)
                  select ?,name,display_order,enabled,note,created_by,updated_by,created_at,updated_at
                  from redeem_games where game_id=?""", (new, old))
    for table in ("redeem_servers", "redeem_codes", "redeem_notification_preferences", "redeem_notification_events"):
        counts[table] = db.execute("update " + table + " set game_id=? where game_id=?", (new, old)).rowcount
    counts["manual_content_localizations"] = db.execute("""update manual_content_localizations set game_id=?,resource_id=?
        where resource_type='redeem_game' and game_id=? and resource_id=?""", (new, new, old, old)).rowcount
    counts["redeem_import_batches"] = len(batches)
    for batch_id, default_id, summary, plan, snapshot, pre_hash, post_hash in batches:
        db.execute("""update redeem_import_batches set default_game_id=?,summary_json=?,plan_json=?,snapshot_json=?,
                   pre_state_hash=?,post_state_hash=? where id=?""", (default_id, summary, plan, snapshot, pre_hash, post_hash, batch_id))
        for item in db.execute("select * from redeem_import_items where batch_id=?", (batch_id,)).fetchall():
            try:
                candidate, before = [json.loads(item[key] or "{}") for key in ("candidate_json", "before_json")]
            except (ValueError, TypeError):
                raise RenameError("相關匯入明細無法解析，已取消更名。") from None
            db.execute("update redeem_import_items set game_id=?,candidate_json=?,before_json=? where id=?",
                       (new if item["game_id"] == old else item["game_id"],
                        json.dumps(_references(candidate, old, new), ensure_ascii=False),
                        json.dumps(_references(before, old, new), ensure_ascii=False), item["id"]))
    counts["notification_links"] = 0
    for identifier, new_link, previous_link in messages:
        if new_link != previous_link:
            db.execute("update message_center_items set link=? where id=?", (new_link, identifier))
            counts["notification_links"] += 1
    db.execute("delete from redeem_game_aliases where old_game_id=?", (new,))
    db.execute("update redeem_game_aliases set game_id=? where game_id=?", (new, old))
    db.execute("insert into redeem_game_aliases values(?,?,?,?)", (old, new, identity, stamp))
    db.execute("delete from redeem_games where game_id=?", (old,))
    if any(row[2] == "redeem_games" for row in db.execute("pragma foreign_key_check")):
        raise RenameError("兌換碼關聯驗證未通過，更名已取消。")
    return counts
