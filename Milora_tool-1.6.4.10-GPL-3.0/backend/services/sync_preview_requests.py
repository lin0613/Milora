"""In-process single-flight state for synchronous Genshin/HSR previews."""
from __future__ import annotations

import threading
import time
import uuid


class PreviewBusy(RuntimeError):
    pass


class PreviewRequests:
    def __init__(self, clock=time.time):
        self.clock = clock
        self._guard = threading.Lock()
        self._active = {}
        self._latest = {}

    def begin(self, game, owner):
        with self._guard:
            stamp = self.clock()
            self._latest = {key: value for key, value in self._latest.items()
                            if value["status"] == "running" or stamp - value["updated_at"] < 3600}
            if game in self._active:
                raise PreviewBusy("此遊戲已有預覽正在建立，請等待既有請求完成，不要重複抓取。")
            identifier = uuid.uuid4().hex
            self._active[game] = (owner, identifier)
            self._latest[(game, owner)] = {"request_id": identifier, "status": "running",
                "started_at": stamp, "updated_at": stamp, "preview_id": ""}
            return identifier

    def finish(self, game, owner, identifier, *, preview_id="", failed=False):
        with self._guard:
            if self._active.get(game) != (owner, identifier):
                return
            self._active.pop(game)
            value = self._latest[(game, owner)]
            value.update(status="failed" if failed else "completed", preview_id=preview_id,
                         updated_at=self.clock())

    def status(self, game, owner):
        with self._guard:
            value = self._latest.get((game, owner))
            if value and (value["status"] == "running" or self.clock() - value["updated_at"] < 3600):
                return dict(value)
            return None
