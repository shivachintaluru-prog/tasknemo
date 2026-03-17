"""View model — build dashboard data structures for the web API.

Extracts section-assignment logic from rendering.py into pure-data functions
that return dicts instead of markdown strings.
"""

from collections import OrderedDict
from datetime import datetime, timedelta

from ..rendering import (
    TASK_TYPES,
    _format_age,
    _compute_idle_days,
    _is_due_within,
    _compute_confidence,
    _generate_next_action,
    classify_task_type,
    _extract_container_key,
    _compute_focus_priority,
    _compute_sync_health,
)
from ..dedup import merge_duplicates
from ..scoring import parse_due_hint
from ..store import load_analytics, load_run_log
from ..grouping import build_search_fallback


def _task_to_dict(task, analytics=None):
    """Enrich a task with computed fields for the frontend."""
    task_id = task.get("id", "")
    created = task.get("created", datetime.now().isoformat())
    d = dict(task)

    d["_idle_days"] = _compute_idle_days(task)
    d["_age"] = _format_age(created)
    d["_confidence"] = round(_compute_confidence(task), 2)
    d["_next_action"] = _generate_next_action(task)
    d["_focus_priority"] = _compute_focus_priority(task)
    d["_task_type"] = classify_task_type(task)
    d["_task_type_info"] = TASK_TYPES.get(d["_task_type"], TASK_TYPES["reply_align"])
    d["_is_pinned"] = (
        task_id in (analytics or {}).get("user_pins", [])
    )

    # Source breadcrumb — use stored value or synthesize from metadata
    source_ctx = task.get("source_context", "")
    if not source_ctx:
        extra = task.get("extra", {})
        src = extra.get("source", task.get("source", ""))
        if src in ("calendar", "transcript") and extra.get("meeting_title"):
            source_ctx = f"Meeting: {extra['meeting_title']}"
        elif src == "email" and task.get("description"):
            source_ctx = f"Email: {task['description'][:60]}"
        elif src == "flagged_email" and task.get("description"):
            source_ctx = f"Flagged: {task['description'][:60]}"
    d["_source_context"] = source_ctx

    # Build links array for frontend
    links = []
    source = task.get("source", "")
    source_link = task.get("source_link", "")
    teams_link = task.get("teams_link", "")
    link_labels = {"email": "Open in Outlook", "calendar": "Open Meeting"}

    if source in link_labels and source_link:
        links.append({"label": link_labels[source], "url": source_link, "source": source})
    if teams_link:
        links.append({"label": "Open in Teams", "url": teams_link, "source": "teams"})
    for alt in task.get("source_metadata", {}).get("alternate_links", []):
        alt_label = link_labels.get(alt.get("source", ""), "Open Link")
        alt_url = alt.get("link", "")
        if alt_url:
            links.append({"label": alt_label, "url": alt_url, "source": alt.get("source", "")})
    fallback = build_search_fallback(task)
    if fallback:
        links.append({"label": "Search", "url": "", "fallback": fallback, "source": "search"})
    d["_links"] = links

    # Due date parsed
    due_dt = parse_due_hint(task.get("due_hint", ""))
    if due_dt:
        d["_due_date"] = due_dt.isoformat()
        d["_is_overdue"] = due_dt < datetime.now()
    else:
        d["_due_date"] = None
        d["_is_overdue"] = False

    return d


def build_dashboard_data(tasks, config, run_stats=None, analytics=None):
    """Build the full dashboard data structure for the web frontend.

    Returns a dict with stats, sections, and metadata.
    """
    now = datetime.now()
    run_stats = run_stats or {}
    if analytics is None:
        analytics = load_analytics()

    all_tasks_map = {t["id"]: t for t in tasks}

    subtask_ids_set = set()
    for t in tasks:
        for sid in t.get("subtask_ids", []):
            subtask_ids_set.add(sid)

    def is_root(t):
        return t["id"] not in subtask_ids_set

    merge_duplicates(tasks)

    for t in tasks:
        if t.get("state") != "closed":
            t["_next_action"] = _generate_next_action(t)

    active = [t for t in tasks if t.get("state") != "closed" and is_root(t)]
    inbound_active = [t for t in active if t.get("direction", "inbound") == "inbound"]
    outbound_active = [t for t in active if t.get("direction") == "outbound"]

    # Pinned tasks (all pinned, regardless of state, among active root tasks)
    user_pins = set(analytics.get("user_pins", []))
    pinned = [t for t in active if t["id"] in user_pins]
    pinned.sort(key=lambda t: t.get("score", 0), reverse=True)

    # Focus section
    focus_sorted = sorted(inbound_active, key=lambda t: _compute_focus_priority(t), reverse=True)
    focus_candidates = [t for t in focus_sorted if t.get("state") in ("open", "needs_followup")]
    if len(focus_candidates) >= 3:
        focus = focus_candidates[:5]
    elif focus_candidates:
        focus = focus_candidates[:]
        remaining = [
            t for t in focus_sorted
            if t not in focus and t.get("state") in ("open", "needs_followup", "waiting")
        ]
        for t in remaining:
            if len(focus) >= 3:
                break
            focus.append(t)
    else:
        focus = []
    focus_ids = {t["id"] for t in focus}

    # Due soon
    due_soon = [
        t for t in inbound_active
        if _is_due_within(t, 48) and t["id"] not in focus_ids
    ]
    due_soon.sort(key=lambda t: parse_due_hint(t.get("due_hint", "")) or datetime.max)
    due_soon_ids = {t["id"] for t in due_soon}

    # Open grouped
    open_grouped = [
        t for t in inbound_active
        if t.get("state") == "open" and t["id"] not in focus_ids and t["id"] not in due_soon_ids
    ]

    # Stale / needs followup
    placed_inbound = focus_ids | due_soon_ids | {t["id"] for t in open_grouped}
    stale = [
        t for t in inbound_active
        if t.get("state") in ("waiting", "needs_followup") and t["id"] not in placed_inbound
    ]

    # Outbound sections
    nudge_due = [t for t in outbound_active if _compute_idle_days(t) >= 3 or _is_due_within(t, 48)]
    nudge_due_ids = {t["id"] for t in nudge_due}
    waiting_outbound = [t for t in outbound_active if t["id"] not in nudge_due_ids]

    # Closed sections
    thirty_days_ago = (now - timedelta(days=30)).isoformat()
    closed_by_me = [
        t for t in tasks
        if t.get("state") == "closed" and t.get("closed_by") == "user"
        and t.get("updated", "") >= thirty_days_ago and is_root(t)
    ]

    seven_days_ago = (now - timedelta(days=7)).isoformat()
    recently_closed = [
        t for t in tasks
        if t.get("state") == "closed" and t.get("updated", "") >= seven_days_ago
        and is_root(t) and t.get("closed_by") != "user"
    ]

    # Build open groups
    open_groups = []
    ungrouped = []
    if open_grouped:
        containers = OrderedDict()
        for t in open_grouped:
            key, c_title, src_type, src_link = _extract_container_key(t)
            if key not in containers:
                containers[key] = {
                    "title": c_title, "source_type": src_type,
                    "source_link": src_link, "tasks": [],
                }
            containers[key]["tasks"].append(t)

        for ckey, cdata in containers.items():
            enriched = [_task_to_dict(t, analytics) for t in cdata["tasks"]]
            if len(cdata["tasks"]) >= 2:
                open_groups.append({
                    "key": ckey,
                    "title": cdata["title"],
                    "source_type": cdata["source_type"],
                    "source_link": cdata["source_link"],
                    "tasks": enriched,
                })
            else:
                ungrouped.extend(enriched)

    # Stats
    stale_count = len([t for t in active if _compute_idle_days(t) >= 3])
    open_count = len([t for t in active if t.get("state") == "open"])
    total_tasks = len(tasks)
    total_closed = len([t for t in tasks if t.get("state") == "closed"])

    last_run = config.get("last_run")
    if last_run:
        try:
            last_synced = datetime.fromisoformat(last_run).strftime("%b %d, %H:%M")
        except (ValueError, TypeError):
            last_synced = "unknown"
    else:
        last_synced = "never"

    sync_health = _compute_sync_health(config)

    return {
        "stats": {
            "focus_count": len(focus),
            "due_soon_count": len(due_soon),
            "nudge_count": len(nudge_due),
            "stale_count": stale_count,
            "open_count": open_count,
            "total_tasks": total_tasks,
            "total_closed": total_closed,
            "sync_health": sync_health,
            "last_synced": last_synced,
        },
        "sections": {
            "pinned": [_task_to_dict(t, analytics) for t in pinned],
            "focus": [_task_to_dict(t, analytics) for t in focus],
            "due_soon": [_task_to_dict(t, analytics) for t in due_soon],
            "open": {
                "groups": open_groups,
                "ungrouped": ungrouped,
            },
            "stale": [_task_to_dict(t, analytics) for t in stale],
            "nudge": [_task_to_dict(t, analytics) for t in nudge_due],
            "waiting_outbound": [_task_to_dict(t, analytics) for t in waiting_outbound],
            "closed_by_me": [_task_to_dict(t, analytics) for t in closed_by_me],
            "recently_closed": [_task_to_dict(t, analytics) for t in recently_closed],
        },
        "run_stats": run_stats,
        "timestamp": now.isoformat(),
    }


def build_alerts_data(analytics=None):
    """Build alerts data from task store and analytics."""
    from ..store import load_tasks
    import json

    alerts = {
        "escalations": [],
        "stale_items": [],
    }

    if analytics:
        for task_id, entries in analytics.get("escalation_history", {}).items():
            if len(entries) >= 2:
                urgencies = [e["urgency"] for e in entries]
                if any(urgencies[i] > urgencies[i - 1] for i in range(1, len(urgencies))):
                    alerts["escalations"].append({
                        "task_id": task_id,
                        "mention_count": len(entries),
                        "urgency_pattern": urgencies,
                    })

    try:
        store = load_tasks()
    except (FileNotFoundError, json.JSONDecodeError):
        store = {"tasks": []}

    for t in store["tasks"]:
        if t.get("state") in ("open", "needs_followup"):
            created = datetime.fromisoformat(t.get("created", datetime.now().isoformat()))
            age_days = (datetime.now() - created).days
            if age_days > 7:
                alerts["stale_items"].append({
                    "task_id": t["id"],
                    "title": t.get("title", ""),
                    "age_days": age_days,
                    "state": t["state"],
                })

    return alerts
