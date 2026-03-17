"""Dashboard API — GET /api/dashboard, GET /api/export/markdown."""

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from ..viewmodel import build_dashboard_data
from ..deps import get_config, get_tasks, get_analytics
from ...rendering import render_dashboard

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard")
def get_dashboard():
    config = get_config()
    store = get_tasks()
    analytics = get_analytics()
    data = build_dashboard_data(store["tasks"], config, analytics=analytics)
    return data


@router.get("/export/markdown", response_class=PlainTextResponse)
def export_markdown():
    """Export the dashboard as Obsidian-flavored markdown."""
    config = get_config()
    store = get_tasks()
    analytics = get_analytics()
    md = render_dashboard(store["tasks"], config, analytics=analytics)
    return md
