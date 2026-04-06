---
name: review
description: Run TaskNemo quality review — heuristic checks + MCP validation cross-check
argument-hint: "[--mode-b]"
---

# TaskNemo Quality Review

Run quality evaluation on the task store. Mode A (default) runs internal heuristic checks. Mode B (with `--mode-b`) additionally cross-checks against live data via MCP tools.

Arguments: $ARGUMENTS

## Mode A: Internal Heuristics

Run the built-in quality evaluation agent:

```bash
cd C:/Users/shchint/tasknemo
python -c "
from tasknemo.agents.quality_eval.agent import QualityEvalAgent
agent = QualityEvalAgent()
result = agent.run({})
print(f'Success: {result.success}')
print(f'Stats: {result.stats}')
if result.errors:
    print(f'Errors: {result.errors}')
# Print the full report if available
report = result.stats.get('report', '')
if report:
    print()
    print(report)
"
```

This checks for:
- Stale open tasks (>7 days without update)
- Tasks missing required fields (sender, title, source)
- Duplicate tasks (same title + sender)
- Tasks with no state history
- Orphaned subtasks
- Score anomalies
- Unresolved high-priority items

## Mode B: MCP Cross-Check (when `--mode-b` is passed)

### Step 1: Get Validation Query

```bash
cd C:/Users/shchint/tasknemo
python -c "
from tasknemo.queries import build_validation_query, calculate_since_date
from tasknemo.store import load_config
config = load_config()
since = calculate_since_date(config.get('last_run'), config.get('overlap_days', 2))
query = build_validation_query(since, config)
print(f'Since: {since}')
print(f'Query: {query}')
"
```

### Step 2: Run Validation via MCP

Call `mcp__mail__SearchMessages` with a query like:
```
What are all my pending tasks, action items, and open commitments since {since_date}? Include anything someone asked me to do, anything I committed to in a meeting, and any emails or messages that need my response. For each, show: who asked, what they need, and the source.
```

Also check recent Teams messages and calendar for any missed items.

### Step 3: Cross-Check Against Task Store

```bash
cd C:/Users/shchint/tasknemo
python -c "
from tasknemo.tasks import list_tasks
tasks = list_tasks(states={'open', 'waiting', 'needs_followup'})
print(f'Open tasks: {len(tasks)}')
for t in sorted(tasks, key=lambda x: x.get('score', 0), reverse=True)[:20]:
    print(f'  {t[\"id\"]} [{t.get(\"score\", 0)}] {t.get(\"state\", \"\"):16s} {t.get(\"sender\", \"\"):20s} {t.get(\"title\", \"\")}')
"
```

Compare the MCP validation results against the open tasks above. Look for:

- **Missed items**: Things in MCP results that have NO matching task in tasks.json. These need to be created.
- **Phantom tasks**: Tasks in tasks.json that MCP shows no evidence for. Flag for review but don't auto-close.
- **Stale open**: Tasks that MCP evidence shows are already resolved (replied, completed, etc.) but are still open locally. Transition these to `likely_done`.

### Step 4: Report Findings

For each discrepancy found:
1. State what was found (missed/phantom/stale)
2. Provide the source evidence
3. For missed items, offer to create them using `cmd_add()`
4. For stale items, offer to transition them

Print a summary table:
```
=== QUALITY REVIEW ===
Mode A: X issues found
Mode B: Y missed | Z phantom | W stale
```

## Output

Save the quality review report to `data/quality_review_{timestamp}.txt` for historical tracking:

```bash
cd C:/Users/shchint/tasknemo
python -c "
from datetime import datetime
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
# Write report content to file
with open(f'data/quality_review_{timestamp}.txt', 'w') as f:
    f.write('... report content ...')
print(f'Report saved: data/quality_review_{timestamp}.txt')
"
```
