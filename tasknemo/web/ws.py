"""WebSocket manager + file watcher for live updates."""

import asyncio
import os
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

from ..store import DATA_DIR

MAX_CONNECTIONS = 5


class ConnectionManager:
    def __init__(self):
        self.active: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        # Reject if too many connections
        if len(self.active) >= MAX_CONNECTIONS:
            # Close oldest connection to make room
            oldest = next(iter(self.active))
            try:
                await oldest.close()
            except Exception:
                pass
            self.active.discard(oldest)

        await websocket.accept()
        self.active.add(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active.discard(websocket)

    async def broadcast(self, message: dict):
        dead = set()
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        self.active -= dead


manager = ConnectionManager()

# Track file modification times for polling-based watcher
_last_mtimes: dict[str, float] = {}
_WATCH_FILES = ["tasks.json", "analytics.json", "run_log.json"]


def _check_file_changes() -> bool:
    """Check if any watched data files have changed. Returns True if changed."""
    changed = False
    for fname in _WATCH_FILES:
        fpath = os.path.join(DATA_DIR, fname)
        try:
            mtime = os.path.getmtime(fpath)
        except OSError:
            continue
        prev = _last_mtimes.get(fname)
        if prev is not None and mtime != prev:
            changed = True
        _last_mtimes[fname] = mtime
    return changed


async def file_watcher_loop():
    """Background task that polls data files and broadcasts changes."""
    _check_file_changes()  # Initialize mtimes
    while True:
        await asyncio.sleep(2)
        if _check_file_changes():
            await asyncio.sleep(0.5)  # Debounce
            await manager.broadcast({"type": "data_changed"})


def setup_websocket(app):
    """Add WebSocket endpoint and start file watcher."""

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)
        except Exception:
            manager.disconnect(websocket)

    @app.on_event("startup")
    async def start_watcher():
        asyncio.create_task(file_watcher_loop())
