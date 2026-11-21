"""Reviewed completion inheritance for the two 行於未明 source IDs only.

Formal source rows are never deleted. Preview is read-only; apply must run in
the catalog transaction. Archived progress is audit data, not a restore source.
"""
import hashlib
import json
import sqlite3
import unicodedata

IDS = ("200141", "201541")
RULE = "wuwa-uncharted-200141-201541-v1"
TEMP_GROUP = "wuwa-stage-1790873290729"
SCHEMA = """
create table if not exists wuwa_duplicate_state(
 game_id text primary key check(game_id='wuwa'), payload_json text not null);
create table if not exists wuwa_duplicate_history(
 id integer primary key, game_id text not null check(game_id='wuwa'),
 created_at integer not null, actor_id text, action text not null,
 before_json text not null, after_json text not null, progress_json text not null);
"""


def digest(condition):
    value = " ".join(unicodedata.normalize("NFC", str(condition or "")).split())
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _dump(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load(db):
    try:
        row = db.execute("select payload_json from wuwa_duplicate_state where game_id='wuwa'").fetchone()
    except sqlite3.OperationalError as exc:
        # Read-only maintenance may inspect an old DB before startup upgrades it.
        # Never create tables or migrate progress as a side effect of a read.
        if str(exc) != "no such table: wuwa_duplicate_state":
            raise
        return None
    return json.loads(row[0]) if row else None


def state_hash(db):
    return hashlib.sha256(_dump(load(db)).encode("utf-8")).hexdigest()


def _pair(rows):
    return {str(row.get("achievement_id") or row.get("id")): dict(row)
            for row in rows if str(row.get("achievement_id") or row.get("id")) in IDS}


def aliases(db):
    state = load(db)
    return {aid: state["canonical"] for aid in IDS if aid != state["canonical"]} if state and state["mode"] == "merged" else {}


def _progress(db):
    return [dict(row) for row in db.execute(
        "select * from game_progress where game_id='wuwa' and achievement_id in (?,?) order by user_id,achievement_id", IDS)]


def _move(db, target):
    # Only current active progress is used: a user's later uncheck stays undone.
    rows = db.execute("select user_id,min(completed_at) completed_at from game_progress where game_id='wuwa' and achievement_id in (?,?) group by user_id", IDS).fetchall()
    db.execute("delete from game_progress where game_id='wuwa' and achievement_id in (?,?)", IDS)
    db.executemany("insert into game_progress(game_id,user_id,achievement_id,completed_at) values('wuwa',?,?,?)",
                   [(row["user_id"], target, row["completed_at"]) for row in rows])


def _save(db, before, after, progress, stamp, actor, action):
    db.execute("insert into wuwa_duplicate_history(game_id,created_at,actor_id,action,before_json,after_json,progress_json) values('wuwa',?,?,?,?,?,?)",
               (stamp, actor, action, _dump(before), _dump(after), _dump(progress)))
    db.execute("insert into wuwa_duplicate_state(game_id,payload_json) values('wuwa',?) on conflict(game_id) do update set payload_json=excluded.payload_json", (_dump(after),))


def initialize(db, rows, stamp):
    """One-time, exact reviewed baseline only. Restart never replays history."""
    if load(db):
        return False
    pair = _pair(rows)
    if set(pair) != set(IDS) or any(pair[aid].get("name") != "行於未明" or
            pair[aid].get("condition") != "在淒心域中見證心與玄方城的起始。" for aid in IDS):
        return False
    baseline = {aid: {"condition": pair[aid]["condition"], "name": pair[aid]["name"]} for aid in IDS}
    state = {"rule": RULE, "mode": "merged", "canonical": "201541", "baseline": baseline,
             "initial": baseline, "revision": 1,
             "routes": {aid + ":" + digest(pair[aid]["condition"]): "201541" for aid in IDS}}
    progress = _progress(db)
    _move(db, "201541")
    _save(db, None, state, progress, stamp, None, "initial_merge")
    return True


def plan(db, rows):
    state = load(db)
    if not state:
        return None
    pair = _pair(rows)
    if set(pair) != set(IDS) or any(not str(pair[aid].get("condition") or "").strip() for aid in IDS):
        return {"kind": "missing", "changed": [], "requires_choice": False}
    changed = [aid for aid in IDS if digest(pair[aid].get("condition")) != digest(state["baseline"][aid]["condition"])]
    same = digest(pair[IDS[0]].get("condition")) == digest(pair[IDS[1]].get("condition"))
    kind = "unchanged"
    target = state["canonical"]
    if changed:
        if state["mode"] == "split":
            kind = "independent"
        elif same:
            kind = "same_new_condition"
        elif len(changed) == 1:
            kind = "single_changed"
            target = next(aid for aid in IDS if aid not in changed)
        else:
            kind = "choose_inheritor"
            target = ""
    return {"rule": RULE, "kind": kind, "changed": changed, "target": target,
            "requires_choice": kind == "choose_inheritor",
            "options": [{"id": aid, "name": pair[aid].get("name", aid), "condition": pair[aid].get("condition", "")} for aid in IDS]}


def annotate(db, diff, candidate):
    proposed = plan(db, candidate)
    if not proposed or proposed["kind"] == "unchanged":
        return diff
    for change in diff.get("changes", []):
        if str(change.get("achievement_id")) not in IDS:
            continue
        change["completion_inheritance"] = proposed
        if proposed["changed"] and change.get("risk") != "blocked":
            change["risk"] = "needs_review"
            change["default_selected"] = False
            change.setdefault("reasons", []).append("行於未明條件變更：完成度須按已確認的繼承規則處理。")
    # Summary must reflect the reclassified rows, not leave a green safe count.
    for risk, key in (("confirmed", "confirmed"), ("needs_review", "needs_review"), ("blocked", "blocked")):
        if key in diff.get("summary", {}):
            diff["summary"][key] = sum(change.get("risk") == risk for change in diff["changes"])
    diff["summary"]["safe_default"] = sum(bool(change.get("default_selected")) for change in diff["changes"])
    return diff


def validate_apply(db, candidate, applied, decisions):
    proposed, actual = plan(db, candidate), plan(db, applied)
    if not actual:
        return ""
    if actual["kind"] == "missing":
        raise ValueError("行於未明兩筆來源 ID 及完整條件必須保留；不可透過同步刪除其中一筆或清空條件。")
    if proposed and len(proposed["changed"]) == 2 and actual["changed"] and set(actual["changed"]) != set(IDS):
        raise ValueError("行於未明兩筆條件同時更新，請一併套用兩筆條件，或兩筆都保留不變。")
    if not actual["requires_choice"]:
        return ""
    choices = {str(value.get("inherit_achievement_id") or "") for value in decisions.values() if value.get("inherit_achievement_id")}
    if len(choices) != 1 or not choices.issubset(set(IDS)):
        raise ValueError("行於未明兩筆均變成不同條件：請選擇 200141 或 201541 繼承原完成度；另一筆將取消完成。")
    return next(iter(choices))


def apply(db, rows, stamp, actor=None, inherit=""):
    state = load(db)
    proposed = plan(db, rows)
    if not proposed or proposed["kind"] == "unchanged":
        return proposed
    if proposed["kind"] == "missing":
        raise ValueError("行於未明來源缺少其中一筆，必須先人工處理。")
    if proposed["requires_choice"] and inherit not in IDS:
        raise ValueError("請由管理員選擇完成度繼承對象。")
    before = json.loads(_dump(state))
    progress = _progress(db)
    routes = state["routes"]
    if proposed["kind"] in {"single_changed", "choose_inheritor"}:
        target = inherit if proposed["requires_choice"] else proposed["target"]
        _move(db, target)
        routes = {key: target for key in routes}
        state["mode"], state["canonical"] = "split", target
    elif proposed["kind"] == "independent":
        changed = proposed["changed"]
        routes = {key: target for key, target in routes.items() if target not in changed}
        for aid in changed:
            db.execute("delete from game_progress where game_id='wuwa' and achievement_id=?", (aid,))
    pair = _pair(rows)
    state["baseline"] = {aid: {"name": pair[aid].get("name", aid), "condition": pair[aid].get("condition", "")} for aid in IDS}
    for aid in IDS:
        routes[aid + ":" + digest(pair[aid].get("condition"))] = state["canonical"] if state["mode"] == "merged" else aid
    state["routes"], state["revision"] = routes, state["revision"] + 1
    _save(db, before, state, progress, stamp, actor, proposed["kind"])
    return proposed


def import_ids(db, ids, fingerprints=None):
    state = load(db)
    if not state:
        return ids
    fingerprints = fingerprints or {}
    result = []
    for aid in ids:
        if aid not in IDS:
            result.append(aid)
            continue
        fingerprint = fingerprints.get(aid) or digest(state["initial"][aid]["condition"])
        target = state["routes"].get(aid + ":" + str(fingerprint))
        if not target:
            raise ValueError("備份的行於未明條件已失效；請移除此項後重新匯入，再自行勾選目前條件。")
        result.append(target)
    return list(dict.fromkeys(result))


def public_state(db):
    state = load(db)
    return {"aliases": aliases(db), "routes": state["routes"],
            "initialFingerprints": {aid: digest(state["initial"][aid]["condition"]) for aid in IDS}} if state else {"aliases": {}, "routes": {}, "initialFingerprints": {}}


def snapshot(db):
    return {"state": [dict(row) for row in db.execute("select * from wuwa_duplicate_state")],
            "history": [dict(row) for row in db.execute("select * from wuwa_duplicate_history order by id")], "progress": _progress(db)}


def restore(db, saved):
    for table, key in (("wuwa_duplicate_state", "state"), ("wuwa_duplicate_history", "history")):
        db.execute(f"delete from {table} where game_id='wuwa'")
        for row in saved[key]:
            columns = list(row)
            db.execute(f"insert into {table}({','.join(columns)}) values({','.join('?' for _ in columns)})", tuple(row.values()))
    db.execute("delete from game_progress where game_id='wuwa' and achievement_id in (?,?)", IDS)
    for row in saved["progress"]:
        db.execute("insert into game_progress(game_id,user_id,achievement_id,completed_at) values(?,?,?,?)",
                   tuple(row[key] for key in ("game_id", "user_id", "achievement_id", "completed_at")))
