"""CLI — all cmd_* functions, main()."""

import json
import os
import re
import sys
from datetime import datetime, timedelta

from .store import (
    SCRIPT_DIR, DATA_DIR, CONFIG_PATH, TASKS_PATH, RUN_LOG_PATH, ANALYTICS_PATH,
    _ANALYTICS_DEFAULT, load_json, save_json, load_config, save_config,
    load_tasks, save_tasks, load_run_log, save_run_log, load_analytics, save_analytics,
)
from .analytics import record_response_time, pin_task, unpin_task
from .dedup import normalize_text
from .grouping import extract_thread_id, suggest_groups, group_tasks
from .tasks import add_task, get_task, list_tasks, update_task
from .scoring import score_task, score_all_tasks, parse_due_hint
from .state_machine import evaluate_transitions, transition_task
from .queries import (
    calculate_since_date, build_all_queries, build_detail_queries,
    build_workiq_queries, build_email_queries, build_calendar_query,
    build_transcript_queries, build_sent_items_query, build_outbound_query,
    build_all_received_query, build_key_contact_queries, build_doc_mentions_queries,
    build_discovery_queries, build_validation_query,
)
from .rendering import (
    render_dashboard, render_alerts, render_sync_log,
    _format_age,
)
from .notifications import _notify, _build_change_summary
from .pipeline import sync_prepare, log_run


def cmd_status():
    """Print task counts by state."""
    tasks = list_tasks()
    counts = {}
    for t in tasks:
        state = t.get("state", "unknown")
        counts[state] = counts.get(state, 0) + 1
    total = len(tasks)
    print(f"TaskNemo Status ({total} total)")
    print("-" * 35)
    for state in ["open", "waiting", "needs_followup", "likely_done", "closed"]:
        print(f"  {state:20s} {counts.get(state, 0)}")


def cmd_list():
    """Print all active tasks, with subtasks nested under parents."""
    tasks = list_tasks()
    subtask_ids = set()
    for t in tasks:
        for sid in t.get("subtask_ids", []):
            subtask_ids.add(sid)

    active = [t for t in tasks if t.get("state") != "closed" and t["id"] not in subtask_ids]
    active_sorted = sorted(active, key=lambda t: t.get("score", 0), reverse=True)
    task_map = {t["id"]: t for t in tasks}

    if not active_sorted:
        print("No active tasks.")
        return
    print(f"{'ID':10s} {'Score':6s} {'State':16s} {'Sender':20s} Title")
    print("-" * 80)
    for t in active_sorted:
        print(f"{t['id']:10s} {t.get('score', 0):<6d} {t.get('state', ''):16s} {t.get('sender', ''):20s} {t.get('title', '')}")
        for sid in t.get("subtask_ids", []):
            child = task_map.get(sid)
            if child and child.get("state") != "closed":
                print(f"  {'+-' + child['id']:10s} {child.get('score', 0):<6d} {child.get('state', ''):16s} {child.get('sender', ''):20s} {child.get('title', '')}")


def cmd_close(task_id):
    """Manually close a task."""
    task = get_task(task_id)
    if not task:
        print(f"Task {task_id} not found.")
        return
    if task["state"] == "closed":
        print(f"Task {task_id} is already closed.")
        return
    transition_task(task, "closed", "Manually closed by user")
    task["closed_by"] = "user"
    update_task(task_id, task)
    print(f"Closed {task_id}: {task.get('title', '')}")


def cmd_check():
    """Lightweight status check — reads local data only."""
    config = load_config()
    tasks = list_tasks()

    last_run = config.get("last_run")
    if last_run:
        delta = datetime.now() - datetime.fromisoformat(last_run)
        hours_since = delta.total_seconds() / 3600
        print(f"Last sync: {last_run} ({_format_age(last_run)})")
    else:
        hours_since = float("inf")
        print("Last sync: never")

    counts = {}
    for t in tasks:
        state = t.get("state", "unknown")
        counts[state] = counts.get(state, 0) + 1
    total = len(tasks)
    print(f"\nTasks: {total} total")
    for state in ["open", "waiting", "needs_followup", "likely_done", "closed"]:
        c = counts.get(state, 0)
        if c:
            print(f"  {state:20s} {c}")

    active = [t for t in tasks if t.get("state") not in ("closed", "likely_done")]
    focus = sorted(active, key=lambda t: t.get("score", 0), reverse=True)
    focus = [t for t in focus if t.get("score", 0) >= 70][:3]
    if focus:
        print("\nFocus now:")
        for t in focus:
            print(f"  [{t.get('score', 0)}] {t['id']}: {t.get('title', '')}")

    stale = [t for t in active if t.get("state") in ("open", "needs_followup")
             and (datetime.now() - datetime.fromisoformat(
                 t.get("created", datetime.now().isoformat()))).days > 7]
    if stale:
        print(f"\nStale items: {len(stale)}")

    threshold = config.get("full_sync_threshold_hours", 8)
    if hours_since > threshold:
        print(f"\n>> Full sync recommended (>{threshold}h since last run)")


def cmd_sync_info():
    """Print compact pipeline instructions for Claude Code orchestration."""
    ctx = sync_prepare()
    config = ctx["config"]
    all_queries = ctx["all_queries"]
    open_tasks = ctx["open_tasks"]
    pre_closed = ctx["pre_closed"]
    since = ctx["since_date"]

    if pre_closed:
        print(f"[pre-sync] Closed {len(pre_closed)} tasks marked done: {', '.join(pre_closed)}")

    inbox_ids = ctx.get("inbox_ids", [])
    if inbox_ids:
        print(f"[pre-sync] Imported {len(inbox_ids)} inbox task(s): {', '.join(inbox_ids)}")

    print("=== TaskNemo Sync ===")
    print(f"Since: {since} | Last run: {config.get('last_run', 'never')} | Open tasks: {len(open_tasks)}")
    print()

    if "phase1" in all_queries:
        query_num = 1
        print("--- Phase 1: Discovery (run all in parallel) ---")
        for source, query in all_queries["phase1"].items():
            print(f"  {query_num}. [{source.title()} discovery] {query}")
            query_num += 1

        print()
        print("--- Phase 2: Detail (per-item, after Phase 1) ---")
        print("  For each discovered item, call:")
        print("    build_detail_queries(source, items, since_date, config)")
        print("  Process sent_items details FIRST for completion evidence.")
        print()

        print("--- Already-Targeted (run as-is) ---")
        if "transcript_discovery" in all_queries:
            print(f"  {query_num}. [Transcript discovery] {all_queries['transcript_discovery']}")
            query_num += 1
            print(f"  {query_num}. [Transcript extraction] {all_queries['transcript_extraction']}")
            query_num += 1
        if "doc_mentions" in all_queries:
            dm = all_queries["doc_mentions"]
            print(f"  {query_num}. [Doc mentions - email] {dm.get('email_notifications', '')}")
            query_num += 1
            print(f"  {query_num}. [Doc mentions - direct] {dm.get('direct_search', '')}")
            query_num += 1
        if "validation" in all_queries:
            print()
            print(f"--- Phase 3: Validation (run AFTER all extraction) ---")
            print(f"  {query_num}. [Validation] {all_queries['validation']}")
            query_num += 1
    else:
        query_num = 1
        print("WorkIQ queries (run all via ask_work_iq):")
        if "teams" in all_queries:
            print(f"  {query_num}. [Teams conversations] {all_queries['teams']['conversations']}")
            query_num += 1
        if "email" in all_queries:
            print(f"  {query_num}. [Email - all] {all_queries['email']['all']}")
            query_num += 1
        if "calendar" in all_queries:
            print(f"  {query_num}. [Calendar - all] {all_queries['calendar']['all']}")
            query_num += 1
            print(f"  {query_num}. [Transcript discovery] {all_queries['calendar']['transcript_discovery']}")
            query_num += 1
            print(f"  {query_num}. [Transcript extraction] {all_queries['calendar']['transcript_extraction']}")
            query_num += 1
        if "sent_items" in all_queries:
            print(f"  {query_num}. [Sent items] {all_queries['sent_items']}")
            query_num += 1
        if "outbound" in all_queries:
            print(f"  {query_num}. [Outbound unreplied] {all_queries['outbound']}")
            query_num += 1
        if "all_received" in all_queries:
            print(f"  {query_num}. [All received messages] {all_queries['all_received']}")
            query_num += 1
        if "key_contacts" in all_queries and all_queries["key_contacts"]:
            for name, q in all_queries["key_contacts"].items():
                print(f"  {query_num}. [Key contact: {name}] {q}")
                query_num += 1

    print(f"""
Pipeline (call in order):
  0. sync_prepare()             -> returns sync_context (already done above)
  1. Run WorkIQ queries (Phase 1 discovery, then Phase 2 detail per item)
  2. For each source response:
     - Extract items as [{{sender, title, link, direction, signal_type, already_done, extra}}]
     - Call process_source_items(source, items, sync_context)
     - For each item in result["to_create"]: call add_task(item, config)
  3. Build completion signals from conversation analysis:
     - Call build_completion_signals(completion_items, open_tasks)
  4. Call run_transitions(all_signals, sync_context)
  5. Run validation query — compare against extracted tasks, verify gaps
  6. Call finalize_sync(run_stats, sync_context)

CRITICAL: Always check sent items BEFORE creating tasks. Transcripts
are the richest task source — extract BOTH inbound and outbound.""")


def cmd_migrate():
    """Migrate existing tasks: add grouping fields, source fields, auto-group, rescore, re-render."""
    store = load_tasks()
    config = load_config()

    for task in store["tasks"]:
        task.setdefault("parent_id", None)
        task.setdefault("subtask_ids", [])
        if not task.get("thread_id"):
            task["thread_id"] = extract_thread_id(task.get("teams_link", ""))
        task.setdefault("source", "teams")
        task.setdefault("source_link", "")
        task.setdefault("source_metadata", {})
        task.setdefault("direction", "inbound")

    config.setdefault("sources_enabled", ["teams", "email", "calendar"])
    config.setdefault("email_query_template",
        "Show me ALL my emails since {since_date}. For each, include: sender, subject, body preview, date, whether I replied, and the Outlook link.")
    config.setdefault("email_completion_query_template",
        "Which of my action-required emails since {since_date} have been resolved? Look for emails where I already replied, the request was completed, or someone else handled it. Include the sender, subject, and evidence of resolution.")
    config.setdefault("calendar_query_template",
        "Show me ALL my calendar events since {since_date}. Include: title, date/time, attendees, any meeting notes, and the link.")
    config.setdefault("scoring", {"calendar_boost": 5})
    config.setdefault("transcript_discovery_query_template",
        "Show me ALL my meetings since {since_date} that have a recording or transcript available. For each meeting, include the title, date, attendees, and the recording/transcript link.")
    config.setdefault("transcript_extraction_query_template",
        "For each of my meetings since {since_date} that has a transcript, read the transcript and extract ALL action items and commitments. For each one include: (1) what the action item is, (2) who committed to it — me or someone else, (3) any deadline mentioned, (4) the meeting title and link. Be exhaustive — include every commitment, even small ones.")
    config.setdefault("sent_items_query_template",
        "Check my sent emails and outgoing Teams messages since {since_date}. What actions have I already completed? Look for emails I sent, documents I shared, replies I gave, and messages where I delivered on a commitment. For each, include what I did, who I sent it to, when, and the link.")
    config.setdefault("outbound_query_template",
        "Show me ALL my sent messages and emails since {since_date} where the recipient has NOT replied. Include: recipient, what I said, when, and the link.")
    config.setdefault("all_received_query_template",
        "Show me ALL messages I received in ALL Teams chats (1:1, group chats, and channels) since {since_date}. Include: sender name, full message text, chat/channel name, timestamp, and the Teams link. Do not filter by reply status. Do not summarize — show actual message content.")
    config.setdefault("key_contacts", [])
    config.setdefault("query_mode", "raw")
    config.setdefault("alerts_filename", "Task Alerts.md")
    config.setdefault("full_sync_threshold_hours", 8)
    config.setdefault("web_port", 8511)
    config.setdefault("ui_mode", "web")

    if not os.path.exists(ANALYTICS_PATH):
        save_analytics(dict(_ANALYTICS_DEFAULT))
        print("[migrate] Created data/analytics.json")

    save_tasks(store)
    save_config(config)
    print(f"[migrate] Added grouping + source + direction fields to {len(store['tasks'])} tasks.")

    groups = suggest_groups(store["tasks"])
    for g in groups:
        group_tasks(g["parent_id"], g["child_ids"], store)
        print(f"[migrate] Grouped: {g['parent_id']} <- {g['child_ids']}")

    if not groups:
        print("[migrate] No auto-groupings found.")

    for task in store["tasks"]:
        if task.get("state") != "closed":
            score_task(task, config)
    save_tasks(store)
    print("[migrate] Rescored all active tasks.")

    print("[migrate] Done.")


def cmd_pin(task_id):
    """Pin a task for priority boost, rescore, and print confirmation."""
    task = get_task(task_id)
    if not task:
        print(f"Task {task_id} not found.")
        return
    analytics = load_analytics()
    pin_task(task_id, analytics)
    config = load_config()
    score_task(task, config, analytics)
    update_task(task_id, task)
    print(f"Pinned {task_id}: {task.get('title', '')} (score: {task['score']})")


def cmd_unpin(task_id):
    """Unpin a task, rescore, and print confirmation."""
    task = get_task(task_id)
    if not task:
        print(f"Task {task_id} not found.")
        return
    analytics = load_analytics()
    unpin_task(task_id, analytics)
    config = load_config()
    score_task(task, config, analytics)
    update_task(task_id, task)
    print(f"Unpinned {task_id}: {task.get('title', '')} (score: {task['score']})")


def cmd_add(title, sender=None, source="manual", direction="inbound",
            due_hint=None, description=None, priority=None):
    """Manually add a task from CLI or Claude Code."""
    config = load_config()
    task_dict = {
        "title": title,
        "sender": sender or "me",
        "source": source,
        "direction": direction,
    }
    if due_hint:
        task_dict["due_hint"] = due_hint
    if description:
        task_dict["description"] = description
    if priority:
        priority_map = {"high": 20, "medium": 10, "low": 0}
        task_dict["user_priority"] = priority_map.get(priority.lower(), 0)
    task_dict["state_history"] = [
        {"state": "open", "reason": "Manually added", "date": datetime.now().isoformat()}
    ]
    task_id = add_task(task_dict, config)
    print(f"Created {task_id}: {title}")
    return task_id


def cmd_find(query=None, sender=None, topic=None):
    """Search tasks by keyword, sender, or topic."""
    tasks = list_tasks()
    active = [t for t in tasks if t.get("state") != "closed"]

    results = active
    if query:
        q = query.lower()
        results = [t for t in results
                   if q in t.get("title", "").lower()
                   or q in t.get("description", "").lower()]
    if sender:
        s = sender.lower()
        results = [t for t in results if s in t.get("sender", "").lower()]
    if topic:
        tp = topic.lower()
        results = [t for t in results
                   if tp in t.get("title", "").lower()
                   or tp in t.get("description", "").lower()
                   or tp in t.get("source_metadata", {}).get("meeting_title", "").lower()]

    results.sort(key=lambda t: t.get("score", 0), reverse=True)

    if not results:
        print("No matching tasks found.")
        return

    print(f"{'ID':10s} {'Score':6s} {'State':16s} {'Sender':20s} Title")
    print("-" * 80)
    for t in results:
        print(f"{t['id']:10s} {t.get('score', 0):<6d} {t.get('state', ''):16s} {t.get('sender', ''):20s} {t.get('title', '')}")


def cmd_init(force=False):
    """First-time setup: create data files and config."""
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.path.exists(CONFIG_PATH) and not force:
        print(f"Config already exists: {CONFIG_PATH}")
        print("Use --force to overwrite.")
        return
    template_path = os.path.join(DATA_DIR, "config.template.json")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            config = json.load(f)
    else:
        config = {
            "ui_mode": "web",
            "dashboard_filename": "TaskNemo.md",
            "overlap_days": 2,
            "max_followup_queries": 5,
            "followup_age_threshold_days": 3,
            "conversation_query_template": "Show me all my Teams conversations since {since_date}",
            "completion_query_template": "Which of my Teams conversations since {since_date} have been resolved or completed, where someone said thanks or confirmed something was finished?",
            "auto_close_likely_done_days": 3,
            "auto_close_stale_days": 7,
            "auto_close_open_days": 10,
            "urgency_keywords": ["urgent", "asap", "eod", "eow", "today", "tomorrow", "blocker", "blocking", "critical", "immediately", "p0", "p1", "deadline", "overdue", "time-sensitive", "high priority"],
            "completion_keywords": ["thanks", "done", "shipped", "approved", "completed", "merged", "resolved", "closed", "fixed", "lgtm", "looks good"],
            "waiting_keywords": ["waiting", "pending", "blocked on", "need input", "awaiting", "depends on", "hold", "on hold"],
            "stakeholders": {},
            "sources_enabled": ["teams", "email", "calendar"],
            "query_mode": "raw",
            "email_query_template": "Show me ALL my emails since {since_date}. For each, include: sender, subject, body preview, date, whether I replied, and the Outlook link.",
            "email_completion_query_template": "Which of my action-required emails since {since_date} have been resolved? Look for emails where I already replied, the request was completed, or someone else handled it. Include the sender, subject, and evidence of resolution.",
            "calendar_query_template": "Show me ALL my calendar events since {since_date}. Include: title, date/time, attendees, any meeting notes, and the link.",
            "transcript_discovery_query_template": "Show me ALL my meetings since {since_date} that have a recording or transcript available. For each meeting, include the title, date, attendees, and the recording/transcript link.",
            "transcript_extraction_query_template": "For each of my meetings since {since_date} that has a transcript, read the transcript and extract ALL action items and commitments. For each one include: (1) what the action item is, (2) who committed to it — me or someone else, (3) any deadline mentioned, (4) the meeting title and link. Be exhaustive — include every commitment, even small ones.",
            "sent_items_query_template": "Check my sent emails and outgoing Teams messages since {since_date}. What actions have I already completed? Look for emails I sent, documents I shared, replies I gave, and messages where I delivered on a commitment. For each, include what I did, who I sent it to, when, and the link.",
            "outbound_query_template": "Show me ALL my sent messages and emails since {since_date} where the recipient has NOT replied. Include: recipient, what I said, when, and the link.",
            "all_received_query_template": "Show me ALL messages I received in ALL Teams chats (1:1, group chats, and channels) since {since_date}. Include: sender name, full message text, chat/channel name, timestamp, and the Teams link. Do not filter by reply status. Do not summarize — show actual message content.",
            "key_contacts": [],
            "scoring": {"calendar_boost": 5},
            "last_run": None,
            "next_task_id": 1,
            "alerts_filename": "Task Alerts.md",
            "full_sync_threshold_hours": 8,
        }
    sync_freq = input("How often should full sync run? Hours between syncs [8]: ").strip()
    if sync_freq:
        try:
            config["full_sync_threshold_hours"] = int(sync_freq)
        except ValueError:
            print(f"  Invalid number '{sync_freq}', using default 8 hours.")
            config["full_sync_threshold_hours"] = 8
    save_json(CONFIG_PATH, config)
    if not os.path.exists(TASKS_PATH) or force:
        save_json(TASKS_PATH, {"tasks": []})
    if not os.path.exists(RUN_LOG_PATH) or force:
        save_json(RUN_LOG_PATH, {"runs": []})
    print(f"Initialized task dashboard in {DATA_DIR}")
    print(f"  Config:     {CONFIG_PATH}")
    print(f"  Tasks:      {TASKS_PATH}")
    print(f"  Run log:    {RUN_LOG_PATH}")
    print()
    print("Next steps:")
    print("  1. Edit data/config.json to add your stakeholders")
    print("  2. Run: python task_dashboard.py check")


def _deep_merge_defaults(template, current):
    """Merge template keys into current config, preserving existing values."""
    added = []
    for key, value in template.items():
        if key not in current:
            current[key] = value
            added.append(key)
        elif isinstance(value, dict) and isinstance(current[key], dict):
            sub_added = _deep_merge_defaults(value, current[key])
            added.extend(f"{key}.{k}" for k in sub_added)
    return added


def cmd_upgrade():
    """Merge new config keys from template into existing config."""
    if not os.path.exists(CONFIG_PATH):
        print("No config found. Run 'python task_dashboard.py init' first.")
        return

    template_path = os.path.join(DATA_DIR, "config.template.json")
    if not os.path.exists(template_path):
        print("No config.template.json found — nothing to merge.")
        print("Running migrate for task schema updates...")
        cmd_migrate()
        return

    with open(template_path, "r", encoding="utf-8") as f:
        template = json.load(f)

    config = load_config()

    added = _deep_merge_defaults(template, config)

    if "query_strategy" not in config:
        config["query_strategy"] = "two_phase"
        added.append("query_strategy")
    if "max_detail_queries_per_source" not in config:
        config["max_detail_queries_per_source"] = 25
        added.append("max_detail_queries_per_source")

    if added:
        save_config(config)
        print(f"[upgrade] Added {len(added)} new config key(s):")
        for key in added:
            print(f"  + {key}")
    else:
        print("[upgrade] Config is up to date — no new keys.")

    print()
    cmd_migrate()



def cmd_refresh():
    """Lightweight refresh — no WorkIQ queries needed."""
    config = load_config()
    analytics = load_analytics()

    store = load_tasks()
    today = datetime.now().isoformat()
    transitions = evaluate_transitions(
        store["tasks"], followup_signals={}, today=today,
        conversation_signals=[], config=config,
    )
    if transitions:
        save_tasks(store)
        for tid, old, new, reason in transitions:
            print(f"[refresh] {tid}: {old} -> {new} ({reason})")
            task_map = {t["id"]: t for t in store["tasks"]}
            if new in ("likely_done", "closed"):
                t = task_map.get(tid)
                if t:
                    created = datetime.fromisoformat(t.get("created", today))
                    hours = (datetime.fromisoformat(today) - created).total_seconds() / 3600
                    record_response_time(t.get("sender", ""), hours, analytics)

    score_all_tasks(config, analytics)

    run_stats = {
        "new_tasks": 0,
        "transitions": len(transitions),
        "merged": 0,
        "skipped": 0,
    }
    log_run(run_stats)

    summary = _build_change_summary(0, 0, len(transitions))
    if summary:
        _notify("TaskNemo", summary)

    if not transitions:
        print("[refresh] No changes.")
    print("[refresh] Done.")


def cmd_serve(host="127.0.0.1", port=8511):
    """Start the TaskNemo web dashboard."""
    import uvicorn
    from .web.app import create_app
    app = create_app()
    print(f"[serve] TaskNemo web dashboard at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port)


def cmd_tray(host="127.0.0.1", port=8511):
    """Start TaskNemo with system tray icon."""
    from .tray.tray_app import run_tray
    run_tray(host=host, port=port)


def cmd_install_tray():
    """Register TaskNemo tray app to auto-start at login."""
    from .tray.autostart import install_autostart
    install_autostart()


def main():
    if len(sys.argv) < 2:
        cmd_sync_info()
        return

    command = sys.argv[1].lower()

    try:
        if command == "init":
            force = "--force" in sys.argv[2:]
            cmd_init(force=force)
        elif command == "sync":
            cmd_sync_info()
        elif command == "status":
            cmd_status()
        elif command == "list":
            cmd_list()
        elif command == "close" and len(sys.argv) >= 3:
            cmd_close(sys.argv[2].upper())
        elif command == "pin" and len(sys.argv) >= 3:
            cmd_pin(sys.argv[2].upper())
        elif command == "unpin" and len(sys.argv) >= 3:
            cmd_unpin(sys.argv[2].upper())
        elif command == "check":
            cmd_check()
        elif command == "migrate":
            cmd_migrate()
        elif command == "upgrade":
            cmd_upgrade()
        elif command == "refresh":
            cmd_refresh()
        elif command == "serve":
            host = "127.0.0.1"
            port = 8511
            for i, arg in enumerate(sys.argv[2:], 2):
                if arg == "--host" and i + 1 < len(sys.argv):
                    host = sys.argv[i + 1]
                if arg == "--port" and i + 1 < len(sys.argv):
                    port = int(sys.argv[i + 1])
            cmd_serve(host=host, port=port)
        elif command == "tray":
            host = "127.0.0.1"
            port = 8511
            for i, arg in enumerate(sys.argv[2:], 2):
                if arg == "--host" and i + 1 < len(sys.argv):
                    host = sys.argv[i + 1]
                if arg == "--port" and i + 1 < len(sys.argv):
                    port = int(sys.argv[i + 1])
            cmd_tray(host=host, port=port)
        elif command == "install-tray":
            cmd_install_tray()
        elif command == "find":
            import argparse
            parser = argparse.ArgumentParser(prog=f"{sys.argv[0]} find", description="Search tasks")
            parser.add_argument("query", nargs="?", default=None, help="Search keyword")
            parser.add_argument("--sender", "-s", default=None, help="Filter by sender name")
            parser.add_argument("--topic", "-t", default=None, help="Filter by topic keyword")
            args = parser.parse_args(sys.argv[2:])
            cmd_find(query=args.query, sender=args.sender, topic=args.topic)
        elif command == "add":
            import argparse
            parser = argparse.ArgumentParser(prog=f"{sys.argv[0]} add", description="Manually add a task")
            parser.add_argument("title", help="Task title")
            parser.add_argument("--sender", "-s", default="me", help="Who assigned/requested this task")
            parser.add_argument("--due", "-d", default=None, dest="due_hint", help="Due date hint")
            parser.add_argument("--desc", default=None, dest="description", help="Task description")
            parser.add_argument("--direction", default="inbound", choices=["inbound", "outbound"])
            parser.add_argument("--source", default="manual", help="Task source label")
            parser.add_argument("--priority", "-p", default=None, choices=["high", "medium", "low"],
                                help="Priority level (high=+20, medium=+10, low=0)")
            args = parser.parse_args(sys.argv[2:])
            cmd_add(args.title, sender=args.sender, source=args.source, direction=args.direction,
                    due_hint=args.due_hint, description=args.description, priority=args.priority)
        elif command == "agent":
            _handle_agent_command()
        else:
            print(f"Usage: python {sys.argv[0]} [init|sync|status|list|close|pin|unpin TASK-ID|check|migrate|upgrade|refresh|serve|tray|install-tray|add|find|agent]")
    except FileNotFoundError as e:
        if "data" in str(e).replace("\\", "/"):
            print(f"Data file not found: {e}")
            print("Run 'python task_dashboard.py init' to set up.")
            sys.exit(1)
        raise


def _handle_agent_command():
    """Handle 'agent' subcommands."""
    if len(sys.argv) < 3:
        print("Usage: python task_dashboard.py agent [list|run|history|enable|disable] [agent_id]")
        return

    subcmd = sys.argv[2].lower()

    try:
        from .agent.registry import get_registry
        registry = get_registry()
    except ImportError:
        print("Agent framework not available.")
        return

    if subcmd == "list":
        agents = registry.list_agents()
        if not agents:
            print("No agents registered.")
            return
        print(f"{'ID':20s} {'Name':25s} {'Enabled':8s} Schedule")
        print("-" * 70)
        for a in agents:
            enabled = "Yes" if a.is_enabled() else "No"
            schedule = a.get_schedule() or "manual"
            print(f"{a.agent_id:20s} {a.display_name:25s} {enabled:8s} {schedule}")

    elif subcmd == "run" and len(sys.argv) >= 4:
        agent_id = sys.argv[3]
        agent = registry.get_agent(agent_id)
        if not agent:
            print(f"Agent '{agent_id}' not found.")
            return
        print(f"Running {agent.display_name}...")
        result = agent.run({})
        print(f"  Success: {result.success}")
        print(f"  Duration: {(result.finished - result.started).total_seconds():.1f}s")
        if result.stats:
            for k, v in result.stats.items():
                print(f"  {k}: {v}")
        if result.errors:
            for err in result.errors:
                print(f"  ERROR: {err}")

    elif subcmd == "history":
        agent_id = sys.argv[3] if len(sys.argv) >= 4 else None
        try:
            run_log = load_run_log()
            runs = run_log.get("runs", [])
            agent_runs = [r for r in runs if r.get("agent_id")]
            if agent_id:
                agent_runs = [r for r in agent_runs if r.get("agent_id") == agent_id]
            if not agent_runs:
                print("No agent runs found.")
                return
            for r in agent_runs[-10:]:
                ts = r.get("timestamp", "unknown")
                aid = r.get("agent_id", "?")
                success = r.get("success", "?")
                print(f"  {ts} | {aid} | success={success}")
        except (FileNotFoundError, json.JSONDecodeError):
            print("No run log found.")

    elif subcmd in ("enable", "disable") and len(sys.argv) >= 4:
        agent_id = sys.argv[3]
        config = load_config()
        agents_config = config.setdefault("agents", {})
        agent_cfg = agents_config.setdefault(agent_id, {})
        agent_cfg["enabled"] = (subcmd == "enable")
        save_config(config)
        print(f"Agent '{agent_id}' {'enabled' if subcmd == 'enable' else 'disabled'}.")

    else:
        print("Usage: python task_dashboard.py agent [list|run|history|enable|disable] [agent_id]")


if __name__ == "__main__":
    main()
