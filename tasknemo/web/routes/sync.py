"""Sync API — status, refresh trigger."""

from datetime import datetime

from fastapi import APIRouter

from ..deps import get_config, get_run_log

router = APIRouter(tags=["sync"])


@router.get("/sync/status")
def sync_status():
    config = get_config()
    last_run = config.get("last_run")

    hours_since = None
    if last_run:
        try:
            delta = datetime.now() - datetime.fromisoformat(last_run)
            hours_since = round(delta.total_seconds() / 3600, 1)
        except (ValueError, TypeError):
            pass

    run_log = get_run_log()
    runs = run_log.get("runs", [])
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    runs_today = sum(1 for r in runs if r.get("timestamp", "") >= today_start.isoformat())

    return {
        "last_run": last_run,
        "hours_since": hours_since,
        "runs_today": runs_today,
        "healthy": hours_since is not None and hours_since < 3,
    }


@router.post("/sync/refresh")
def sync_refresh():
    """Run a lightweight refresh (no WorkIQ queries)."""
    from ...cli import cmd_refresh
    cmd_refresh()
    return {"status": "refreshed", "timestamp": datetime.now().isoformat()}
