"""Rendering — dashboard v1/v2, alerts, sync_log, write helpers."""

import json
import os
import re
from collections import OrderedDict
from datetime import datetime, timedelta

from .dedup import STOP_WORDS, normalize_text, normalize_title_words, merge_duplicates
from .scoring import parse_due_hint
from .store import load_analytics, load_tasks, load_run_log
from .grouping import build_search_fallback


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

TASK_TYPES = {
    "followup_nudge": {
        "emoji": "\U0001f514",
        "label": "Follow-up / Nudge",
        "keywords": ["follow up", "followup", "nudge", "ping", "remind", "check in", "chase"],
    },
    "schedule_book": {
        "emoji": "\U0001f4c5",
        "label": "Schedule / Book",
        "keywords": ["schedule", "book", "invite", "meeting", "calendar", "set up", "arrange"],
    },
    "draft_create": {
        "emoji": "\u270f\ufe0f",
        "label": "Draft / Create",
        "keywords": ["draft", "create", "write", "prepare", "document", "build", "design"],
    },
    "review_decide": {
        "emoji": "\U0001f50d",
        "label": "Review / Decide",
        "keywords": ["review", "decide", "approve", "evaluate", "assess", "feedback", "sign off"],
    },
    "reply_align": {
        "emoji": "\u2709\ufe0f",
        "label": "Reply / Align",
        "keywords": ["reply", "respond", "align", "update", "status", "confirm", "acknowledge"],
    },
}


def _format_age(created_str):
    """Return a human-readable age string like '2d ago' or '3h ago'."""
    created = datetime.fromisoformat(created_str)
    delta = datetime.now() - created
    days = delta.days
    if days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            return "just now"
        return f"{hours}h ago"
    if days == 1:
        return "1d ago"
    return f"{days}d ago"


def _compute_idle_days(task):
    """Days since last update (falls back to created)."""
    ts = task.get("updated") or task.get("created")
    if not ts:
        return 0
    dt = datetime.fromisoformat(ts)
    return (datetime.now() - dt).days


def _is_due_within(task, hours=48):
    """True if the task's due_hint resolves to within `hours` from now."""
    dt = parse_due_hint(task.get("due_hint", ""))
    if dt is None:
        return False
    return dt <= datetime.now() + timedelta(hours=hours)


def _compute_confidence(task):
    """Heuristic confidence score 0.0–1.0, computed at render time."""
    conf = 0.0
    if task.get("description"):
        conf += 0.2
    if task.get("due_hint"):
        conf += 0.1
    if task.get("teams_link") or task.get("source_link"):
        conf += 0.2
    if task.get("thread_id"):
        conf += 0.1
    if task.get("times_seen", 1) > 1:
        conf += 0.1
    if task.get("next_step"):
        conf += 0.1
    if task.get("source") in ("calendar", "transcript"):
        conf += 0.1
    if task.get("sender"):
        conf += 0.1
    return min(conf, 1.0)


def classify_task_type(task):
    """Classify a task into one of TASK_TYPES based on keyword scan."""
    text = " ".join([
        task.get("title", ""),
        task.get("description", ""),
        task.get("next_step", ""),
    ]).lower()
    for type_key, info in TASK_TYPES.items():
        for kw in info["keywords"]:
            if kw in text:
                return type_key
    return "reply_align"


def _generate_next_action(task):
    """Return a short next-action string for a task."""
    ns = task.get("next_step", "").strip()
    if ns:
        words = ns.split()
        return " ".join(words[:12])

    tt = classify_task_type(task)
    sender = task.get("sender", "them")
    defaults = {
        "reply_align": "Reply with status and ETA",
        "draft_create": "Draft document and share link",
        "schedule_book": "Send meeting invite",
        "review_decide": "Review and provide decision",
        "followup_nudge": f"Ping {sender} with reminder",
    }
    return defaults.get(tt, "Reply with status and ETA")


def _shorten_meeting_title(title, max_words=5):
    """Shorten a meeting title to its most meaningful words."""
    filler = {"and", "the", "for", "with", "sync", "meeting", "discussion",
              "review", "weekly", "daily", "bi-weekly", "recurring", "session",
              "call", "touchpoint", "catchup", "catch-up", "check-in"}
    words = title.split()
    if len(words) <= max_words:
        return title
    meaningful = [w for w in words if w.lower().strip("()-,") not in filler]
    if not meaningful:
        meaningful = words
    return " ".join(meaningful[:max_words])


def _extract_container_key(task):
    """Return (key, title, source_type, source_link) for grouping."""
    meta = task.get("source_metadata", {})
    meeting = meta.get("meeting_title", "")
    if meeting:
        short = _shorten_meeting_title(meeting)
        return (f"meeting:{meeting}", short, "meeting", task.get("source_link", ""))

    thread = task.get("thread_id", "")
    if thread:
        sender = task.get("sender", "Unknown")
        title_words = task.get("title", "").split()
        summary = " ".join(title_words[:4]) if title_words else "thread"
        display = f"{sender} \u2014 {summary}"
        return (f"thread:{thread}", display, "chat", task.get("teams_link", ""))

    sender = task.get("sender", "Unknown")
    title_words = task.get("title", "").split()[:5]
    fallback_title = f"{sender} \u2014 {' '.join(title_words)}" if title_words else sender
    return (f"sender:{sender}:{' '.join(title_words)}", fallback_title, "direct", "")


def _compute_focus_priority(task):
    """Priority score for Focus sorting. Not persisted."""
    score = task.get("score", 0)
    due_48h = 25 if _is_due_within(task, 48) else 0
    due_7d = 15 if _is_due_within(task, 168) else 0
    idle = min(5 * _compute_idle_days(task), 20)
    conf_penalty = -10 if _compute_confidence(task) < 0.6 else 0
    return score + due_48h + due_7d + idle + conf_penalty


def _build_links_line(task, prefix):
    """Build a single links line combining all available links."""
    parts = []
    source = task.get("source", "")
    source_link = task.get("source_link", "")
    teams_link = task.get("teams_link", "")

    link_labels = {
        "email": "Open in Outlook",
        "calendar": "Open Meeting",
    }

    if source in link_labels and source_link:
        parts.append(f"[{link_labels[source]}]({source_link})")

    if teams_link:
        parts.append(f"[Open in Teams]({teams_link})")

    alt_links = task.get("source_metadata", {}).get("alternate_links", [])
    for alt in alt_links:
        alt_label = link_labels.get(alt.get("source", ""), "Open Link")
        alt_url = alt.get("link", "")
        if alt_url:
            parts.append(f"[{alt_label}]({alt_url})")

    fallback = build_search_fallback(task)
    if fallback:
        parts.append(fallback)

    if parts:
        return f"{prefix}  \U0001f517 {' \u00b7 '.join(parts)}"
    return ""


# ---------------------------------------------------------------------------
# V1 rendering
# ---------------------------------------------------------------------------


def _render_task_item_v1(task, indent=0, all_tasks=None, section=None, analytics=None):
    """Render a single task as a markdown item (v1 layout)."""
    prefix = "  " * indent
    title = task.get("title", "Untitled")
    score = task.get("score", 0)
    description = task.get("description", "")
    next_step = task.get("next_step", "")
    sender = task.get("sender", "Unknown")
    created = task.get("created", datetime.now().isoformat())
    state = task.get("state", "open")
    task_id = task.get("id", "")
    direction = task.get("direction", "inbound")
    due_hint = task.get("due_hint", "")

    if state == "closed":
        age = _format_age(task.get("updated", created))
        return f"{prefix}- [x] ~~{task_id} | {title}~~ \u00b7 closed {age}"

    if direction == "outbound":
        lines = [f"{prefix}- [ ] **{task_id} | {title}** `Score: {score}`"]
        if due_hint:
            lines.append(f"{prefix}  \U0001f4c5 Due: {due_hint} \u00b7 \u23f1 {_format_age(created)}")
        else:
            lines.append(f"{prefix}  \u23f1 {_format_age(created)}")
        lines.append(f"{prefix}  \u2192 **{sender}** owes this")
        links_line = _build_links_line(task, prefix)
        if links_line:
            lines.append(links_line)
        return "\n".join(lines)

    lines = [f"{prefix}- [ ] **{task_id} | {title}** `Score: {score}`"]

    if due_hint:
        lines.append(f"{prefix}  \U0001f4c5 Due: {due_hint} \u00b7 \u23f1 Created: {_format_age(created)}")
    elif section == "focus":
        lines.append(f"{prefix}  \U0001f4c5 Due: \u2014 \u00b7 \u23f1 Created: {_format_age(created)}")
    else:
        lines.append(f"{prefix}  \u23f1 Created: {_format_age(created)}")

    pin_indicator = ""
    if analytics and task_id in analytics.get("user_pins", []):
        pin_indicator = " \u00b7 \U0001f4cc Pinned"
    lines.append(f"{prefix}  \U0001f464 {sender}{pin_indicator}")

    if description and next_step:
        lines.append(f"{prefix}  \U0001f4ac {description} \u00b7 Next: {next_step}")
    elif description:
        lines.append(f"{prefix}  \U0001f4ac {description}")
    elif next_step:
        lines.append(f"{prefix}  \U0001f4ac Next: {next_step}")

    links_line = _build_links_line(task, prefix)
    if links_line:
        lines.append(links_line)

    subtask_ids = task.get("subtask_ids", [])
    if subtask_ids and all_tasks:
        lines.append(f"{prefix}  - Subtasks:")
        for sid in subtask_ids:
            child = all_tasks.get(sid)
            if child:
                lines.append(_render_task_item_v1(child, indent=indent + 2, all_tasks=all_tasks,
                                                  section=section, analytics=analytics))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# V2 rendering
# ---------------------------------------------------------------------------


def _render_task_item_v2(task, indent=0, all_tasks=None, section=None, analytics=None):
    """Render a single task as a multi-line block (v2 layout)."""
    prefix = "  " * indent
    title = task.get("title", "Untitled")
    score = task.get("score", 0)
    sender = task.get("sender", "Unknown")
    created = task.get("created", datetime.now().isoformat())
    state = task.get("state", "open")
    task_id = task.get("id", "")
    direction = task.get("direction", "inbound")
    due_hint = task.get("due_hint", "")

    if state == "closed":
        age = _format_age(task.get("updated", created))
        return f"{prefix}- [x] ~~{task_id} | {title}~~ \u00b7 closed {age}"

    idle_days = _compute_idle_days(task)
    next_action = task.get("_next_action") or _generate_next_action(task)
    age = _format_age(created)

    lines = [f"{prefix}- [ ] {task_id} | {title}"]
    lines.append(f"{prefix}  Score: {score} \u00b7 Age: {age} \u00b7 Idle: {idle_days}d")
    if due_hint:
        lines.append(f"{prefix}  Due: {due_hint}")

    if direction == "outbound":
        lines.append(f"{prefix}  Assigned to: {sender}")
    else:
        lines.append(f"{prefix}  Asked by: {sender}")

    lines.append(f"{prefix}  Next: {next_action}")

    links_line = _build_links_line(task, prefix)
    if links_line:
        lines.append(links_line)

    subtask_ids = task.get("subtask_ids", [])
    if subtask_ids and all_tasks:
        lines.append(f"{prefix}  - Subtasks:")
        for sid in subtask_ids:
            child = all_tasks.get(sid)
            if child:
                lines.append(_render_task_item_v2(child, indent=indent + 2, all_tasks=all_tasks,
                                                  section=section, analytics=analytics))

    return "\n".join(lines)


def _render_task_item(task, indent=0, all_tasks=None, section=None, analytics=None):
    """Dispatcher — calls v1 or v2 based on task's _dashboard_version flag."""
    version = task.get("_dashboard_version", 2)
    if version == 1:
        return _render_task_item_v1(task, indent, all_tasks, section, analytics)
    return _render_task_item_v2(task, indent, all_tasks, section, analytics)


# ---------------------------------------------------------------------------
# Dashboard v1
# ---------------------------------------------------------------------------


def render_dashboard_v1(tasks, config, run_stats=None, analytics=None):
    """Render the full dashboard as a markdown string."""
    now = datetime.now()
    run_stats = run_stats or {}
    if analytics is None:
        analytics = load_analytics()
    all_tasks = {t["id"]: t for t in tasks}

    subtask_ids = set()
    for t in tasks:
        for sid in t.get("subtask_ids", []):
            subtask_ids.add(sid)

    def is_root(t):
        return t["id"] not in subtask_ids

    active = [t for t in tasks if t.get("state") != "closed" and is_root(t)]
    inbound_active = [t for t in active if t.get("direction", "inbound") == "inbound"]
    outbound_active = [t for t in active if t.get("direction") == "outbound"]
    active_sorted = sorted(inbound_active, key=lambda t: t.get("score", 0), reverse=True)
    outbound_sorted = sorted(outbound_active, key=lambda t: t.get("score", 0), reverse=True)

    focus = [t for t in active_sorted if t.get("score", 0) >= 70 and t.get("state") in ("open", "needs_followup")][:5]
    focus_ids = {t["id"] for t in focus}

    open_tasks = [t for t in active_sorted if t.get("state") == "open" and t["id"] not in focus_ids]
    waiting = [t for t in active_sorted if t.get("state") == "waiting"]
    needs_followup = [t for t in active_sorted if t.get("state") == "needs_followup" and t["id"] not in focus_ids]

    seven_days_ago = (now - timedelta(days=7)).isoformat()
    recently_closed = [
        t for t in tasks
        if t.get("state") == "closed" and t.get("updated", "") >= seven_days_ago and is_root(t)
    ]

    total_open = len(active)
    total_closed = len([t for t in tasks if t.get("state") == "closed" and is_root(t)])
    focus_count = len(focus)
    last_run = config.get("last_run")
    sync_age = _format_age(last_run) if last_run else "just now"

    lines = [
        "# TaskNemo",
        "",
        f"> Last synced {sync_age} | **{total_open}** open \u00b7 **{total_closed}** closed \u00b7 **{focus_count}** need attention",
        "",
    ]

    if run_stats:
        new_count = run_stats.get("new_tasks", 0)
        transitions_count = run_stats.get("transitions", 0)
        lines.append(f"> Run: +{new_count} new, {transitions_count} transitions")
        lines.append("")

    def _render_section(callout_type, title, items, empty_msg, section_key=None):
        lines.append("---")
        lines.append("")
        lines.append(f"> [!{callout_type}] {title} ({len(items)})")
        lines.append(">")
        if items:
            for i, t in enumerate(items):
                rendered = _render_task_item_v1(
                    t, all_tasks=all_tasks, section=section_key, analytics=analytics
                )
                for line in rendered.split("\n"):
                    lines.append(f"> {line}")
                if i < len(items) - 1:
                    lines.append(">")
        else:
            lines.append(f"> *{empty_msg}*")
        lines.append("")

    _render_section("warning", "Focus Now", focus,
                    "No high-priority tasks right now.", "focus")
    _render_section("todo", "Open", open_tasks,
                    "No other open tasks.", "open")
    _render_section("example", "Waiting", waiting,
                    "Nothing waiting on others.", "waiting")
    _render_section("question", "Stale \u2014 Close or Chase", needs_followup,
                    "Nothing stale \u2014 you're on top of it.", "needs_followup")
    _render_section("info", "Following Up", outbound_sorted,
                    "No pending requests to others.", "outbound")
    _render_section("success", "Recently Closed", recently_closed,
                    "No recently closed tasks.", "closed")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dashboard v2
# ---------------------------------------------------------------------------


def _compute_sync_health(config):
    """Compute sync health line from run_log.json."""
    try:
        run_log = load_run_log()
        runs = run_log.get("runs", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return ""

    if not runs:
        return ""

    last_run = runs[-1]
    last_ts = last_run.get("timestamp", "")
    if not last_ts:
        return ""

    try:
        last_dt = datetime.fromisoformat(last_ts)
        age = _format_age(last_ts)
    except (ValueError, TypeError):
        return ""

    # Count runs today
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    runs_today = sum(1 for r in runs
                     if r.get("timestamp", "") >= today_start.isoformat())
    errors_today = sum(1 for r in runs
                       if r.get("timestamp", "") >= today_start.isoformat()
                       and r.get("error"))

    hours_since = (datetime.now() - last_dt).total_seconds() / 3600
    status = "\u2713" if hours_since < 3 and errors_today == 0 else "\u26a0\ufe0f"

    return f"Sync: {status} {age} \u00b7 {runs_today} runs today ({errors_today} errors)"


def render_dashboard_v2(tasks, config, run_stats=None, analytics=None):
    """Render the full dashboard as markdown (v2 layout with grouped sections)."""
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

    focus_sorted = sorted(inbound_active, key=lambda t: _compute_focus_priority(t), reverse=True)
    focus_candidates = [t for t in focus_sorted if t.get("state") in ("open", "needs_followup")]
    if len(focus_candidates) >= 5:
        focus = focus_candidates[:5]
    elif len(focus_candidates) >= 3:
        focus = focus_candidates[:5]
    elif focus_candidates:
        focus = focus_candidates[:]
        remaining = [t for t in focus_sorted if t not in focus and t.get("state") in ("open", "needs_followup", "waiting")]
        for t in remaining:
            if len(focus) >= 3:
                break
            focus.append(t)
    else:
        focus = []
    focus_ids = {t["id"] for t in focus}

    due_soon = [
        t for t in inbound_active
        if _is_due_within(t, 48) and t["id"] not in focus_ids
    ]
    due_soon.sort(key=lambda t: parse_due_hint(t.get("due_hint", "")) or datetime.max)
    due_soon_ids = {t["id"] for t in due_soon}

    open_grouped = [
        t for t in inbound_active
        if t.get("state") == "open" and t["id"] not in focus_ids and t["id"] not in due_soon_ids
    ]

    placed_inbound = focus_ids | due_soon_ids | {t["id"] for t in open_grouped}
    needs_followup = [
        t for t in inbound_active
        if t.get("state") in ("waiting", "needs_followup") and t["id"] not in placed_inbound
    ]

    nudge_due = [t for t in outbound_active if _compute_idle_days(t) >= 3 or _is_due_within(t, 48)]
    nudge_due_ids = {t["id"] for t in nudge_due}

    waiting_outbound = [t for t in outbound_active if t["id"] not in nudge_due_ids]

    # Closed by Me (user-closed, 30 day window)
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

    focus_count = len(focus)
    stale_count = len([t for t in active if _compute_idle_days(t) >= 3])
    last_run = config.get("last_run")
    if last_run:
        try:
            ts_dt = datetime.fromisoformat(last_run)
            timestamp = ts_dt.strftime("%b %d, %H:%M")
        except (ValueError, TypeError):
            timestamp = "unknown"
    else:
        timestamp = "just now"

    # Sync health
    sync_health = _compute_sync_health(config)

    lines = [
        "# TaskNemo",
        "",
        f"> Last synced: {timestamp} | Focus: {focus_count} \u00b7 Due soon: {len(due_soon)} \u00b7 Nudge: {len(nudge_due)} \u00b7 Stale (idle \u22653d): {stale_count}",
    ]
    if sync_health:
        lines.append(f"> {sync_health}")
    lines.append("")

    if run_stats:
        new_count = run_stats.get("new_tasks", 0)
        transitions_count = run_stats.get("transitions", 0)
        lines.append(f"> Run: +{new_count} new, {transitions_count} transitions")
        lines.append("")

    # Task Inbox
    lines.append("## Task Inbox")
    lines.append("Add tasks below \u2014 they'll be imported on next sync or refresh.")
    lines.append("")
    lines.append("- ")
    lines.append("")
    lines.append("---")
    lines.append("")

    def _render_section_v2(callout_type, title, items, empty_msg, section_key=None):
        lines.append("---")
        lines.append("")
        lines.append(f"> [!{callout_type}] {title} ({len(items)} tasks)")
        lines.append(">")
        if items:
            for i, t in enumerate(items):
                rendered = _render_task_item_v2(
                    t, all_tasks=all_tasks_map, section=section_key, analytics=analytics
                )
                for line in rendered.split("\n"):
                    lines.append(f"> {line}")
                if i < len(items) - 1:
                    lines.append(">")
        else:
            lines.append(f"> *{empty_msg}*")
        lines.append("")

    def _render_grouped_open_section():
        lines.append("---")
        lines.append("")
        lines.append(f"> [!todo] \U0001f4cb Open ({len(open_grouped)} tasks)")
        lines.append(">")
        if not open_grouped:
            lines.append("> *No other open tasks.*")
            lines.append("")
            return

        containers = OrderedDict()
        for t in open_grouped:
            key, c_title, src_type, src_link = _extract_container_key(t)
            if key not in containers:
                containers[key] = {"title": c_title, "source_type": src_type, "source_link": src_link, "tasks": []}
            containers[key]["tasks"].append(t)

        grouped = [(k, c) for k, c in containers.items() if len(c["tasks"]) >= 2]
        solo_tasks = [t for _k, c in containers.items() if len(c["tasks"]) == 1 for t in c["tasks"]]

        for _ckey, cdata in grouped:
            c_title = cdata["title"]
            c_tasks = cdata["tasks"]
            c_type = cdata["source_type"]
            c_link = cdata["source_link"]
            lines.append(f"> ### {c_title} \u00b7 {len(c_tasks)} open  ({c_type})")
            if c_link:
                lines.append(f"> \U0001f517 {c_link}")

            by_type = OrderedDict()
            for t in c_tasks:
                tt = classify_task_type(t)
                by_type.setdefault(tt, []).append(t)

            shown = 0
            for _tt, tt_tasks in by_type.items():
                for t in tt_tasks:
                    rendered = _render_task_item_v2(
                        t, all_tasks=all_tasks_map, section="open", analytics=analytics
                    )
                    for line in rendered.split("\n"):
                        lines.append(f"> {line}")
                    lines.append(">")
                    shown += 1

            # Collapsible callout for overflow
            if len(c_tasks) > 15:
                lines.append(f"> > [!note]- Show all ({len(c_tasks)} tasks)")
                lines.append(f"> > Expand to see all tasks in this group.")
            lines.append(">")

        for t in solo_tasks:
            rendered = _render_task_item_v2(
                t, all_tasks=all_tasks_map, section="open", analytics=analytics
            )
            for line in rendered.split("\n"):
                lines.append(f"> {line}")
            lines.append(">")

        lines.append("")

    # My Actions
    lines.append("## My Actions")
    lines.append("")
    _render_section_v2("warning", "\U0001f525 Focus Now", focus,
                       "No high-priority tasks right now.", "focus")
    _render_section_v2("danger", "\u23f0 Due Soon", due_soon,
                       "Nothing due soon.", "due_soon")
    _render_grouped_open_section()
    _render_section_v2("example", "\U0001f50d Stale \u2014 Close or Chase", needs_followup,
                       "Nothing stale \u2014 you're on top of it.", "needs_followup")

    # Following Up
    lines.append("## Following Up")
    lines.append("")
    _render_section_v2("question", "\U0001f4e3 Nudge Needed", nudge_due,
                       "No nudges needed.", "nudge_due")
    _render_section_v2("example", "\u23f3 Waiting for Reply", waiting_outbound,
                       "Nothing waiting.", "waiting")

    # Closed by Me
    if closed_by_me:
        _render_section_v2("abstract", "\u2705 Closed by Me", closed_by_me,
                           "No tasks closed by you recently.", "closed_by_me")

    _render_section_v2("success", "\u2705 Recently Closed", recently_closed,
                       "No recently closed tasks.", "closed")

    return "\n".join(lines)


def render_dashboard(tasks, config, run_stats=None, analytics=None):
    """Dispatcher — calls v1 or v2 based on config dashboard_version."""
    version = config.get("dashboard_version", 2)
    if version == 1:
        return render_dashboard_v1(tasks, config, run_stats, analytics)
    return render_dashboard_v2(tasks, config, run_stats, analytics)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


def render_alerts(transitions, new_tasks, run_stats, analytics=None):
    """Render Task Alerts markdown with callout-based sections."""
    lines = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines.append(f"# Task Alerts \u2014 {now_str}")
    lines.append("")

    lines.append("> [!abstract] New Tasks")
    lines.append(">")
    if new_tasks:
        for t in new_tasks:
            direction = t.get("direction", "inbound")
            arrow = "<-" if direction == "inbound" else "->"
            sender = t.get("sender", "Unknown")
            lines.append(f"> - {arrow} **{t.get('title', 'Untitled')}** ({sender})")
    else:
        lines.append("> *No new tasks this sync.*")
    lines.append("")

    lines.append("> [!info] State Changes")
    lines.append(">")
    if transitions:
        for task_id, old_state, new_state, reason in transitions:
            lines.append(f"> - {task_id}: {old_state} -> {new_state} \u2014 {reason}")
    else:
        lines.append("> *No state changes.*")
    lines.append("")

    lines.append("> [!warning] Escalations")
    lines.append(">")
    escalation_items = []
    if analytics:
        for task_id, entries in analytics.get("escalation_history", {}).items():
            if len(entries) >= 2:
                urgencies = [e["urgency"] for e in entries]
                if any(urgencies[i] > urgencies[i - 1] for i in range(1, len(urgencies))):
                    escalation_items.append(
                        f"> - {task_id}: {len(entries)} mentions, urgency pattern {urgencies}"
                    )
    if escalation_items:
        lines.extend(escalation_items)
    else:
        lines.append("> *No escalation patterns detected.*")
    lines.append("")

    lines.append("> [!danger] Stale Items")
    lines.append(">")
    stale_items = []
    store = None
    try:
        store = load_tasks()
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    if store:
        for t in store["tasks"]:
            if t.get("state") in ("open", "needs_followup"):
                created = datetime.fromisoformat(t.get("created", datetime.now().isoformat()))
                age_days = (datetime.now() - created).days
                if age_days > 7:
                    stale_items.append(
                        f"> - {t['id']}: **{t.get('title', '')}** ({age_days}d old, {t['state']})"
                    )
    if stale_items:
        lines.extend(stale_items[:10])
        if len(stale_items) > 10:
            lines.append(f"> - ...and {len(stale_items) - 10} more")
    else:
        lines.append("> *No stale items.*")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sync Log
# ---------------------------------------------------------------------------


def render_sync_log(run_log_entries, max_entries=20):
    """Render a Sync Log markdown page from run_log entries (newest first)."""
    lines = ["# Sync Log", ""]
    if not run_log_entries:
        lines.append("*No syncs recorded yet.*")
        return "\n".join(lines)

    recent = list(reversed(run_log_entries))[:max_entries]
    for entry in recent:
        ts_raw = entry.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(ts_raw).strftime("%Y-%m-%d %H:%M")
        except (ValueError, TypeError):
            ts = ts_raw

        is_full = "sources_queried" in entry
        if is_full:
            callout = "[!tip] Full Sync"
        else:
            callout = "[!note] Refresh"

        new = entry.get("new_tasks", 0)
        trans = entry.get("transitions", 0)
        merged = entry.get("merged", 0)
        skipped = entry.get("skipped", 0)

        lines.append(f"> {callout} \u2014 {ts}")
        lines.append(">")
        lines.append(f"> +{new} new \u00b7 {trans} transitions \u00b7 {merged} merged \u00b7 {skipped} skipped")

        sources = entry.get("sources_queried", [])
        if sources:
            lines.append(f"> Sources: {', '.join(sources)}")

        lines.append("")

    return "\n".join(lines)


