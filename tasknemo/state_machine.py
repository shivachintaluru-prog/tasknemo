"""State machine — VALID_STATES, transitions, evaluate_transitions."""

from datetime import datetime

from .dedup import normalize_text, fuzzy_match


VALID_STATES = {"open", "waiting", "needs_followup", "likely_done", "closed"}

VALID_TRANSITIONS = {
    "open": {"waiting", "needs_followup", "likely_done", "closed"},
    "waiting": {"open", "needs_followup", "likely_done", "closed"},
    "needs_followup": {"open", "waiting", "likely_done", "closed"},
    "likely_done": {"open", "closed"},
    "closed": {"open", "needs_followup"},  # allow reopen or reopen-to-followup
}


def transition_task(task, new_state, reason, today=None):
    """Move task to new_state if valid. Mutates task in-place. Returns bool."""
    current = task.get("state", "open")
    if new_state not in VALID_TRANSITIONS.get(current, set()):
        return False
    today = today or datetime.now().isoformat()
    task["state"] = new_state
    task.setdefault("state_history", []).append({
        "state": new_state,
        "reason": reason,
        "date": today,
    })
    task["updated"] = today
    return True


def match_conversation_to_tasks(conversation, tasks, threshold=0.5):
    """Match a conversation theme to existing tasks."""
    conv_thread = conversation.get("thread_id", "")
    conv_sender = normalize_text(conversation.get("sender", ""))
    conv_topic = conversation.get("topic", "")

    if conv_thread:
        for task in tasks:
            if task.get("thread_id") == conv_thread:
                return task

    sender_matches = [
        t for t in tasks
        if normalize_text(t.get("sender", "")) == conv_sender
    ] if conv_sender else []

    if sender_matches and conv_topic:
        match = fuzzy_match(conv_topic, sender_matches, threshold=threshold)
        if match:
            return match

    return None


def evaluate_transitions(tasks, followup_signals=None, today=None,
                         conversation_signals=None, config=None):
    """Evaluate state transitions for a list of tasks."""
    from .grouping import extract_thread_id

    today_dt = datetime.fromisoformat(today) if today else datetime.now()
    today_str = today or today_dt.isoformat()
    followup_signals = followup_signals or {}
    config = config or {}
    transitions = []
    task_map = {t["id"]: t for t in tasks}

    if conversation_signals:
        open_tasks = [t for t in tasks if t.get("state") != "closed"]
        for conv in conversation_signals:
            matched_task = match_conversation_to_tasks(conv, open_tasks)
            if matched_task:
                task_id = matched_task["id"]
                if task_id not in followup_signals:
                    followup_signals[task_id] = {
                        "has_update": True,
                        "signal_type": conv.get("signal_type", "active"),
                        "signal": conv.get("signal", "Conversation activity detected"),
                    }
                conv_link = conv.get("teams_link", "")
                if conv_link and "context=" in conv_link:
                    matched_task["teams_link"] = conv_link
                    matched_task["thread_id"] = extract_thread_id(conv_link)

    for task in tasks:
        if task["state"] == "closed":
            continue

        task_id = task["id"]
        old_state = task["state"]
        created = datetime.fromisoformat(task.get("created", today_str))
        age_days = (today_dt - created).days
        signal = followup_signals.get(task_id, {})

        if task["state"] == "likely_done":
            last_transition = task.get("state_history", [])[-1] if task.get("state_history") else None
            if last_transition:
                ld_date = datetime.fromisoformat(last_transition["date"])
                if (today_dt - ld_date).days >= 3 and not signal.get("has_update"):
                    transition_task(task, "closed", "Auto-closed: no contradicting signal after likely_done", today_str)
                    transitions.append((task_id, old_state, "closed", "Auto-closed after likely_done timeout"))
            continue

        if signal.get("signal_type") == "completion":
            transition_task(task, "likely_done", f"Completion signal: {signal.get('signal', '')}", today_str)
            transitions.append((task_id, old_state, "likely_done", f"Completion signal detected"))
            continue

        if signal.get("signal_type") == "waiting":
            if task["state"] != "waiting":
                transition_task(task, "waiting", f"Waiting signal: {signal.get('signal', '')}", today_str)
                transitions.append((task_id, old_state, "waiting", "Waiting signal detected"))
            continue

        if signal.get("signal_type") == "active" and task["state"] in ("needs_followup",):
            transition_task(task, "open", f"Activity detected: {signal.get('signal', '')}", today_str)
            transitions.append((task_id, old_state, "open", "Activity detected in conversation"))
            continue

        if task["state"] == "needs_followup" and not signal.get("has_update"):
            nf_entry = None
            for sh in reversed(task.get("state_history", [])):
                if sh.get("state") == "needs_followup":
                    nf_entry = sh
                    break
            days_in_nf = (today_dt - datetime.fromisoformat(nf_entry["date"])).days if nf_entry else age_days
            auto_close_stale = config.get("auto_close_stale_days", 7)
            if days_in_nf >= auto_close_stale:
                transition_task(task, "closed", f"Auto-closed: in needs_followup for {days_in_nf}d", today_str)
                transitions.append((task_id, old_state, "closed", "Stale auto-close"))
                continue

        auto_close_open = config.get("auto_close_open_days", 10)
        if task["state"] == "open" and age_days >= auto_close_open and not signal.get("has_update"):
            transition_task(task, "closed", f"Auto-closed: open {age_days}d with no signals", today_str)
            transitions.append((task_id, old_state, "closed", f"Stale open auto-close after {age_days}d"))
            continue

        if task["state"] == "open" and age_days > 3 and not signal.get("has_update"):
            transition_task(task, "needs_followup", f"No update after {age_days} days", today_str)
            transitions.append((task_id, old_state, "needs_followup", f"No update after {age_days}d"))
            continue

    newly_closed = {tid for (tid, _, ns, _) in transitions if ns == "closed"}
    for parent_id in newly_closed:
        parent = task_map.get(parent_id)
        if not parent:
            continue
        for child_id in parent.get("subtask_ids", []):
            child = task_map.get(child_id)
            if child and child["state"] != "closed":
                child_old = child["state"]
                transition_task(child, "closed", "Parent task closed.", today_str)
                transitions.append((child_id, child_old, "closed", "Parent task closed."))

    return transitions
