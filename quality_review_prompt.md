You are reviewing TaskNemo's Quality Report. Read it, then take corrective actions.

## Steps

1. Run the quality evaluation agent:
   ```
   python task_dashboard.py agent run quality_eval
   ```

2. Read `Quality Report.md` from the Obsidian vault (path in config.json `vault_path`).

3. **Act on each category:**

### Duplicates
For each duplicate pair in the table:
- Read both tasks from tasks.json (use `get_task()`)
- Decide which to keep (prefer: higher score, more metadata, newer created date)
- Close the weaker one: `update_task(TASK-XXX, {"state": "closed", "state_history": [...existing..., {"state": "closed", "reason": "Merged into TASK-YYY by QA review", "date": now}]})`
- Log what you merged and why

### Stale Open Items
For items stale >14 days:
- Check if there's any recent activity (state_history, times_seen)
- If truly abandoned, transition to `closed` with reason "Auto-closed by QA review: no activity in N days"
- If ambiguous, leave open but add to a "Needs Triage" note

### Missing Fields
- For tasks missing `dedup_hash`: compute it using `compute_dedup_hash(sender, title, created)` and update the task
- For tasks missing `sender`: skip (can't fix without source data)

### Score Anomalies
- For tasks scoring 0: rescore with `score_task(task, config, analytics)` and update
- For tasks scoring 100: check if the score is legitimate (pinned + high stakeholder + urgent) — if so, leave it

### Orphan Subtasks
- Remove orphan subtask IDs from parent's `subtask_ids` list

4. After all fixes, run:
   ```python
   score_all_tasks(config, analytics)
   ```

5. Re-render the dashboard:
   ```python
   finalize_sync(run_stats, sync_context)
   ```
   Or simpler: `cmd_refresh()`

6. Re-run quality_eval to produce an updated report showing remaining issues.

7. Print a summary: what you fixed, what you left, and why.

CRITICAL: Do NOT close tasks that have real activity. When in doubt, leave open. Only merge duplicates where you're confident they refer to the same work.
