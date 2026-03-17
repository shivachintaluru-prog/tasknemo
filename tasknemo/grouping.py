"""Grouping — thread extraction, subtask grouping."""

from collections import defaultdict
from urllib.parse import urlparse, parse_qs

from .dedup import normalize_text
from .store import load_tasks, save_tasks


def extract_thread_id(teams_link):
    """Extract the thread/conversation ID from a Teams deep link."""
    if not teams_link:
        return ""
    try:
        parsed = urlparse(teams_link)
        qs = parse_qs(parsed.query)
        ctx = qs.get("context", [""])[0]
        if ctx:
            import json as _json
            ctx_obj = _json.loads(ctx)
            cid = ctx_obj.get("chatOrChannel", {}).get("id", "")
            if cid:
                return cid
        parts = parsed.path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "l" and parts[1] == "message":
            return parts[2]
    except Exception:
        pass
    return ""


def build_search_fallback(task):
    """Return a plain-text search hint for manually finding the thread."""
    from .dedup import STOP_WORDS
    sender = task.get("sender", "")
    title = task.get("title", "")
    words = [w for w in title.split() if w.lower() not in STOP_WORDS]
    keyword = " ".join(words[:3]) if words else title[:30]
    if sender:
        return f'Search "{keyword}" in chat with {sender}'
    return f'Search "{keyword}" in Teams'


def suggest_groups(tasks):
    """Group tasks by same sender + same thread_id."""
    buckets = defaultdict(list)
    for t in tasks:
        thread = t.get("thread_id", "")
        if not thread:
            continue
        sender = normalize_text(t.get("sender", ""))
        if not sender:
            continue
        key = f"{sender}|{thread}"
        buckets[key].append(t)

    groups = []
    for key, group in buckets.items():
        if len(group) < 2:
            continue
        group_sorted = sorted(group, key=lambda t: len(t.get("description", "")), reverse=True)
        parent = group_sorted[0]
        children = [t for t in group_sorted[1:] if t["id"] != parent["id"]]
        groups.append({
            "parent_id": parent["id"],
            "child_ids": [c["id"] for c in children],
        })
    return groups


def group_tasks(parent_id, child_ids, store=None):
    """Set parent/child relationships in the store. Saves to disk."""
    if store is None:
        store = load_tasks()
    task_map = {t["id"]: t for t in store["tasks"]}
    parent = task_map.get(parent_id)
    if not parent:
        return False
    existing = set(parent.get("subtask_ids", []))
    for cid in child_ids:
        child = task_map.get(cid)
        if child and cid != parent_id:
            child["parent_id"] = parent_id
            existing.add(cid)
    parent["subtask_ids"] = sorted(existing)
    save_tasks(store)
    return True


def ungroup_task(task_id, store=None):
    """Remove a task from its parent. Saves to disk."""
    if store is None:
        store = load_tasks()
    task_map = {t["id"]: t for t in store["tasks"]}
    task = task_map.get(task_id)
    if not task:
        return False
    parent_id = task.get("parent_id")
    if not parent_id:
        return False
    task["parent_id"] = None
    parent = task_map.get(parent_id)
    if parent:
        subs = parent.get("subtask_ids", [])
        parent["subtask_ids"] = [s for s in subs if s != task_id]
    save_tasks(store)
    return True
