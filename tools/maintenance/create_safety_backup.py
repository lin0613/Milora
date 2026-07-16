#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[2]))
    parser.add_argument('--reason', default='manual')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_root = root / 'backups' / f'safety-{stamp}'
    backup_root.mkdir(parents=True, exist_ok=False)

    copied = []
    for rel in ('.env', 'release-info.json', 'release-manifest.json'):
        source = root / rel
        if source.is_file():
            destination = backup_root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            copied.append(rel)

    source_db = root / 'data/app.db'
    if not source_db.is_file():
        raise RuntimeError('Missing data/app.db')
    destination_db = backup_root / 'data/app.db'
    destination_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source_db) as source, sqlite3.connect(destination_db) as destination:
        source.backup(destination)
        if destination.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup database integrity check failed')
    copied.append('data/app.db')

    metadata = {
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'reason': args.reason,
        'source_root': str(root),
        'files': copied,
    }
    (backup_root / 'backup-info.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(str(backup_root))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f'Backup failed: {exc}', file=sys.stderr)
        raise SystemExit(1)
