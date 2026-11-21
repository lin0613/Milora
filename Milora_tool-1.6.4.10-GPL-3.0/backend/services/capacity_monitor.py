"""Non-destructive capacity checks and owner-only, incident-deduplicated alerts."""
import json
import logging
import shutil
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

GIB = 1024 ** 3
CHECK_SECONDS = 300
SAMPLE_SECONDS = 3600
SEVERITY_LABELS = {0: "正常", 1: "提醒", 2: "嚴重警告", 3: "危急警告"}
SCHEMA = """
create table if not exists system_health_alert_state(
 alert_key text primary key, severity integer not null, notified_severity integer not null default 0,
 owner_id text not null default '', notification_ids_json text not null default '[]',
 name text not null, message text not null, checked_at integer not null);
create table if not exists audit_capacity_samples(
 sample_day text primary key, collected_at integer not null, record_count integer not null,
 content_bytes integer not null, database_bytes integer not null);
"""
logger = logging.getLogger(__name__)


def disk_severity(free):
    return 3 if free <= GIB else 2 if free <= 5 * GIB else 1 if free <= 10 * GIB else 0


def issue(key, name, severity, message, **details):
    return {"key": key, "name": name, "severity": severity,
            "severity_label": SEVERITY_LABELS[severity], "message": message, "details": details}


class CapacityMonitor:
    def __init__(self, root, database, connect, owner_email, notify, clock=time.time, on_notifications_changed=None):
        self.root, self.database = Path(root), Path(database)
        self.connect, self.owner_email, self.notify, self.clock = connect, owner_email, notify, clock
        self.lock = threading.RLock()
        self.latest = None
        self.integrity = None
        self.integrity_at = 0
        self.on_notifications_changed = on_notifications_changed

    def _persist(self, checks, sample, stamp):
        # Do not create a missing database just to record a warning.
        if not self.database.is_file():
            return False
        notifications_changed = False
        with self.connect() as db:
            db.execute("pragma busy_timeout=250")
            db.execute("begin immediate")
            owner = db.execute("select id from users where email_key=? and is_active=1 and role='admin'",
                               (self.owner_email,)).fetchone() if self.owner_email else None
            owner_id = str(owner[0]) if owner else ""
            for check in checks:
                prior = db.execute("select * from system_health_alert_state where alert_key=?", (check["key"],)).fetchone()
                if prior and int(prior["checked_at"]) > stamp:
                    continue
                notified = int(prior["notified_severity"]) if prior else 0
                previous_owner = str(prior["owner_id"]) if prior else ""
                ids = json.loads(prior["notification_ids_json"]) if prior else []
                severity = check["severity"]
                if severity and (not prior or severity > int(prior["severity"])):
                    logger.log(logging.ERROR if severity >= 2 else logging.WARNING,
                               "System health alert %s (%s): %s", check["key"], check["severity_label"], check["message"])
                elif prior and int(prior["severity"]) and not severity:
                    logger.info("System health alert recovered: %s", check["key"])
                if not severity:
                    # Retain the history row; only deactivate the resolved notifications.
                    for item_id in ids:
                        changed = db.execute("update message_center_items set is_active=0 where id=? and kind='system_health' and is_active=1", (item_id,)).rowcount
                        notifications_changed = notifications_changed or bool(changed)
                    notified, ids = 0, []
                elif owner_id and (severity > notified or owner_id != previous_owner):
                    body = (f"{check['message']}\n\n警告等級：{check['severity_label']}。"
                            "\n請前往後台「系統健康」查看。系統不會自動刪除操作紀錄或限制紀錄容量。")
                    item_id = self.notify(db, user_id=owner_id, title=f"系統預警｜{check['name']}：{check['severity_label']}",
                                          body=body, link="/admin/?admin_tab=health", kind="system_health",
                                          level="warning" if severity == 1 else "danger")
                    ids.append(item_id)
                    notifications_changed = True
                    notified, previous_owner = severity, owner_id
                db.execute("""insert into system_health_alert_state(
                    alert_key,severity,notified_severity,owner_id,notification_ids_json,name,message,checked_at)
                    values(?,?,?,?,?,?,?,?) on conflict(alert_key) do update set
                    severity=excluded.severity,notified_severity=excluded.notified_severity,owner_id=excluded.owner_id,
                    notification_ids_json=excluded.notification_ids_json,name=excluded.name,message=excluded.message,checked_at=excluded.checked_at""",
                           (check["key"], severity, notified, previous_owner, json.dumps(ids), check["name"], check["message"], stamp))
            if sample:
                db.execute("""insert into audit_capacity_samples(sample_day,collected_at,record_count,content_bytes,database_bytes)
                    values(?,?,?,?,?) on conflict(sample_day) do update set collected_at=excluded.collected_at,
                    record_count=excluded.record_count,content_bytes=excluded.content_bytes,database_bytes=excluded.database_bytes
                    where excluded.collected_at>=audit_capacity_samples.collected_at""",
                           tuple(sample[key] for key in ("sample_day", "collected_at", "record_count", "content_bytes", "database_bytes")))
        if notifications_changed and self.on_notifications_changed:
            try:
                self.on_notifications_changed()
            except Exception:
                logger.exception("Health notifications committed but live revision update failed")
        return True

    def _collect(self, stamp, force):
        checks = []
        # A configured DB may live on a different volume from the site's backups.
        paths = {str(self.root.anchor or self.root): self.root,
                 str(self.database.parent.anchor or self.database.parent): self.database.parent}
        for key, path in paths.items():
            try:
                disk = shutil.disk_usage(path)
                checks.append(issue("disk:" + key, "磁碟空間 " + key, disk_severity(disk.free),
                                    f"可用 {disk.free / GIB:.2f} GiB；提醒／嚴重／危急門檻為 10／5／1 GiB。",
                                    total=disk.total, used=disk.used, free=disk.free))
            except OSError as exc:
                checks.append(issue("disk:" + key, "磁碟空間 " + key, 3, f"無法檢查磁碟（{type(exc).__name__}）。"))
        try:
            backups_exist = any((self.root / "backups").glob("*.db"))
            checks.append(issue("backup.missing", "資料庫備份", 0 if backups_exist else 1,
                                "已找到備份檔；有效性需由備份檢查確認。" if backups_exist else "目前沒有資料庫備份，請建立備份。"))
        except OSError as exc:
            checks.append(issue("backup.missing", "資料庫備份", 2, f"無法檢查備份（{type(exc).__name__}）。"))
        wal = Path(str(self.database) + "-wal")
        try:
            wal_bytes = wal.stat().st_size if wal.exists() else 0
            checks.append(issue("database.wal", "SQLite WAL", 1 if wal_bytes > 64 * 1024 ** 2 else 0,
                                "WAL 暫存檔超過 64 MB，請確認是否持續增長或有長時間交易。" if wal_bytes > 64 * 1024 ** 2 else "WAL 容量正常。",
                                size_bytes=wal_bytes))
        except OSError as exc:
            checks.append(issue("database.wal", "SQLite WAL", 2, f"無法檢查 WAL（{type(exc).__name__}）。"))
        sample, history = None, []
        if not self.database.is_file():
            checks.append(issue("database.integrity", "資料庫", 3, "找不到資料庫檔案。"))
            return checks, sample, history
        try:
            with self.connect() as db:
                if force or self.integrity is None or stamp - self.integrity_at >= SAMPLE_SECONDS:
                    self.integrity = str(db.execute("pragma quick_check").fetchone()[0])
                    self.integrity_at = stamp
                checks.append(issue("database.integrity", "資料庫完整性", 0 if self.integrity == "ok" else 3,
                                    "完整性檢查正常。" if self.integrity == "ok" else "資料庫完整性檢查異常，請保留現況並檢查備份。"))
                failure = db.execute("select severity,message from system_health_alert_state where alert_key='backup.failure'").fetchone()
                checks.append(issue("backup.failure", "備份失敗", int(failure[0]) if failure else 0,
                                    str(failure[1]) if failure else "最近沒有備份失敗。"))
                latest = db.execute("select * from audit_capacity_samples order by collected_at desc limit 1").fetchone()
                if not latest or stamp - int(latest["collected_at"]) >= SAMPLE_SECONDS:
                    # UTF-8 field-content volume, not SQLite physical pages/indexes.
                    columns = [row[1] for row in db.execute("pragma table_info(admin_audit_logs)")]
                    expression = "+".join('coalesce(length(cast("' + name.replace('"', '""') + '" as blob)),0)' for name in columns)
                    count, size = db.execute("select count(*),sum(" + expression + ") from admin_audit_logs").fetchone()
                    sample = {"sample_day": datetime.fromtimestamp(stamp, timezone(timedelta(hours=8))).date().isoformat(),
                              "collected_at": stamp, "record_count": count, "content_bytes": int(size or 0),
                              "database_bytes": self.database.stat().st_size}
                else:
                    sample = dict(latest)
                history = [dict(row) for row in db.execute("select * from audit_capacity_samples order by sample_day desc limit 7")]
        except Exception as exc:
            checks = [row for row in checks if row["key"] != "database.integrity"]
            checks.append(issue("database.integrity", "資料庫檢查", 3, f"檢查無法完成（{type(exc).__name__}）；請查看後端日誌。"))
            logger.exception("Capacity monitor database check failed")
        return checks, sample, history

    def check(self, force=False):
        with self.lock:
            stamp = int(self.clock())
            if not force and self.latest and stamp - self.latest["checked_at"] < CHECK_SECONDS:
                return self.latest
            checks, sample, history = self._collect(stamp, force)
            delivery = "available"
            try:
                if not self._persist(checks, sample, stamp):
                    delivery = "unavailable"
                    logger.error("Capacity alert storage unavailable: %s", "; ".join(row["message"] for row in checks if row["severity"]))
            except Exception:
                # A full/corrupt DB cannot reliably store an in-site notification.
                delivery = "unavailable"
                logger.exception("Capacity alert persistence failed; no records were deleted")
            if delivery == "unavailable":
                checks.append(issue("monitor.persistence", "預警儲存", 2,
                                    "預警狀態無法寫入資料庫，站內通知可能無法送達；請檢查後端日誌。"))
            if sample:
                history = sorted({row["sample_day"]: row for row in [*history, sample]}.values(), key=lambda row: row["sample_day"])[-7:]
            previous = history[-2] if len(history) > 1 else None
            severity = max((row["severity"] for row in checks), default=0)
            self.latest = {"checked_at": stamp, "severity": severity, "severity_label": SEVERITY_LABELS[severity],
                           "status": "error" if severity >= 2 else "warning" if severity else "ok", "checks": checks,
                           "alerts": [row for row in checks if row["severity"]], "notification_delivery": delivery,
                           "audit": {"latest": sample, "history": history,
                                     "change_bytes": sample["content_bytes"] - previous["content_bytes"] if sample and previous else None,
                                     "change_count": sample["record_count"] - previous["record_count"] if sample and previous else None}}
            return self.latest

    def backup_result(self, error=None):
        with self.lock:
            check = issue("backup.failure", "備份失敗", 3 if error else 0,
                          f"建立資料庫備份失敗（{type(error).__name__}），請查看後端日誌並重新建立備份。" if error else "最近一次備份成功。")
            try:
                self._persist([check], None, int(self.clock()))
            except Exception:
                logger.exception("Could not persist backup result")
            self.latest = None

    def run(self, stop):
        while not stop.is_set():
            try:
                self.check()
            except Exception:
                logger.exception("Capacity monitor iteration failed")
            stop.wait(CHECK_SECONDS)
