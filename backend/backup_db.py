from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path

from dotenv import load_dotenv

from backend.core.paths import BACKUP_DIR, DATA_DIR, ROOT

load_dotenv(ROOT / ".env")


def main() -> int:
    source = Path(os.getenv("DATABASE_PATH", str(DATA_DIR / "app.db")))
    if not source.exists():
        raise FileNotFoundError(f"找不到資料庫：{source}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"app-{time.strftime('%Y%m%d-%H%M%S')}.db"

    with sqlite3.connect(source) as source_db, sqlite3.connect(target) as target_db:
        source_db.backup(target_db)
        result = target_db.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"備份資料庫完整性檢查失敗：{result}")

    # Keep the newest 30 automatic backups; older files are generated history.
    backups = sorted(BACKUP_DIR.glob("app-*.db"), key=lambda path: path.stat().st_mtime, reverse=True)
    for old_backup in backups[30:]:
        old_backup.unlink(missing_ok=True)

    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
