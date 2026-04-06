"""Pipeline — sync_prepare, process_source_items, run_transitions, finalize_sync."""

from datetime import datetime

from .store import load_config, save_config, load_tasks, save_tasks, load_analytics, load_run_log
from .tasks import list_tasks, add_task
from .queries import calculate_since_date, build_all_queries
from .dedup import find_cross_source_match, merge_cross_source_signal
from .state_machine import evaluate_transitions, match_conversation_to_tasks
from .scoring import score_all_tasks, score_task
from .analytics import record_response_time
from .notifications import _notify, _build_change_summary


def sync_prepare():
    """Prepare sync context — the first step of the pipeline."""
    config = load_config()

    pre_closed = []
    inbox_ids = []

    since_date = calculate_since_date(
        config.get("last_run"), config.get("overlap_days", 2)
    )
    since_dt = datetime.strptime(since_date, "%B %d, %Y")
    since_date_iso = since_dt.strftime("%Y-%m-%d")
    all_queries = build_all_queries(since_date, config)
    open_tasks = list_tasks(states={"open", "needs_followup", "waiting"})
    all_tasks = list_tasks()

    return {
        "config": config,
        "since_date": since_date,
        "since_date_iso": since_date_iso,
        "all_queries": all_queries,
        "open_tasks": open_tasks,
        "all_tasks": all_tasks,
        "pre_closed": pre_closed,
        "inbox_ids": inbox_ids,
        "run_stats": {
            "new_tasks": 0,
            "transitions": 0,
            "merged": 0,
            "skipped": 0,
            "source_counts": {},
        },
    }


def process_source_items(source, items, sync_context):
    """Process extracted items from a single WorkIQ source response."""
    all_tasks = sync_context.get("all_tasks", sync_context["open_tasks"])
    run_stats = sync_context["run_stats"]
    to_create = []
    merged_ids = []
    signals = []
    skipped = 0

    for item in items:
        if item.get("already_done"):
            skipped += 1
            run_stats["skipped"] += 1
            continue

        item_date = item.get("extra", {}).get("extracted_date", "")
        since_iso = sync_context.get("since_date_iso", "")
        if item_date and since_iso and item_date < since_iso:
            skipped += 1
            run_stats["skipped"] += 1
            continue

        match = find_cross_source_match(
            {"sender": item.get("sender", ""), "title": item.get("title", "")},
            all_tasks,
        )

        if match:
            if match.get("state") in ("closed", "likely_done"):
                skipped += 1
                run_stats["skipped"] += 1
                continue
            merge_cross_source_signal(
                match, source, item.get("link", "")
            )
            merged_ids.append(match["id"])
            run_stats["merged"] += 1
        else:
            to_create.append(item)

        if item.get("signal_type"):
            signals.append({
                "sender": item.get("sender", ""),
                "topic": item.get("title", ""),
                "thread_id": item.get("extra", {}).get("thread_id", ""),
                "signal_type": item["signal_type"],
                "signal": item.get("extra", {}).get("evidence", ""),
                "teams_link": item.get("link", ""),
            })

    return {
        "source": source,
        "to_create": to_create,
        "merged_ids": merged_ids,
        "signals": signals,
        "skipped": skipped,
    }


def build_completion_signals(items, open_tasks):
    """Build completion signals by matching completion evidence to open tasks."""
    signals = []
    for item in items:
        conversation = {
            "sender": item.get("sender", ""),
            "topic": item.get("topic", ""),
            "thread_id": item.get("thread_id", ""),
        }
        matched = match_conversation_to_tasks(conversation, open_tasks)
        if matched:
            signals.append({
                "task_id": matched["id"],
                "signal_type": "completion",
                "signal": item.get("evidence", "Completion detected"),
            })
    return signals


def run_transitions(conversation_signals, sync_context):
    """Run the mechanical transition sequence."""
    config = sync_context["config"]
    run_stats = sync_context["run_stats"]

    all_tasks = load_tasks()["tasks"]
    today = datetime.now().isoformat()

    transitions = evaluate_transitions(
        all_tasks, followup_signals={}, today=today,
        conversation_signals=conversation_signals, config=config,
    )
    run_stats["transitions"] = len(transitions)

    analytics = load_analytics()
    task_map = {t["id"]: t for t in all_tasks}
    for task_id, _old_state, new_state, _reason in transitions:
        if new_state in ("likely_done", "closed"):
            t = task_map.get(task_id)
            if t:
                created = datetime.fromisoformat(t.get("created", today))
                hours = (datetime.fromisoformat(today) - created).total_seconds() / 3600
                record_response_time(t.get("sender", ""), hours, analytics)

    score_all_tasks(config, analytics)
    save_tasks(load_tasks())

    config["last_run"] = today
    save_config(config)

    return {
        "transitions": transitions,
        "run_stats": run_stats,
    }


def finalize_sync(run_stats, sync_context, transitions=None, new_tasks=None):
    """Log the run and send notification summary."""
    config = sync_context["config"]

    log_run(run_stats)

    summary = _build_change_summary(
        run_stats.get("new_tasks", 0),
        len(sync_context.get("pre_closed", [])),
        run_stats.get("transitions", 0),
    )
    if summary:
        _notify("TaskNemo", summary)

    return None


def log_run(stats):
    """Append a run entry to the run log."""
    from .store import load_run_log as _load_run_log, save_run_log as _save_run_log
    log = _load_run_log()
    entry = {
        "timestamp": datetime.now().isoformat(),
        **stats,
    }
    log["runs"].append(entry)
    _save_run_log(log)
    return entry
