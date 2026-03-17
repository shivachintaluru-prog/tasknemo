# Quality Evaluation — WorkIQ Cross-Check (Mode B)

This skill performs a cross-check of TaskNemo's task store against WorkIQ data.

## When to run
- After a full sync, as a validation pass
- When the Quality Report shows gaps or suspicious patterns
- On request: `python task_dashboard.py agent run quality_eval`

## Steps

1. Run Mode A (internal heuristics) first:
   ```
   python task_dashboard.py agent run quality_eval
   ```

2. For Mode B (WorkIQ cross-check), use `build_validation_query()`:
   ```python
   from task_dashboard import build_validation_query, load_config, calculate_since_date
   config = load_config()
   since = calculate_since_date(config.get("last_run"))
   query = build_validation_query(since, config)
   ```

3. Run the validation query via WorkIQ MCP.

4. Compare WorkIQ results against tasks.json:
   - **Missed**: items in WorkIQ response not in tasks.json
   - **Phantom**: items in tasks.json with no WorkIQ backing
   - **Stale open**: items WorkIQ shows resolved but still open locally

5. For each discrepancy, verify against raw message content before acting.
   Remember: **never trust WorkIQ's interpretive summaries** to create tasks.

## Output
Results are appended to Quality Report.md in the Obsidian vault.
