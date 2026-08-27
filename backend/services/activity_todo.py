from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from calendar import monthrange
from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SCHEMA_MIGRATION = "2026-08-22-activity-todo-core-v1"
SOURCE_OPERATIONS_MIGRATION = "2026-08-22-activity-source-operations-v1"
ADMIN_CONTROLS_MIGRATION = "2026-08-23-activity-admin-controls-v1"
SUPPORTED_CADENCES = {"daily", "weekly", "monthly", "once", "custom"}
SUPPORTED_SOURCE_TYPES = {"manual", "system", "event"}
EVENT_OVERRIDE_FIELDS = ("title", "summary", "category", "start_at", "end_at", "official_url", "image_url")
ACTIVITY_GAMES: tuple[dict[str, Any], ...] = (
    {"game_id": "genshin", "name": "原神", "display_order": 10, "icon_path": "/assets/games/genshin/icon.png"},
    {"game_id": "hsr", "name": "崩壞：星穹鐵道", "display_order": 20, "icon_path": "/assets/games/hsr/icon.png"},
    {"game_id": "zzz", "name": "絕區零", "display_order": 30, "icon_path": "/assets/games/zzz/icon.png"},
    {"game_id": "wuwa", "name": "鳴潮", "display_order": 40, "icon_path": "/assets/games/wuwa/icon.png"},
    {"game_id": "nte", "name": "異環", "display_order": 50, "icon_path": "/assets/games/nte/icon.png"},
    {"game_id": "endfield", "name": "終末地", "display_order": 60, "icon_path": "/assets/games/endfield/icon.png"},
)


def ensure_schema(db: sqlite3.Connection, stamp: int) -> None:
    db.executescript(
        """
        create table if not exists activity_games (
            game_id text primary key,
            name text not null,
            display_order integer not null default 0,
            timezone text not null default 'Asia/Taipei',
            daily_reset_minute integer not null default 240,
            weekly_reset_weekday integer not null default 0,
            weekly_reset_minute integer not null default 240,
            enabled integer not null default 1,
            icon_path text not null default '',
            created_at integer not null,
            updated_at integer not null,
            check(daily_reset_minute between 0 and 1439),
            check(weekly_reset_weekday between 0 and 6),
            check(weekly_reset_minute between 0 and 1439)
        );
        create table if not exists activity_sources (
            id text primary key,
            game_id text not null references activity_games(game_id) on delete cascade,
            name text not null,
            source_type text not null default 'official_web',
            official_url text not null default '',
            fetch_url text not null default '',
            language text not null default 'zh-TW',
            enabled integer not null default 1,
            auto_publish_safe integer not null default 1,
            last_attempt_at integer,
            last_success_at integer,
            last_error text not null default '',
            last_content_hash text not null default '',
            created_at integer not null,
            updated_at integer not null,
            unique(game_id,name)
        );
        create table if not exists activity_events (
            id text primary key,
            game_id text not null references activity_games(game_id) on delete restrict,
            source_id text references activity_sources(id) on delete set null,
            source_key text not null,
            title text not null,
            summary text not null default '',
            category text not null default '限時活動',
            start_at integer,
            end_at integer,
            official_url text not null default '',
            image_url text not null default '',
            language text not null default 'zh-TW',
            source_updated_at integer,
            content_hash text not null,
            published integer not null default 0,
            review_state text not null default 'pending',
            removed_at integer,
            created_at integer not null,
            updated_at integer not null,
            check(end_at is null or start_at is null or end_at >= start_at),
            check(review_state in ('pending','approved','rejected')),
            unique(game_id,source_id,source_key)
        );
        create table if not exists activity_tasks (
            id text primary key,
            owner_user_id text references users(id) on delete cascade,
            game_id text not null references activity_games(game_id) on delete restrict,
            event_id text references activity_events(id) on delete set null,
            title text not null,
            description text not null default '',
            cadence text not null,
            schedule_json text not null default '{}',
            due_at integer,
            source_type text not null default 'manual',
            enabled integer not null default 1,
            display_order integer not null default 0,
            deleted_at integer,
            created_at integer not null,
            updated_at integer not null,
            check(cadence in ('daily','weekly','monthly','once','custom')),
            check(source_type in ('manual','system','event'))
        );
        create table if not exists activity_task_completions (
            user_id text not null references users(id) on delete cascade,
            task_id text not null references activity_tasks(id) on delete cascade,
            period_key text not null,
            completed_at integer not null,
            updated_at integer not null,
            primary key(user_id,task_id,period_key)
        );
        create table if not exists activity_sync_runs (
            id text primary key,
            source_id text not null references activity_sources(id) on delete cascade,
            status text not null,
            fetched_count integer not null default 0,
            added_count integer not null default 0,
            updated_count integer not null default 0,
            removed_count integer not null default 0,
            conflict_count integer not null default 0,
            snapshot_json text not null default '{}',
            diff_json text not null default '{}',
            error_message text not null default '',
            started_at integer not null,
            completed_at integer,
            applied_at integer,
            applied_by text references users(id) on delete set null,
            check(status in ('running','preview_ready','applied','needs_review','failed','rolled_back'))
        );
        create table if not exists activity_sync_leases (
            name text primary key,
            owner_token text not null,
            expires_at integer not null,
            updated_at integer not null
        );
        create table if not exists activity_event_overrides (
            event_id text primary key references activity_events(id) on delete cascade,
            override_json text not null default '{}',
            hidden integer not null default 0,
            reason text not null default '',
            base_content_hash text not null default '',
            updated_by text references users(id) on delete set null,
            created_at integer not null,
            updated_at integer not null,
            check(hidden in (0,1))
        );
        create table if not exists activity_source_candidates (
            id text primary key,
            game_id text not null references activity_games(game_id) on delete cascade,
            source_id text references activity_sources(id) on delete set null,
            source_key text not null,
            title text not null default '',
            official_url text not null default '',
            source_published_at integer,
            reason text not null default '',
            raw_json text not null default '{}',
            status text not null default 'pending',
            linked_event_id text references activity_events(id) on delete set null,
            first_seen_at integer not null,
            last_seen_at integer not null,
            reviewed_by text references users(id) on delete set null,
            reviewed_at integer,
            review_reason text not null default '',
            check(status in ('pending','ignored','linked')),
            unique(game_id,source_id,source_key)
        );
        create index if not exists activity_games_order_idx on activity_games(enabled,display_order,game_id);
        create index if not exists activity_events_window_idx on activity_events(published,game_id,start_at,end_at);
        create index if not exists activity_events_review_idx on activity_events(review_state,updated_at);
        create index if not exists activity_tasks_owner_idx on activity_tasks(owner_user_id,game_id,enabled,display_order);
        create index if not exists activity_tasks_event_idx on activity_tasks(event_id);
        create index if not exists activity_task_completions_user_idx on activity_task_completions(user_id,updated_at);
        create index if not exists activity_sync_runs_source_idx on activity_sync_runs(source_id,started_at desc);
        create index if not exists activity_event_overrides_hidden_idx on activity_event_overrides(hidden,updated_at desc);
        create index if not exists activity_source_candidates_review_idx on activity_source_candidates(status,game_id,last_seen_at desc);
        """
    )
    for game in ACTIVITY_GAMES:
        db.execute(
            """insert into activity_games(
            game_id,name,display_order,timezone,daily_reset_minute,weekly_reset_weekday,
            weekly_reset_minute,enabled,icon_path,created_at,updated_at)
            values(?,?,?,'Asia/Taipei',240,0,240,1,?,?,?)
            on conflict(game_id) do update set
            name=excluded.name,display_order=excluded.display_order,icon_path=excluded.icon_path,
            updated_at=excluded.updated_at
            where activity_games.name<>excluded.name
            or activity_games.display_order<>excluded.display_order
            or activity_games.icon_path<>excluded.icon_path""",
            (
                game["game_id"],
                game["name"],
                game["display_order"],
                game["icon_path"],
                stamp,
                stamp,
            ),
        )
    db.execute(
        "insert or ignore into schema_migrations(name,applied_at,details_json) values(?,?,?)",
        (
            SCHEMA_MIGRATION,
            stamp,
            json.dumps(
                {
                    "feature": "活動&代辦",
                    "admin_only": True,
                    "games": [game["game_id"] for game in ACTIVITY_GAMES],
                    "account_sync": "activity_task_completions",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        ),
    )
    db.execute(
        "insert or ignore into schema_migrations(name,applied_at,details_json) values(?,?,?)",
        (
            ADMIN_CONTROLS_MIGRATION,
            stamp,
            json.dumps(
                {
                    "feature": "活動&代辦後台控制",
                    "event_overrides": "manual_locked_priority",
                    "default_tasks": "owner_user_id_null",
                    "source_candidates": "pending_admin_review",
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        ),
    )
    db.execute(
        "insert or ignore into schema_migrations(name,applied_at,details_json) values(?,?,?)",
        (
            SOURCE_OPERATIONS_MIGRATION,
            stamp,
            json.dumps(
                {
                    "feature": "活動&代辦官方來源",
                    "scheduler_lease": "activity-source-auto-sync",
                    "review": "保留或確認移除",
                    "rollback": True,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ),
        ),
    )


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(str(value or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _timezone(value: str):
    timezone_name = str(value or "Asia/Taipei")
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        if timezone_name == "Asia/Taipei":
            return timezone(timedelta(hours=8), name="Asia/Taipei")
        return UTC


def _normalized_task_schedule(cadence: str, schedule: dict[str, Any]) -> dict[str, Any]:
    if cadence == "monthly":
        value = schedule if isinstance(schedule, dict) else {}
        raw_month_day = value.get("month_day", 1)
        if isinstance(raw_month_day, bool):
            raise ValueError("每月日期必須是 1 至 31 的整數。")
        try:
            month_day = int(raw_month_day)
        except (TypeError, ValueError) as exc:
            raise ValueError("每月日期必須是 1 至 31 的整數。") from exc
        if isinstance(raw_month_day, float) and raw_month_day != month_day:
            raise ValueError("每月日期必須是 1 至 31 的整數。")
        if isinstance(raw_month_day, str) and raw_month_day.strip() != str(month_day):
            raise ValueError("每月日期必須是 1 至 31 的整數。")
        if month_day < 1 or month_day > 31:
            raise ValueError("每月日期必須介於 1 至 31 日。")
        return {"month_day": month_day}
    if cadence != "custom":
        return {}
    value = schedule if isinstance(schedule, dict) else {}
    if str(value.get("period") or "once") != "interval":
        return {"period": "once"}
    raw_interval = value.get("interval_days")
    if isinstance(raw_interval, bool):
        raise ValueError("自訂間隔天數必須是 1 至 365 的整數。")
    try:
        interval_days = int(raw_interval)
    except (TypeError, ValueError) as exc:
        raise ValueError("自訂間隔天數必須是 1 至 365 的整數。") from exc
    if isinstance(raw_interval, float) and raw_interval != interval_days:
        raise ValueError("自訂間隔天數必須是 1 至 365 的整數。")
    if isinstance(raw_interval, str) and raw_interval.strip() != str(interval_days):
        raise ValueError("自訂間隔天數必須是 1 至 365 的整數。")
    if interval_days < 1 or interval_days > 365:
        raise ValueError("自訂間隔天數必須介於 1 至 365 天。")
    return {"period": "interval", "interval_days": interval_days}


def _period_key(task: sqlite3.Row | dict[str, Any], game: sqlite3.Row | dict[str, Any], stamp: int) -> str:
    cadence = str(task["cadence"])
    schedule = _json_object(task["schedule_json"])
    if cadence == "custom":
        if str(schedule.get("period") or "once") != "interval":
            return "once"
        try:
            interval_days = int(schedule.get("interval_days"))
        except (TypeError, ValueError):
            return "once"
        if interval_days < 1 or interval_days > 365:
            return "once"
        cadence = "interval"
    if cadence == "once":
        return "once"
    zone = _timezone(str(game["timezone"]))
    local = datetime.fromtimestamp(stamp, UTC).astimezone(zone)
    reset_minute = int(game["daily_reset_minute"] or 0)
    shifted = local - timedelta(minutes=reset_minute)
    if cadence == "interval":
        anchor_stamp = int(_row_value(task, "created_at", stamp) or stamp)
        anchor_local = datetime.fromtimestamp(anchor_stamp, UTC).astimezone(zone)
        anchor_date = (anchor_local - timedelta(minutes=reset_minute)).date()
        elapsed_days = max(0, (shifted.date() - anchor_date).days)
        period_start = anchor_date + timedelta(days=(elapsed_days // interval_days) * interval_days)
        return f"I:{interval_days}:" + period_start.isoformat()
    if cadence == "daily":
        return shifted.strftime("%Y-%m-%d")
    if cadence == "monthly":
        try:
            month_day = int(schedule.get("month_day", 1))
        except (TypeError, ValueError):
            month_day = 1
        if month_day < 1 or month_day > 31:
            month_day = 1
        if month_day == 1:
            return shifted.strftime("%Y-%m")
        shifted_date = shifted.date()
        boundary = shifted_date.replace(day=min(month_day, monthrange(shifted_date.year, shifted_date.month)[1]))
        if shifted_date < boundary:
            previous_month = shifted_date.replace(day=1) - timedelta(days=1)
            boundary = previous_month.replace(day=min(month_day, monthrange(previous_month.year, previous_month.month)[1]))
        return f"M:{month_day}:" + boundary.isoformat()
    if cadence == "weekly":
        weekly_shifted = local - timedelta(minutes=int(game["weekly_reset_minute"] or 0))
        weekday = int(game["weekly_reset_weekday"] or 0)
        start = weekly_shifted.date() - timedelta(days=(weekly_shifted.weekday() - weekday) % 7)
        return "W:" + start.isoformat()
    return "once"


def _game_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["game_id"],
        "name": row["name"],
        "display_order": int(row["display_order"]),
        "timezone": row["timezone"],
        "daily_reset_minute": int(row["daily_reset_minute"]),
        "weekly_reset_weekday": int(row["weekly_reset_weekday"]),
        "weekly_reset_minute": int(row["weekly_reset_minute"]),
        "icon": row["icon_path"],
    }


def _row_value(row: sqlite3.Row | dict[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return row[key] if key in row.keys() else default


def _effective_event(row: sqlite3.Row | dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    base = {field: _row_value(row, field) for field in EVENT_OVERRIDE_FIELDS}
    override = _json_object(_row_value(row, "override_json", "{}"))
    effective = dict(base)
    for field in EVENT_OVERRIDE_FIELDS:
        if field in override:
            effective[field] = override[field]
    for field in ("start_at", "end_at"):
        if effective[field] is not None:
            effective[field] = int(effective[field])
    return effective, override


def _event_payload(row: sqlite3.Row, stamp: int) -> dict[str, Any]:
    effective, _ = _effective_event(row)
    start_at = effective["start_at"]
    end_at = effective["end_at"]
    status = "進行中"
    if start_at is not None and stamp < start_at:
        status = "即將開始"
    elif end_at is not None and stamp > end_at:
        status = "已結束"
    return {
        "id": row["id"],
        "game_id": row["game_id"],
        "title": effective["title"],
        "summary": effective["summary"],
        "category": effective["category"],
        "start_at": start_at,
        "end_at": end_at,
        "official_url": effective["official_url"],
        "image_url": effective["image_url"],
        "status": status,
        "language": row["language"],
    }


def _task_payload(row: sqlite3.Row, game: sqlite3.Row, completion: sqlite3.Row | None, stamp: int) -> dict[str, Any]:
    period_key = _period_key(row, game, stamp)
    return {
        "id": row["id"],
        "game_id": row["game_id"],
        "event_id": row["event_id"],
        "title": row["title"],
        "description": row["description"],
        "cadence": row["cadence"],
        "schedule": _json_object(row["schedule_json"]),
        "due_at": int(row["due_at"]) if row["due_at"] is not None else None,
        "source_type": row["source_type"],
        "period_key": period_key,
        "completed": bool(completion),
        "completed_at": int(completion["completed_at"]) if completion else None,
        "display_order": int(row["display_order"]),
        "editable": row["owner_user_id"] is not None,
    }


def dashboard(db: sqlite3.Connection, user_id: str, stamp: int) -> dict[str, Any]:
    game_rows = db.execute(
        "select * from activity_games where enabled=1 order by display_order,game_id"
    ).fetchall()
    games_by_id = {str(row["game_id"]): row for row in game_rows}
    events = db.execute(
        """select e.*,o.override_json,o.hidden as override_hidden,o.reason as override_reason,
        o.base_content_hash as override_base_content_hash,o.updated_at as override_updated_at
        from activity_events e left join activity_event_overrides o on o.event_id=e.id
        where e.published=1 and e.removed_at is null
        order by case when e.start_at is null then 1 else 0 end,e.start_at,e.end_at,e.title""",
    ).fetchall()
    visible_events = []
    for event in events:
        effective, _ = _effective_event(event)
        if bool(_row_value(event, "override_hidden", 0)):
            continue
        if effective["end_at"] is not None and int(effective["end_at"]) < stamp:
            continue
        visible_events.append(event)
    tasks = db.execute(
        """select * from activity_tasks
        where enabled=1 and deleted_at is null and (owner_user_id is null or owner_user_id=?)
        order by display_order,created_at,id""",
        (user_id,),
    ).fetchall()
    completion_rows = db.execute(
        """select c.* from activity_task_completions c
        join activity_tasks t on t.id=c.task_id
        where c.user_id=? and t.enabled=1 and t.deleted_at is null""",
        (user_id,),
    ).fetchall()
    completions = {(str(row["task_id"]), str(row["period_key"])): row for row in completion_rows}
    task_payloads: list[dict[str, Any]] = []
    for task in tasks:
        game = games_by_id.get(str(task["game_id"]))
        if game is None:
            continue
        period_key = _period_key(task, game, stamp)
        task_payloads.append(_task_payload(task, game, completions.get((str(task["id"]), period_key)), stamp))
    return {
        "games": [_game_payload(row) for row in game_rows],
        "events": [_event_payload(row, stamp) for row in visible_events],
        "tasks": task_payloads,
        "summary": {
            "task_count": len(task_payloads),
            "completed_count": sum(1 for task in task_payloads if task["completed"]),
            "event_count": len(visible_events),
        },
    }


def _validate_game(db: sqlite3.Connection, game_id: str) -> None:
    if not db.execute("select 1 from activity_games where game_id=? and enabled=1", (game_id,)).fetchone():
        raise ValueError("找不到可用的遊戲。")


def _validate_event_window(start_at: int | None, end_at: int | None) -> None:
    if start_at is not None and end_at is not None and int(end_at) < int(start_at):
        raise ValueError("活動結束時間不可早於開始時間。")


def admin_events(db: sqlite3.Connection, stamp: int) -> list[dict[str, Any]]:
    rows = db.execute(
        """select e.*,g.name as game_name,g.display_order as game_display_order,s.name as source_name,
        o.override_json,o.hidden as override_hidden,o.reason as override_reason,
        o.base_content_hash as override_base_content_hash,o.updated_by as override_updated_by,
        o.updated_at as override_updated_at
        from activity_events e join activity_games g on g.game_id=e.game_id
        left join activity_sources s on s.id=e.source_id
        left join activity_event_overrides o on o.event_id=e.id
        where e.removed_at is null
        order by g.display_order,case when e.start_at is null then 1 else 0 end,e.start_at desc,e.updated_at desc"""
    ).fetchall()
    payloads: list[dict[str, Any]] = []
    for row in rows:
        effective, override = _effective_event(row)
        start_at = effective["start_at"]
        end_at = effective["end_at"]
        status = "進行中"
        if bool(_row_value(row, "override_hidden", 0)):
            status = "已隱藏"
        elif not bool(row["published"]):
            status = "待確認"
        elif start_at is not None and stamp < start_at:
            status = "即將開始"
        elif end_at is not None and stamp > end_at:
            status = "已結束"
        payloads.append(
            {
                "id": row["id"],
                "game_id": row["game_id"],
                "game_name": row["game_name"],
                "source_id": row["source_id"],
                "source_name": row["source_name"] or "管理員新增",
                "source_key": row["source_key"],
                "manual": row["source_id"] is None,
                "published": bool(row["published"]),
                "review_state": row["review_state"],
                "status": status,
                "effective": effective,
                "official": {field: row[field] for field in EVENT_OVERRIDE_FIELDS},
                "override": override,
                "override_active": bool(override) or bool(_row_value(row, "override_hidden", 0)),
                "hidden": bool(_row_value(row, "override_hidden", 0)),
                "override_reason": _row_value(row, "override_reason", ""),
                "official_changed_after_override": bool(
                    _row_value(row, "override_base_content_hash", "")
                    and _row_value(row, "override_base_content_hash", "") != row["content_hash"]
                ),
                "updated_at": int(row["updated_at"]),
                "override_updated_at": _row_value(row, "override_updated_at"),
            }
        )
    return payloads


def admin_default_tasks(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute(
        """select t.*,g.name as game_name,g.display_order as game_display_order
        from activity_tasks t join activity_games g on g.game_id=t.game_id
        where t.owner_user_id is null and t.source_type='system' and t.deleted_at is null
        order by g.display_order,t.display_order,t.created_at,t.id"""
    ).fetchall()
    return [
        {
            "id": row["id"],
            "game_id": row["game_id"],
            "game_name": row["game_name"],
            "title": row["title"],
            "description": row["description"],
            "cadence": row["cadence"],
            "schedule": _json_object(row["schedule_json"]),
            "due_at": int(row["due_at"]) if row["due_at"] is not None else None,
            "enabled": bool(row["enabled"]),
            "display_order": int(row["display_order"]),
            "updated_at": int(row["updated_at"]),
        }
        for row in rows
    ]


def create_default_task(
    db: sqlite3.Connection,
    *,
    game_id: str,
    title: str,
    description: str,
    cadence: str,
    schedule: dict[str, Any],
    due_at: int | None,
    enabled: bool,
    display_order: int,
    stamp: int,
) -> str:
    if cadence not in SUPPORTED_CADENCES:
        raise ValueError("不支援的代辦週期。")
    schedule = _normalized_task_schedule(cadence, schedule)
    _validate_game(db, game_id)
    task_id = "default-task-" + uuid.uuid4().hex
    db.execute(
        """insert into activity_tasks(
        id,owner_user_id,game_id,event_id,title,description,cadence,schedule_json,due_at,
        source_type,enabled,display_order,deleted_at,created_at,updated_at)
        values(?,null,?,null,?,?,?,?,?,'system',?,?,null,?,?)""",
        (
            task_id,
            game_id,
            title,
            description,
            cadence,
            json.dumps(schedule, ensure_ascii=False, separators=(",", ":")),
            due_at,
            int(enabled),
            int(display_order),
            stamp,
            stamp,
        ),
    )
    return task_id


def update_default_task(
    db: sqlite3.Connection,
    *,
    task_id: str,
    game_id: str,
    title: str,
    description: str,
    cadence: str,
    schedule: dict[str, Any],
    due_at: int | None,
    enabled: bool,
    display_order: int,
    stamp: int,
) -> None:
    if cadence not in SUPPORTED_CADENCES:
        raise ValueError("不支援的代辦週期。")
    schedule = _normalized_task_schedule(cadence, schedule)
    _validate_game(db, game_id)
    changed = db.execute(
        """update activity_tasks set game_id=?,title=?,description=?,cadence=?,schedule_json=?,due_at=?,
        enabled=?,display_order=?,updated_at=? where id=? and owner_user_id is null
        and source_type='system' and deleted_at is null""",
        (
            game_id,
            title,
            description,
            cadence,
            json.dumps(schedule, ensure_ascii=False, separators=(",", ":")),
            due_at,
            int(enabled),
            int(display_order),
            stamp,
            task_id,
        ),
    ).rowcount
    if not changed:
        raise LookupError("找不到預設代辦。")


def delete_default_task(db: sqlite3.Connection, *, task_id: str, stamp: int) -> None:
    changed = db.execute(
        """update activity_tasks set enabled=0,deleted_at=?,updated_at=? where id=?
        and owner_user_id is null and source_type='system' and deleted_at is null""",
        (stamp, stamp, task_id),
    ).rowcount
    if not changed:
        raise LookupError("找不到預設代辦。")


def create_manual_event(
    db: sqlite3.Connection,
    *,
    game_id: str,
    title: str,
    summary: str,
    category: str,
    start_at: int | None,
    end_at: int | None,
    official_url: str,
    image_url: str,
    stamp: int,
) -> str:
    _validate_game(db, game_id)
    _validate_event_window(start_at, end_at)
    event_id = "manual-event-" + uuid.uuid4().hex
    source_key = "manual:" + uuid.uuid4().hex
    event = {
        "source_key": source_key,
        "title": title,
        "summary": summary,
        "category": category,
        "start_at": start_at,
        "end_at": end_at,
        "official_url": official_url,
        "image_url": image_url,
        "language": "zh-TW",
        "source_updated_at": stamp,
    }
    db.execute(
        """insert into activity_events(
        id,game_id,source_id,source_key,title,summary,category,start_at,end_at,official_url,
        image_url,language,source_updated_at,content_hash,published,review_state,removed_at,created_at,updated_at)
        values(?,?,null,?,?,?,?,?,?,?,?,'zh-TW',?,?,1,'approved',null,?,?)""",
        (
            event_id,
            game_id,
            source_key,
            title,
            summary,
            category,
            start_at,
            end_at,
            official_url,
            image_url,
            stamp,
            event_content_hash(event),
            stamp,
            stamp,
        ),
    )
    return event_id


def delete_event(db: sqlite3.Connection, *, event_id: str, stamp: int) -> None:
    changed = db.execute(
        """update activity_events set published=0,removed_at=?,updated_at=?
        where id=? and removed_at is null""",
        (stamp, stamp, event_id),
    ).rowcount
    if not changed:
        raise LookupError("找不到活動。")


def set_event_override(
    db: sqlite3.Connection,
    *,
    event_id: str,
    values: dict[str, Any],
    hidden: bool,
    reason: str,
    admin_user_id: str,
    stamp: int,
) -> None:
    event = db.execute("select * from activity_events where id=? and removed_at is null", (event_id,)).fetchone()
    if event is None:
        raise LookupError("找不到活動。")
    normalized = {field: values[field] for field in EVENT_OVERRIDE_FIELDS if field in values}
    _validate_event_window(normalized.get("start_at"), normalized.get("end_at"))
    db.execute(
        """insert into activity_event_overrides(
        event_id,override_json,hidden,reason,base_content_hash,updated_by,created_at,updated_at)
        values(?,?,?,?,?,?,?,?) on conflict(event_id) do update set
        override_json=excluded.override_json,hidden=excluded.hidden,reason=excluded.reason,
        base_content_hash=excluded.base_content_hash,updated_by=excluded.updated_by,updated_at=excluded.updated_at""",
        (
            event_id,
            json.dumps(normalized, ensure_ascii=False, separators=(",", ":")),
            int(hidden),
            reason,
            event["content_hash"],
            admin_user_id,
            stamp,
            stamp,
        ),
    )


def restore_event_official(db: sqlite3.Connection, *, event_id: str) -> None:
    if not db.execute("select 1 from activity_events where id=?", (event_id,)).fetchone():
        raise LookupError("找不到活動。")
    db.execute("delete from activity_event_overrides where event_id=?", (event_id,))


def admin_candidates(db: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = db.execute(
        """select c.*,g.name as game_name,g.display_order,s.name as source_name
        from activity_source_candidates c join activity_games g on g.game_id=c.game_id
        left join activity_sources s on s.id=c.source_id
        order by case c.status when 'pending' then 0 else 1 end,g.display_order,c.last_seen_at desc"""
    ).fetchall()
    return [
        {
            "id": row["id"],
            "game_id": row["game_id"],
            "game_name": row["game_name"],
            "source_id": row["source_id"],
            "source_name": row["source_name"] or "官方來源",
            "source_key": row["source_key"],
            "title": row["title"],
            "official_url": row["official_url"],
            "source_published_at": row["source_published_at"],
            "reason": row["reason"],
            "status": row["status"],
            "linked_event_id": row["linked_event_id"],
            "first_seen_at": row["first_seen_at"],
            "last_seen_at": row["last_seen_at"],
            "review_reason": row["review_reason"],
        }
        for row in rows
    ]


def review_candidate(
    db: sqlite3.Connection,
    *,
    candidate_id: str,
    action: str,
    reason: str,
    event_id: str | None,
    admin_user_id: str,
    stamp: int,
) -> None:
    candidate = db.execute("select * from activity_source_candidates where id=?", (candidate_id,)).fetchone()
    if candidate is None:
        raise LookupError("找不到待確認公告。")
    if action not in {"ignore", "link"}:
        raise ValueError("不支援的公告審核動作。")
    linked_event_id = None
    status = "ignored"
    if action == "link":
        linked = db.execute("select game_id from activity_events where id=? and removed_at is null", (event_id,)).fetchone()
        if linked is None or str(linked["game_id"]) != str(candidate["game_id"]):
            raise ValueError("請選擇同一遊戲的有效活動。")
        linked_event_id = str(event_id)
        status = "linked"
    db.execute(
        """update activity_source_candidates set status=?,linked_event_id=?,reviewed_by=?,
        reviewed_at=?,review_reason=? where id=?""",
        (status, linked_event_id, admin_user_id, stamp, reason, candidate_id),
    )


def create_custom_task(
    db: sqlite3.Connection,
    *,
    user_id: str,
    game_id: str,
    title: str,
    description: str,
    cadence: str,
    schedule: dict[str, Any],
    due_at: int | None,
    stamp: int,
) -> str:
    if cadence not in SUPPORTED_CADENCES:
        raise ValueError("不支援的代辦週期。")
    schedule = _normalized_task_schedule(cadence, schedule)
    if not db.execute("select 1 from activity_games where game_id=? and enabled=1", (game_id,)).fetchone():
        raise ValueError("找不到可用的遊戲。")
    task_id = "task-" + uuid.uuid4().hex
    db.execute(
        """insert into activity_tasks(
        id,owner_user_id,game_id,event_id,title,description,cadence,schedule_json,due_at,
        source_type,enabled,display_order,deleted_at,created_at,updated_at)
        values(?,?,?,null,?,?,?,?,?,'manual',1,0,null,?,?)""",
        (
            task_id,
            user_id,
            game_id,
            title,
            description,
            cadence,
            json.dumps(schedule, ensure_ascii=False, separators=(",", ":")),
            due_at,
            stamp,
            stamp,
        ),
    )
    return task_id


def update_custom_task(
    db: sqlite3.Connection,
    *,
    task_id: str,
    user_id: str,
    title: str,
    description: str,
    cadence: str,
    schedule: dict[str, Any],
    due_at: int | None,
    enabled: bool,
    stamp: int,
) -> None:
    if cadence not in SUPPORTED_CADENCES:
        raise ValueError("不支援的代辦週期。")
    schedule = _normalized_task_schedule(cadence, schedule)
    changed = db.execute(
        """update activity_tasks set
        title=?,description=?,cadence=?,schedule_json=?,due_at=?,enabled=?,updated_at=?
        where id=? and owner_user_id=? and source_type='manual' and deleted_at is null""",
        (
            title,
            description,
            cadence,
            json.dumps(schedule, ensure_ascii=False, separators=(",", ":")),
            due_at,
            int(enabled),
            stamp,
            task_id,
            user_id,
        ),
    ).rowcount
    if not changed:
        raise LookupError("找不到可編輯的代辦。")


def delete_custom_task(db: sqlite3.Connection, *, task_id: str, user_id: str, stamp: int) -> None:
    changed = db.execute(
        """update activity_tasks set enabled=0,deleted_at=?,updated_at=?
        where id=? and owner_user_id=? and source_type='manual' and deleted_at is null""",
        (stamp, stamp, task_id, user_id),
    ).rowcount
    if not changed:
        raise LookupError("找不到可刪除的代辦。")


def set_completion(
    db: sqlite3.Connection,
    *,
    task_id: str,
    user_id: str,
    completed: bool,
    stamp: int,
) -> dict[str, Any]:
    task = db.execute(
        """select t.*,g.timezone,g.daily_reset_minute,g.weekly_reset_weekday,g.weekly_reset_minute
        from activity_tasks t join activity_games g on g.game_id=t.game_id
        where t.id=? and t.enabled=1 and t.deleted_at is null
        and (t.owner_user_id is null or t.owner_user_id=?)""",
        (task_id, user_id),
    ).fetchone()
    if not task:
        raise LookupError("找不到可操作的代辦。")
    period_key = _period_key(task, task, stamp)
    if completed:
        db.execute(
            """insert into activity_task_completions(user_id,task_id,period_key,completed_at,updated_at)
            values(?,?,?,?,?) on conflict(user_id,task_id,period_key) do update set
            completed_at=excluded.completed_at,updated_at=excluded.updated_at""",
            (user_id, task_id, period_key, stamp, stamp),
        )
    else:
        db.execute(
            "delete from activity_task_completions where user_id=? and task_id=? and period_key=?",
            (user_id, task_id, period_key),
        )
    return {"task_id": task_id, "period_key": period_key, "completed": completed, "completed_at": stamp if completed else None}


def event_content_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
