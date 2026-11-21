"""Metadata-only inspection cache; cached results never authorize a restore."""
from collections import OrderedDict
from pathlib import Path
import threading
import time


class BackupInspectionCache:
    def __init__(self, limit=128, clock=time.time):
        self.limit, self.clock = max(1, limit), clock
        self.entries = OrderedDict()
        self.lock = threading.RLock()

    @staticmethod
    def fingerprint(path):
        path = Path(path).resolve()
        parts = []
        for file in (path, Path(str(path) + "-wal"), Path(str(path) + "-journal")):
            try:
                stat = file.stat()
                if file == Path(str(path) + "-wal") and stat.st_size == 0:
                    parts.append(None)  # SQLite may create an empty WAL while opening read-only.
                    continue
                parts.append((stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_ino))
            except FileNotFoundError:
                if file == path:
                    raise
                parts.append(None)
        return tuple(parts)

    def status(self, path):
        key = str(Path(path).resolve())
        try:
            current = self.fingerprint(path)
        except OSError:
            current = None
        with self.lock:
            saved = self.entries.get(key)
            if current is not None and saved and saved[0] == current:
                self.entries.move_to_end(key)
                return {**saved[1], "cached": True}
            self.entries.pop(key, None)
        return {"integrity": "unchecked", "checked_at": None, "cached": False}

    def inspect(self, path, checker):
        key = str(Path(path).resolve())
        before = self.fingerprint(path)
        with self.lock:
            self.entries.pop(key, None)
        integrity = checker(Path(path))  # Explicit checks always run, even if cached.
        try:
            after = self.fingerprint(path)
        except OSError:
            after = None
        if before != after:
            with self.lock:
                self.entries.pop(key, None)
            return {"integrity": "changed", "checked_at": None, "cached": False}
        result = {"integrity": integrity, "checked_at": int(self.clock())}
        with self.lock:
            self.entries[key] = (after, result)
            self.entries.move_to_end(key)
            while len(self.entries) > self.limit:
                self.entries.popitem(last=False)
        return {**result, "cached": False}
