"""Scoring — score_task, score_all_tasks, parse_due_hint, focus_priority."""

import re
from datetime import datetime, timedelta

from .dedup import normalize_text
from .analytics import get_response_time_factor, get_escalation_bonus, get_pin_bonus
from .store import load_tasks, save_tasks, load_analytics


def score_task(task, config, analytics=None):
    """Score a task 0–100 with breakdown. Mutates task in-place."""
    breakdown = {}

    # Stakeholder weight (0–40)
    sender_key = normalize_text(task.get("sender", ""))
    stakeholder = config.get("stakeholders", {}).get(sender_key, {})
    weight = stakeholder.get("weight", 2)
    stakeholder_score = min(weight * 4, 40)
    breakdown["stakeholder"] = stakeholder_score

    # Urgency signal (0–30)
    urgency_keywords = config.get("urgency_keywords", [])
    text_to_scan = f"{task.get('title', '')} {task.get('description', '')} {task.get('due_hint', '')}".lower()
    urgency_hits = sum(1 for kw in urgency_keywords if kw.lower() in text_to_scan)
    urgency_score = min(urgency_hits * 10, 30)
    breakdown["urgency"] = urgency_score

    # Age penalty (0–20)
    created = datetime.fromisoformat(task.get("created", datetime.now().isoformat()))
    age_days = (datetime.now() - created).days
    if age_days <= 1:
        age_score = 0
    elif age_days <= 3:
        age_score = 5
    elif age_days <= 7:
        age_score = 10
    elif age_days <= 14:
        age_score = 15
    else:
        age_score = 20
    breakdown["age"] = age_score

    # Thread intensity (0–10)
    times_seen = task.get("times_seen", 1)
    thread_score = min(times_seen * 2, 10)
    breakdown["thread"] = thread_score

    # Subtask boost (0–15)
    subtask_count = len(task.get("subtask_ids", []))
    subtask_boost = min(subtask_count * 5, 15)
    breakdown["subtask_boost"] = subtask_boost

    # Calendar boost (0–5)
    cal_boost_val = config.get("scoring", {}).get("calendar_boost", 5)
    calendar_boost = cal_boost_val if task.get("source") == "calendar" else 0
    breakdown["calendar_boost"] = calendar_boost

    # Multi-source corroboration (0–5)
    alt_links = task.get("source_metadata", {}).get("alternate_links", [])
    multi_source = 5 if alt_links else 0
    breakdown["multi_source"] = multi_source

    # Analytics-based components
    response_time = get_response_time_factor(task.get("sender", ""), analytics)
    breakdown["response_time"] = response_time

    escalation = get_escalation_bonus(task.get("id", ""), analytics)
    breakdown["escalation"] = escalation

    pin = get_pin_bonus(task.get("id", ""), analytics)
    breakdown["pin"] = pin

    # Manual/inbox task boost
    if task.get("source") == "manual":
        manual_boost = config.get("scoring", {}).get("manual_boost", 15)
    else:
        manual_boost = 0
    breakdown["manual_boost"] = manual_boost

    # @mention boost (0-15)
    mention_boost = 0
    mention_patterns = ["@mention", "mentioned you", "tagged you in", "@" + config.get("user_name", "").lower()]
    for pattern in mention_patterns:
        if pattern and pattern in text_to_scan:
            mention_boost = 15
            break
    breakdown["mention_boost"] = mention_boost

    # User priority boost (from --priority flag)
    user_priority = task.get("user_priority", 0)
    breakdown["user_priority_boost"] = user_priority

    total = (stakeholder_score + urgency_score + age_score + thread_score
             + subtask_boost + calendar_boost + multi_source
             + response_time + escalation + pin + manual_boost
             + mention_boost + user_priority)
    task["score"] = min(total, 100)
    task["score_breakdown"] = breakdown
    return task["score"]


def score_all_tasks(config, analytics=None):
    """Rescore all active (non-closed) tasks. Saves store."""
    if analytics is None:
        analytics = load_analytics()
    store = load_tasks()
    for task in store["tasks"]:
        if task.get("state") != "closed":
            score_task(task, config, analytics)
    save_tasks(store)


def parse_due_hint(due_hint, reference_date=None):
    """Parse a due_hint keyword into a datetime."""
    if not due_hint:
        return None
    ref = reference_date or datetime.now()
    hint = due_hint.strip().lower()

    if hint in ("eod", "eod today", "today", "urgent", "asap"):
        return ref.replace(hour=17, minute=0, second=0, microsecond=0)

    if hint == "tomorrow":
        return (ref + timedelta(days=1)).replace(hour=17, minute=0, second=0, microsecond=0)

    if hint in ("eow", "end of week"):
        days_ahead = (4 - ref.weekday()) % 7
        if days_ahead == 0 and ref.hour >= 17:
            days_ahead = 7
        return (ref + timedelta(days=days_ahead)).replace(hour=17, minute=0, second=0, microsecond=0)

    if hint == "next week":
        days_ahead = (7 - ref.weekday()) % 7
        if days_ahead == 0:
            days_ahead = 7
        return (ref + timedelta(days=days_ahead)).replace(hour=9, minute=0, second=0, microsecond=0)

    weekdays = {
        "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
        "friday": 4, "saturday": 5, "sunday": 6,
    }
    m = re.match(r"^eod\s+(\w+)$", hint)
    if m:
        day_name = m.group(1)
        target = weekdays.get(day_name)
        if target is not None:
            days_ahead = (target - ref.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return (ref + timedelta(days=days_ahead)).replace(hour=17, minute=0, second=0, microsecond=0)

    try:
        return datetime.fromisoformat(due_hint.strip())
    except (ValueError, TypeError):
        pass

    return None
