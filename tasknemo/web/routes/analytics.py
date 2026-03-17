"""Analytics API — chart data, sync log, alerts, quality."""

import json
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter

from ..deps import get_config, get_tasks, get_analytics, get_run_log
from ..viewmodel import build_alerts_data
from ...rendering import _compute_confidence, _compute_idle_days

router = APIRouter(tags=["analytics"])


@router.get("/analytics/overview")
def analytics_overview():
    store = get_tasks()
    tasks = store["tasks"]
    analytics = get_analytics()

    # State distribution
    state_counts = Counter(t.get("state", "open") for t in tasks)

    # Source distribution
    source_counts = Counter(t.get("source", "unknown") for t in tasks if t.get("state") != "closed")

    # Score distribution (buckets of 10)
    active = [t for t in tasks if t.get("state") != "closed"]
    score_buckets = Counter()
    for t in active:
        bucket = min(t.get("score", 0) // 10 * 10, 90)
        score_buckets[bucket] += 1
    score_distribution = [
        {"range": f"{b}-{b+9}", "count": score_buckets.get(b, 0)}
        for b in range(0, 100, 10)
    ]

    # Direction split
    direction_counts = Counter(t.get("direction", "inbound") for t in active)

    # Age histogram
    age_buckets = Counter()
    for t in active:
        days = _compute_idle_days(t)
        if days <= 1:
            age_buckets["< 1d"] += 1
        elif days <= 3:
            age_buckets["1-3d"] += 1
        elif days <= 7:
            age_buckets["3-7d"] += 1
        elif days <= 14:
            age_buckets["7-14d"] += 1
        else:
            age_buckets["14d+"] += 1

    total_closed = state_counts.get("closed", 0)
    total_all = len(tasks)
    close_rate = round(total_closed / total_all * 100, 1) if total_all else 0

    return {
        "state_counts": dict(state_counts),
        "source_counts": dict(source_counts),
        "score_distribution": score_distribution,
        "direction_counts": dict(direction_counts),
        "age_histogram": dict(age_buckets),
        "totals": {
            "all": total_all,
            "active": len(active),
            "closed": total_closed,
            "close_rate": close_rate,
        },
    }


@router.get("/analytics/response-times")
def analytics_response_times():
    analytics = get_analytics()
    rt = analytics.get("response_times", {})
    items = [
        {"sender": k, "avg_hours": round(v["avg"], 1), "count": v["count"]}
        for k, v in sorted(rt.items(), key=lambda x: x[1]["avg"], reverse=True)
    ]
    return {"response_times": items}


@router.get("/analytics/sync-log")
def analytics_sync_log(limit: int = 20):
    run_log = get_run_log()
    runs = list(reversed(run_log.get("runs", [])))[:limit]
    return {"runs": runs}


@router.get("/analytics/trends")
def analytics_trends():
    run_log = get_run_log()
    runs = run_log.get("runs", [])

    daily = {}
    for r in runs:
        ts = r.get("timestamp", "")
        if not ts:
            continue
        try:
            day = datetime.fromisoformat(ts).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            continue
        if day not in daily:
            daily[day] = {"new": 0, "transitions": 0, "merged": 0, "runs": 0}
        daily[day]["new"] += r.get("new_tasks", 0)
        daily[day]["transitions"] += r.get("transitions", 0)
        daily[day]["merged"] += r.get("merged", 0)
        daily[day]["runs"] += 1

    return {"daily": [{"date": k, **v} for k, v in sorted(daily.items())]}


@router.get("/analytics/quality")
def analytics_quality():
    store = get_tasks()
    tasks = store["tasks"]
    active = [t for t in tasks if t.get("state") != "closed"]

    confidence_buckets = Counter()
    low_confidence = []
    for t in active:
        conf = _compute_confidence(t)
        bucket = round(conf, 1)
        confidence_buckets[str(bucket)] += 1
        if conf < 0.5:
            low_confidence.append({
                "id": t["id"],
                "title": t.get("title", ""),
                "confidence": round(conf, 2),
                "missing": _missing_fields(t),
            })

    return {
        "confidence_distribution": dict(confidence_buckets),
        "low_confidence_tasks": low_confidence[:20],
        "avg_confidence": round(
            sum(_compute_confidence(t) for t in active) / len(active), 2
        ) if active else 0,
    }


def _missing_fields(task):
    missing = []
    if not task.get("description"):
        missing.append("description")
    if not task.get("due_hint"):
        missing.append("due_hint")
    if not task.get("teams_link") and not task.get("source_link"):
        missing.append("links")
    if not task.get("sender"):
        missing.append("sender")
    return missing


@router.get("/analytics/alerts")
def analytics_alerts(limit: int = 50):
    analytics = get_analytics()
    data = build_alerts_data(analytics)
    data["stale_items"] = data["stale_items"][:limit]
    return data
