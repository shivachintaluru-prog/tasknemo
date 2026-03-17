"""Analytics — response_time, escalation, pin tracking."""

from datetime import datetime

from .store import load_analytics, save_analytics


def record_response_time(sender, hours, analytics=None):
    """Track running average response time for a sender."""
    if analytics is None:
        analytics = load_analytics()
    key = sender.lower().strip()
    rt = analytics.setdefault("response_times", {})
    if key in rt:
        prev = rt[key]
        prev["count"] += 1
        prev["avg"] = prev["avg"] + (hours - prev["avg"]) / prev["count"]
    else:
        rt[key] = {"avg": hours, "count": 1}
    save_analytics(analytics)
    return analytics


def get_response_time_factor(sender, analytics=None):
    """Return 0-10 score factor based on avg response time."""
    if analytics is None:
        return 0
    key = sender.lower().strip()
    entry = analytics.get("response_times", {}).get(key)
    if not entry or entry["count"] < 2:
        return 0
    avg = entry["avg"]
    if avg <= 4:
        return 0
    if avg <= 12:
        return 3
    if avg <= 24:
        return 6
    return 10


def record_mention(task_id, urgency_hits, analytics=None):
    """Log a mention with its urgency level for escalation tracking."""
    if analytics is None:
        analytics = load_analytics()
    history = analytics.setdefault("escalation_history", {})
    entries = history.setdefault(task_id, [])
    if len(entries) < 5:
        entries.append({"urgency": urgency_hits, "ts": datetime.now().isoformat()})
    save_analytics(analytics)
    return analytics


def get_escalation_bonus(task_id, analytics=None):
    """Return 0-15 based on increasing urgency pattern across mentions."""
    if analytics is None:
        return 0
    entries = analytics.get("escalation_history", {}).get(task_id, [])
    if len(entries) < 2:
        return 0
    urgencies = [e["urgency"] for e in entries]
    increases = sum(1 for i in range(1, len(urgencies)) if urgencies[i] > urgencies[i - 1])
    if increases == 0:
        return 3
    return min(increases * 5 + 3, 15)


def pin_task(task_id, analytics=None):
    """Add task to user_pins list. No-op if already pinned."""
    if analytics is None:
        analytics = load_analytics()
    pins = analytics.setdefault("user_pins", [])
    if task_id not in pins:
        pins.append(task_id)
    save_analytics(analytics)
    return analytics


def unpin_task(task_id, analytics=None):
    """Remove task from user_pins list. No-op if not pinned."""
    if analytics is None:
        analytics = load_analytics()
    pins = analytics.setdefault("user_pins", [])
    if task_id in pins:
        pins.remove(task_id)
    save_analytics(analytics)
    return analytics


def get_pin_bonus(task_id, analytics=None):
    """Return 20 if task is pinned, else 0."""
    if analytics is None:
        return 0
    return 20 if task_id in analytics.get("user_pins", []) else 0
