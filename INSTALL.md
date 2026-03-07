# Installation and Usage Guide

Step-by-step guide to set up the TaskNemo on a new machine, including Claude Code integration for automated sync.

---

## Quick Install

```powershell
git clone https://github.com/shivachintaluru-prog/tasknemo.git
cd tasknemo
.\install.ps1
```

The installer checks prerequisites, installs dependencies, initializes data files, configures WorkIQ MCP, and optionally sets up scheduled tasks. Use `.\install.ps1 -VaultPath "C:\path\to\vault"` to skip the interactive prompt, or `.\install.ps1 -SkipSchedulers` to skip scheduler setup.

For manual setup, follow the steps below.

---

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Must be on PATH |
| Windows | 11 | Required for scheduled tasks and toast notifications |
| Node.js / npm | 18+ | Required for WorkIQ MCP server |
| Claude Code CLI | Latest | `npm install -g @anthropic-ai/claude-code` |
| Obsidian | Any | Optional, for viewing the rendered dashboard |

---

## Step 1 -- Clone and Initialize

```bash
git clone https://github.com/shivachintaluru-prog/tasknemo.git
cd tasknemo
python task_dashboard.py init --vault-path "C:\Users\<you>\Documents\TaskVault"
```

This creates three data files in `data/`:
- `config.json` -- your local configuration (gitignored)
- `tasks.json` -- task store
- `run_log.json` -- audit trail

If you use Obsidian, point `--vault-path` to an existing vault folder. The dashboard will render there as `TaskNemo.md`. If you don't use Obsidian, any folder works -- the output is standard markdown.

Verify the setup:

```bash
python task_dashboard.py check
```

## Step 2 -- Install Optional Dependencies

```bash
pip install -r requirements.txt
```

This installs `win11toast` for desktop notifications on Windows. The dashboard works without it -- notifications are skipped gracefully.

## Step 3 -- Configure Stakeholders

Edit `data/config.json` and populate the `stakeholders` section. This controls priority scoring -- tasks from higher-weight people score higher.

```json
"stakeholders": {
  "jane doe": {
    "name": "Jane Doe",
    "title": "PM Manager",
    "role": "manager",
    "weight": 8
  },
  "alex chen": {
    "name": "Alex Chen",
    "title": "Engineer",
    "role": "peer",
    "weight": 3
  }
}
```

**Keys must be lowercase.** Roles and suggested weights:

| Role | Weight | Description |
|---|---|---|
| `skip` | 9 | Skip-level manager |
| `manager` | 7-8 | Direct manager |
| `partner` | 5 | Cross-team partner |
| `peer` | 3 | Teammate |

## Step 4 -- Try It Out (Standalone Mode)

You can use the dashboard right away without Claude Code or WorkIQ:

```bash
# Add a task manually
python task_dashboard.py add "Review design doc" --sender "Jane Doe" --due "Friday"

# See your tasks
python task_dashboard.py list

# Quick status
python task_dashboard.py check

# Close a task
python task_dashboard.py close TASK-001

# Re-render the Obsidian dashboard
python task_dashboard.py refresh
```

This is the standalone mode -- you manage tasks manually via CLI or Obsidian inbox.

---

## Setting Up Claude Code (Full Sync Mode)

Full sync mode uses Claude Code as an orchestrator: it queries your Teams, email, and calendar through WorkIQ MCP, extracts tasks automatically, and runs the full pipeline.

### Step 5 -- Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

Verify it's working:

```bash
claude --version
```

### Step 6 -- Install and Configure WorkIQ MCP

WorkIQ is the MCP server that gives Claude Code read access to your Teams messages, emails, and calendar.

```bash
npm install -g workiq
```

Create `.mcp.json` in the project root (this file is gitignored):

```json
{
  "mcpServers": {
    "workiq": {
      "command": "workiq",
      "args": ["mcp"]
    }
  }
}
```

> **Windows note:** If `workiq` isn't found by command name, use the full path to the `.cmd` file. Find it with `where workiq` or check `%APPDATA%\npm\workiq.cmd`.

Verify WorkIQ is available:

```bash
claude
# Then in the Claude Code session, ask: "What MCP tools are available?"
# You should see ask_work_iq listed
```

### Step 7 -- Run a Full Sync (Interactive)

Open Claude Code in the project directory:

```bash
cd tasknemo
claude
```

Then tell Claude:

> Run a full TaskNemo sync following the pipeline in SKILL.md.

Claude will:
1. Call `sync_prepare()` to load config and build queries
2. Run all WorkIQ queries (sent items first, then Teams/email/calendar/transcripts)
3. Extract structured items from each response
4. Deduplicate against existing tasks
5. Run state machine transitions
6. Render the dashboard to your Obsidian vault

### Step 8 -- Run a Full Sync (Headless)

For unattended syncs, use the included prompt file:

```powershell
.\full_sync.ps1
```

This runs `claude -p` with the sync prompt from `full_sync_prompt.md` and logs output to `data/sync_log_<timestamp>.txt`.

**Required tool permissions:** The script allows these tools: `mcp__workiq__ask_work_iq`, `Bash`, `Read`, `Grep`, `Glob`, `Write`, `Edit`.

---

## Scheduling (Optional)

### Lightweight Refresh (every 30 minutes)

Runs `python task_dashboard.py refresh` -- no Claude Code or WorkIQ needed. Checks Obsidian for completed tasks, runs the state machine, and re-renders.

```powershell
.\setup_scheduler.ps1
```

Creates a Windows Task Scheduler job running every 30 minutes from 8 AM to 6 PM on weekdays.

### Full Sync (every 2 hours)

Runs the full Claude Code pipeline via `full_sync.ps1`.

```powershell
.\setup_full_sync_scheduler.ps1
```

Creates a Windows Task Scheduler job running every 2 hours from 9 AM to 7 PM on weekdays.

---

## CLI Reference

| Command | Description |
|---|---|
| `init` | First-time setup (creates data files and config) |
| `sync` | Print pipeline queries and instructions |
| `status` | Task counts by state |
| `list` | Active tasks sorted by priority score |
| `close TASK-ID` | Manually close a task |
| `pin TASK-ID` | Pin a task (+20 score boost) |
| `unpin TASK-ID` | Remove pin from a task |
| `check` | Quick status check (no external calls) |
| `migrate` | Backfill new fields to existing tasks |
| `upgrade` | Merge new config keys from template + migrate task schema |
| `refresh` | Close checked tasks, run state machine, re-render |
| `watch` | Auto-refresh on dashboard file changes (Ctrl+C to stop) |
| `add "title"` | Add a task manually (`--sender`, `--due`, `--desc`, `--direction`) |

All commands: `python task_dashboard.py <command>`

---

## How It Works

### Architecture

```
Claude Code (orchestrator)
    |
    +-- WorkIQ MCP --> Teams, Email, Calendar, Transcripts
    |
    +-- task_dashboard.py (deterministic Python)
            |
            +-- Dedup & matching
            +-- Priority scoring (stakeholder weights, urgency, age)
            +-- State machine (open -> waiting -> needs_followup -> likely_done -> closed)
            +-- Markdown rendering --> Obsidian vault
```

Claude Code handles natural language understanding -- interpreting WorkIQ responses, extracting structured task items, judging completion signals. The Python script handles everything deterministic -- dedup, scoring, state transitions, rendering.

### Task Lifecycle

```
open --> waiting --> needs_followup --> likely_done --> closed
```

- **open**: Active task needing attention
- **waiting**: Blocked on someone else's input
- **needs_followup**: Stale and needs a nudge
- **likely_done**: Completion evidence found, auto-closes after 3 days
- **closed**: Terminal state

### Dashboard Sections

| Section | What goes here |
|---|---|
| Focus Now | Top-scored open tasks |
| Open | All open tasks |
| Waiting | Tasks blocked on others |
| Needs Follow-up | Stale tasks needing a nudge |
| Waiting on Others | Outbound tasks (I asked someone) |
| Recently Closed | Tasks closed in the last few days |

### Adding Tasks Without the Pipeline

Three methods:

1. **CLI**: `python task_dashboard.py add "title" --sender "Name"`
2. **Claude Code**: Tell Claude "add a task to..." in an interactive session
3. **Obsidian Inbox**: Write tasks in `Task Inbox.md` in your vault -- imported on every `refresh`

---

## Data Files

| File | Gitignored | Description |
|---|---|---|
| `data/config.template.json` | No | Sanitized config template (checked in) |
| `data/config.json` | Yes | Your local config with stakeholders |
| `data/tasks.json` | Yes | Task store (source of truth) |
| `data/run_log.json` | Yes | Audit trail per sync run |
| `data/analytics.json` | Yes | Response time and escalation analytics |
| `data/sync_log_*.txt` | Yes | Headless sync output logs |

---

## Keeping Up to Date

When the repo gets updates (new features, bug fixes, config changes):

```powershell
.\update.ps1
```

This pulls the latest code, installs any new dependencies, merges new config keys into your local config (without overwriting your stakeholders or settings), migrates the task schema, and verifies everything works.

You can also update manually:

```bash
git pull
pip install -r requirements.txt
python task_dashboard.py upgrade
```

---

## Running Tests

```bash
python -m pytest tests/ -v
```

---

## Troubleshooting

**"Data file not found" error**
Run `python task_dashboard.py init` to create the data files.

**WorkIQ not found in Claude Code**
Check that `.mcp.json` exists in the project root and the `workiq` command path is correct. Run `where workiq` to find it.

**Python not found by scheduler**
Ensure Python is on your system PATH. The scheduler scripts auto-detect Python via `Get-Command python`.

**Toast notifications not appearing**
Install `win11toast`: `pip install win11toast`. The dashboard works without it -- notifications are optional.

**Obsidian dashboard not updating**
Check that `vault_path` in `data/config.json` points to your Obsidian vault. Run `python task_dashboard.py refresh` to force a re-render.
