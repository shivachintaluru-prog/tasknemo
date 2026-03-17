"""Task CRUD — add, get, list, update, prep_item."""

from datetime import datetime

from .store import load_tasks, save_tasks, load_config, save_config
from .grouping import extract_thread_id


def next_task_id(config, store=None):
    """Generate next TASK-NNN id and increment counter.

    Scans actual task IDs to find the true max, so even if the config
    counter is reset the function will never produce a duplicate.
    """
    if store is None:
        store = load_tasks()
    existing_ids = {t["id"] for t in store.get("tasks", [])}

    # Always compute max from actual data, never trust counter alone
    max_existing = 0
    for tid in existing_ids:
        if tid.startswith("TASK-"):
            try:
                max_existing = max(max_existing, int(tid.split("-")[1]))
            except (ValueError, IndexError):
                pass

    # Start from whichever is higher: config counter or actual max + 1
    num = max(config.get("next_task_id", 1), max_existing + 1)
    task_id = f"TASK-{num:03d}"

    # Safety: still skip any collision (shouldn't happen but belt-and-suspenders)
    while task_id in existing_ids:
        num += 1
        task_id = f"TASK-{num:03d}"

    config["next_task_id"] = num + 1
    return task_id


def add_task(task_dict, config):
    """Add a new task to the store. Returns the assigned task ID."""
    store = load_tasks()
    task_id = next_task_id(config, store)
    task_dict["id"] = task_id
    task_dict.setdefault("state", "open")
    if task_dict.get("direction") == "outbound" and task_dict.get("state") == "open":
        task_dict["state"] = "waiting"
    task_dict.setdefault("score", 0)
    task_dict.setdefault("score_breakdown", {})
    source = task_dict.get("source", "teams")
    source_labels = {"teams": "Teams", "email": "email", "calendar": "calendar",
                     "doc_mentions": "Document Mention", "all_received": "Teams message",
                     "key_contacts": "key contact message", "flagged_email": "flagged email",
                     "planner": "Planner/To-Do"}
    initial_state = task_dict.get("state", "open")
    reason = f"Extracted from {source_labels.get(source, source)}"
    task_dict.setdefault("state_history", [
        {"state": initial_state, "reason": reason, "date": datetime.now().isoformat()}
    ])
    task_dict.setdefault("times_seen", 1)
    # Persist source breadcrumb from extraction metadata
    extra = task_dict.get("extra", {})
    if extra.get("source_context"):
        task_dict.setdefault("source_context", extra["source_context"])
    task_dict.setdefault("source_context", "")
    # Use actual message date when available, fall back to sync time
    if extra.get("extracted_date"):
        task_dict.setdefault("created", extra["extracted_date"] + "T00:00:00")
    task_dict.setdefault("created", datetime.now().isoformat())
    task_dict.setdefault("updated", datetime.now().isoformat())
    task_dict.setdefault("source", "teams")
    task_dict.setdefault("source_link", "")
    task_dict.setdefault("source_metadata", {})
    task_dict.setdefault("direction", "inbound")
    task_dict.setdefault("parent_id", None)
    task_dict.setdefault("subtask_ids", [])
    task_dict.setdefault("thread_id", extract_thread_id(task_dict.get("teams_link", "")))
    store["tasks"].append(task_dict)
    save_tasks(store)
    save_config(config)
    return task_id


def get_task(task_id):
    """Return a single task by ID, or None."""
    store = load_tasks()
    for t in store["tasks"]:
        if t["id"] == task_id:
            return t
    return None


def list_tasks(states=None):
    """Return tasks, optionally filtered by state(s)."""
    store = load_tasks()
    tasks = store["tasks"]
    if states:
        tasks = [t for t in tasks if t.get("state") in states]
    return tasks


def update_task(task_id, updates):
    """Partial update of a task. Returns updated task or None."""
    store = load_tasks()
    for t in store["tasks"]:
        if t["id"] == task_id:
            t.update(updates)
            t["updated"] = datetime.now().isoformat()
            save_tasks(store)
            return t
    return None
