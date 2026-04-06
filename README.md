# TaskNemo

AI-powered task tracker that auto-syncs from Teams, Email, and Calendar via Claude Code. Web dashboard at `localhost:8511`.

## Quick Start

```bash
git clone https://github.com/shivachintaluru-prog/tasknemo.git && cd tasknemo
pip install -r requirements.txt
python -m tasknemo.cli init
python -m tasknemo.cli serve
```

Open [http://localhost:8511](http://localhost:8511) in your browser.

Then in Claude Code, run `/sync` to start your first full sync.

## Prerequisites

- Python 3.10+
- Claude Code with MCP servers configured for Teams, Mail, and Calendar

## How It Works

TaskNemo uses Claude Code as the orchestration layer. The `/sync` skill calls Teams, Mail, and Calendar MCP tools to discover messages and meetings, uses Claude's NLU to extract action items, then feeds them through deterministic Python functions for dedup, scoring, state transitions, and task lifecycle management.

### Sync Pipeline

1. **Discovery** -- Query Teams chats, emails, calendar events, and sent items via MCP
2. **Extraction** -- Extract action items (inbound) and commitments waiting on others (outbound)
3. **Processing** -- Dedup against existing tasks, merge cross-source signals
4. **Transitions** -- Auto-close stale items, detect completions, update states
5. **Finalize** -- Log the run, send desktop notification

### Architecture

```
Claude Code (/sync skill)
    |
    +-- MCP Tools (Teams, Mail, Calendar)
    |       |
    |       +-- Discovery + Extraction (Claude NLU)
    |
    +-- Python Pipeline (deterministic)
    |       |
    |       +-- sync_prepare() -> process_source_items() -> run_transitions() -> finalize_sync()
    |
    +-- Data Store (data/*.json)
    |
    +-- Web Dashboard (FastAPI @ localhost:8511)
```

## Skills (Claude Code Slash Commands)

| Skill | Description |
|---|---|
| `/sync` | Full sync -- fetches Teams, Email, Calendar via MCP, extracts tasks, runs pipeline |
| `/sync --full` | Full sync with wider lookback window (7 days) |
| `/review` | Quality review -- heuristic checks on task store |
| `/review --mode-b` | Quality review + MCP cross-check for missed/phantom/stale tasks |
| `/loop 30m /sync` | Run full sync every 30 minutes in the background |

Skills are defined in `.claude/skills/` and committed to the repo.

## Web Dashboard

Start the server:

```bash
python -m tasknemo.cli serve
```

The dashboard is available at `http://localhost:8511` with API endpoints:

| Endpoint | Description |
|---|---|
| `GET /api/dashboard` | Full dashboard data (JSON) |
| `GET /api/tasks` | All tasks with filtering |
| `PATCH /api/tasks/{id}` | Update a task |
| `GET /api/analytics` | Response time and escalation analytics |
| `GET /api/sync/status` | Last sync time and health |
| `POST /api/sync/refresh` | Trigger a lightweight refresh |
| `GET /api/config` | Current configuration |
| `GET /api/export/markdown` | Dashboard as markdown |

## CLI Commands

| Command | Description |
|---|---|
| `init` | First-time setup (creates data files, prompts for sync frequency) |
| `serve` | Start the web dashboard (default: `localhost:8511`) |
| `tray` | Start with system tray icon |
| `status` | Task counts by state |
| `list` | Active tasks sorted by priority score |
| `check` | Quick status check with focus recommendations |
| `refresh` | Run state transitions and re-score |
| `close TASK-ID` | Manually close a task |
| `pin TASK-ID` | Pin a task (+20 score boost) |
| `unpin TASK-ID` | Unpin a task |
| `add "title"` | Manually add a task (`--sender`, `--due`, `--desc`, `--priority`) |
| `find "query"` | Search tasks (`--sender`, `--topic`) |

All commands: `python -m tasknemo.cli <command>`

## Configure Stakeholders

After `init`, edit `data/config.json` to add your stakeholders:

```json
"stakeholders": {
  "jane doe": {
    "name": "Jane Doe",
    "title": "PM Manager",
    "role": "manager",
    "weight": 8
  }
}
```

Roles and typical weights:
- `manager` (7-8) -- your direct manager
- `skip` (9) -- skip-level manager
- `peer` (3) -- teammates
- `partner` (5) -- cross-team partners

Higher weight = higher priority score for tasks from that person.

## Data Files

| File | Purpose |
|---|---|
| `data/config.json` | Stakeholder weights, sync frequency, query settings |
| `data/config.template.json` | Sanitized config template (checked in) |
| `data/tasks.json` | Task store (source of truth) |
| `data/run_log.json` | Audit trail per pipeline run |
| `data/analytics.json` | Response time and escalation analytics |

All data files except the template are gitignored.

## Running Tests

```bash
python -m pytest tests/ -v
```
