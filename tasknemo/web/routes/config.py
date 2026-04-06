"""Config API — read/update configuration."""

from fastapi import APIRouter

from ..deps import get_config
from ...store import save_config

router = APIRouter(tags=["config"])


@router.get("/config")
def read_config():
    config = get_config()
    # Return a safe subset (exclude query templates for brevity)
    return {
        "stakeholders": config.get("stakeholders", {}),
        "urgency_keywords": config.get("urgency_keywords", []),
        "completion_keywords": config.get("completion_keywords", []),
        "waiting_keywords": config.get("waiting_keywords", []),
        "sources_enabled": config.get("sources_enabled", []),
        "query_mode": config.get("query_mode", "raw"),
        "overlap_days": config.get("overlap_days", 2),
        "auto_close_likely_done_days": config.get("auto_close_likely_done_days", 3),
        "auto_close_stale_days": config.get("auto_close_stale_days", 7),
        "auto_close_open_days": config.get("auto_close_open_days", 10),
        "scoring": config.get("scoring", {}),
        "web_port": config.get("web_port", 8511),
        "ui_mode": config.get("ui_mode", "web"),
    }


@router.patch("/config")
def update_config(updates: dict):
    config = get_config()

    allowed_keys = {
        "stakeholders", "urgency_keywords", "completion_keywords",
        "waiting_keywords", "sources_enabled", "overlap_days",
        "auto_close_likely_done_days", "auto_close_stale_days",
        "auto_close_open_days", "scoring", "web_port", "ui_mode",
    }
    for key, value in updates.items():
        if key in allowed_keys:
            config[key] = value

    save_config(config)
    return {"status": "updated"}
