"""QualityEvalAgent — autonomous daily diagnostics (Mode A: internal heuristics)."""

import json
import os
from datetime import datetime, timedelta

from ...agent.base import AgentBase, AgentResult


class QualityEvalAgent(AgentBase):
    agent_id = "quality_eval"
    display_name = "Quality Evaluation"

    def get_schedule(self):
        return "daily 7:00"

    def run(self, context):
        started = datetime.now()
        errors = []
        issues = []
        stats = {}

        try:
            from ...store import load_tasks, load_run_log, load_config
            from ...dedup import (
                jaccard_similarity, normalize_title_words, normalize_text,
            )

            store = load_tasks()
            tasks = store.get("tasks", [])
            config = load_config()
            task_map = {t["id"]: t for t in tasks}

            stats["total_tasks"] = len(tasks)
            non_closed = [t for t in tasks if t.get("state") != "closed"]
            stats["active_tasks"] = len(non_closed)

            # 1. Duplicate detection: Jaccard > 0.7 on title + same sender
            dup_pairs = []
            for i in range(len(non_closed)):
                for j in range(i + 1, len(non_closed)):
                    t1, t2 = non_closed[i], non_closed[j]
                    s1 = normalize_text(t1.get("sender", ""))
                    s2 = normalize_text(t2.get("sender", ""))
                    if s1 != s2 or not s1:
                        continue
                    w1 = set(normalize_title_words(t1.get("title", "")).split())
                    w2 = set(normalize_title_words(t2.get("title", "")).split())
                    sim = jaccard_similarity(w1, w2)
                    if sim > 0.7:
                        dup_pairs.append((t1["id"], t2["id"], f"{sim:.2f}"))
            if dup_pairs:
                for d1, d2, sim in dup_pairs:
                    t1, t2 = task_map.get(d1, {}), task_map.get(d2, {})
                    issues.append({
                        "category": "duplicate",
                        "severity": "medium",
                        "description": f"Potential duplicate: {d1} and {d2} (similarity: {sim})",
                        "task_ids": [d1, d2],
                        "detail": {
                            "id_a": d1,
                            "title_a": t1.get("title", ""),
                            "sender_a": t1.get("sender", ""),
                            "state_a": t1.get("state", ""),
                            "score_a": t1.get("score", 0),
                            "created_a": t1.get("created", ""),
                            "id_b": d2,
                            "title_b": t2.get("title", ""),
                            "sender_b": t2.get("sender", ""),
                            "state_b": t2.get("state", ""),
                            "score_b": t2.get("score", 0),
                            "created_b": t2.get("created", ""),
                            "similarity": sim,
                        },
                    })
            stats["duplicates_found"] = len(dup_pairs)

            # 2. Stale open items: open/needs_followup > 14 days, no state_history updates
            stale_threshold = 14
            stale_items = []
            for t in non_closed:
                if t.get("state") not in ("open", "needs_followup"):
                    continue
                created = datetime.fromisoformat(t.get("created", datetime.now().isoformat()))
                age = (datetime.now() - created).days
                if age <= stale_threshold:
                    continue
                # Check for recent state_history updates
                history = t.get("state_history", [])
                if history:
                    last_update = datetime.fromisoformat(history[-1].get("date", t.get("created", "")))
                    days_since_update = (datetime.now() - last_update).days
                    if days_since_update <= stale_threshold:
                        continue
                stale_items.append(t)
                issues.append({
                    "category": "stale",
                    "severity": "low",
                    "description": f"Stale: {t['id']} '{t.get('title', '')[:50]}' ({age}d old, no recent updates)",
                    "task_ids": [t["id"]],
                })
            stats["stale_items"] = len(stale_items)

            # 3. State inconsistencies: closed tasks with new signals
            for t in tasks:
                if t.get("state") != "closed":
                    continue
                history = t.get("state_history", [])
                if len(history) < 2:
                    continue
                # Check if last transition was unexpected
                states_seen = [h["state"] for h in history]
                for i in range(1, len(states_seen)):
                    from ...state_machine import VALID_TRANSITIONS
                    prev = states_seen[i - 1]
                    curr = states_seen[i]
                    if curr not in VALID_TRANSITIONS.get(prev, set()) and curr != prev:
                        issues.append({
                            "category": "inconsistency",
                            "severity": "high",
                            "description": f"Invalid transition in {t['id']}: {prev} -> {curr}",
                            "task_ids": [t["id"]],
                        })
                        break

            # 4. Missing fields
            missing_field_count = 0
            for t in non_closed:
                missing = []
                if not t.get("sender"):
                    missing.append("sender")
                if not t.get("source_link") and not t.get("teams_link"):
                    missing.append("source_link")
                if not t.get("dedup_hash"):
                    missing.append("dedup_hash")
                if missing:
                    missing_field_count += 1
                    issues.append({
                        "category": "missing_fields",
                        "severity": "low",
                        "description": f"{t['id']}: missing {', '.join(missing)}",
                        "task_ids": [t["id"]],
                    })
            stats["missing_fields"] = missing_field_count

            # 5. Score anomalies: tasks scoring 0 or 100
            anomaly_count = 0
            for t in non_closed:
                score = t.get("score", -1)
                if score == 0 or score == 100:
                    anomaly_count += 1
                    issues.append({
                        "category": "score_anomaly",
                        "severity": "medium",
                        "description": f"{t['id']}: score={score} (may be misconfigured)",
                        "task_ids": [t["id"]],
                    })
            stats["score_anomalies"] = anomaly_count

            # 6. Orphan subtasks
            orphan_count = 0
            for t in tasks:
                for sid in t.get("subtask_ids", []):
                    if sid not in task_map:
                        orphan_count += 1
                        issues.append({
                            "category": "orphan_subtask",
                            "severity": "medium",
                            "description": f"{t['id']}: subtask {sid} not found in store",
                            "task_ids": [t["id"], sid],
                        })
            stats["orphan_subtasks"] = orphan_count

            # 7. Sync health
            try:
                run_log = load_run_log()
                runs = run_log.get("runs", [])
                if runs:
                    last_run = runs[-1]
                    last_ts = last_run.get("timestamp", "")
                    if last_ts:
                        hours_since = (datetime.now() - datetime.fromisoformat(last_ts)).total_seconds() / 3600
                        stats["hours_since_last_sync"] = round(hours_since, 1)
                        if hours_since > 24:
                            issues.append({
                                "category": "sync_health",
                                "severity": "high",
                                "description": f"No sync in {hours_since:.0f} hours",
                                "task_ids": [],
                            })

                    # Error rate from recent runs
                    recent_runs = runs[-20:]
                    error_count = sum(1 for r in recent_runs if r.get("error") or not r.get("success", True))
                    stats["recent_error_rate"] = f"{error_count}/{len(recent_runs)}"
                    if error_count > len(recent_runs) * 0.3:
                        issues.append({
                            "category": "sync_health",
                            "severity": "high",
                            "description": f"High error rate: {error_count}/{len(recent_runs)} recent runs failed",
                            "task_ids": [],
                        })
                else:
                    stats["hours_since_last_sync"] = "never"
            except (FileNotFoundError, json.JSONDecodeError):
                stats["hours_since_last_sync"] = "unavailable"

            stats["total_issues"] = len(issues)

            # Generate Quality Report.md
            report = self._render_report(stats, issues, config)

            # Report is available via web API; no file write needed
            stats["report"] = report

        except Exception as e:
            errors.append(str(e))

        return AgentResult(
            agent_id=self.agent_id,
            started=started,
            finished=datetime.now(),
            success=len(errors) == 0,
            stats=stats,
            outputs=[report] if not errors else [],
            errors=errors,
        )

    def _render_report(self, stats, issues, config):
        """Render Quality Report.md content."""
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        lines = [
            f"# Quality Report — {now}",
            "",
        ]

        # Summary
        total = stats.get("total_issues", 0)
        high = sum(1 for i in issues if i["severity"] == "high")
        medium = sum(1 for i in issues if i["severity"] == "medium")
        low = sum(1 for i in issues if i["severity"] == "low")

        lines.append(f"> Checked {stats.get('active_tasks', 0)} active tasks "
                     f"(of {stats.get('total_tasks', 0)} total). "
                     f"Found **{total}** issues: "
                     f"{high} high, {medium} medium, {low} low.")
        lines.append("")

        # Issues by category
        categories = {}
        for issue in issues:
            cat = issue["category"]
            categories.setdefault(cat, []).append(issue)

        category_labels = {
            "duplicate": "Potential Duplicates",
            "stale": "Stale Open Items",
            "inconsistency": "State Inconsistencies",
            "missing_fields": "Missing Fields",
            "score_anomaly": "Score Anomalies",
            "orphan_subtask": "Orphan Subtasks",
            "sync_health": "Sync Health",
        }

        for cat, cat_issues in categories.items():
            label = category_labels.get(cat, cat.replace("_", " ").title())
            severity_emoji = {"high": "\U0001f534", "medium": "\U0001f7e1", "low": "\U0001f7e2"}

            lines.append(f"## {label} ({len(cat_issues)})")
            lines.append("")

            if cat == "duplicate":
                # Render duplicates as a detail table
                lines.append("| Task A | Title A | Task B | Title B | Sender | Similarity |")
                lines.append("|--------|---------|--------|---------|--------|------------|")
                for issue in cat_issues[:30]:
                    d = issue.get("detail", {})
                    title_a = d.get("title_a", "")[:50]
                    title_b = d.get("title_b", "")[:50]
                    lines.append(
                        f"| {d.get('id_a', '')} | {title_a} "
                        f"| {d.get('id_b', '')} | {title_b} "
                        f"| {d.get('sender_a', '')} | {d.get('similarity', '')} |"
                    )
                if len(cat_issues) > 30:
                    lines.append(f"| ... | +{len(cat_issues) - 30} more | | | | |")
            else:
                for issue in cat_issues[:20]:
                    emoji = severity_emoji.get(issue["severity"], "")
                    lines.append(f"- {emoji} {issue['description']}")
                if len(cat_issues) > 20:
                    lines.append(f"- ...and {len(cat_issues) - 20} more")
            lines.append("")

        # Sync health section
        lines.append("## Sync Health")
        lines.append("")
        lines.append(f"- Hours since last sync: {stats.get('hours_since_last_sync', 'unknown')}")
        lines.append(f"- Recent error rate: {stats.get('recent_error_rate', 'N/A')}")
        lines.append("")

        # Recommendations
        lines.append("## Recommendations")
        lines.append("")
        if stats.get("duplicates_found", 0) > 0:
            lines.append("- Review potential duplicates and merge where appropriate")
        if stats.get("stale_items", 0) > 5:
            lines.append("- Consider closing stale items that are no longer relevant")
        if stats.get("score_anomalies", 0) > 0:
            lines.append("- Check scoring config for tasks with extreme scores (0 or 100)")
        hours = stats.get("hours_since_last_sync", 0)
        if isinstance(hours, (int, float)) and hours > 24:
            lines.append("- Run a full sync — it's been over 24 hours")
        if not any(True for cat in categories if cat in ("duplicate", "stale", "score_anomaly")):
            lines.append("- No action needed — task store looks healthy")
        lines.append("")

        return "\n".join(lines)
