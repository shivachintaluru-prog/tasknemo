# Getting Started with TaskNemo

TaskNemo extracts your tasks from Teams, email, and calendar, scores them by priority, and renders a live dashboard in Obsidian.

---

## 1. Install (5 minutes)

```powershell
git clone https://github.com/shivachintaluru-prog/tasknemo.git
cd tasknemo
.\install.ps1
```

The installer will:
- Check that Python and npm are installed
- Set up your local data files
- Ask for your Obsidian vault path (or any folder for the dashboard output)
- Configure WorkIQ MCP for Claude Code (if installed)
- Optionally set up automatic scheduled syncs

That's it. Run `python task_dashboard.py check` to verify.

---

## 2. Start Using It

Stakeholder config is **automatic**. When the sync pipeline encounters a new sender, it queries WorkIQ to find out who they are (title, org relationship) and adds them to your config with the right priority weight. Your first sync populates everything.

You can also manually tweak weights in `data/config.json` if needed:

```json
"stakeholders": {
  "jane doe": { "name": "Jane Doe", "role": "manager", "weight": 8 }
}
```

Roles: `skip` (9), `manager` (7-8), `partner` (5), `peer` (3), `external` (1).

---

## 3. Use It

### Add tasks manually

```bash
python task_dashboard.py add "Review design doc" --sender "Jane Doe" --due "Friday"
```

### View your tasks

```bash
python task_dashboard.py list       # all active tasks, sorted by priority
python task_dashboard.py check      # quick status summary
```

### Close a task

```bash
python task_dashboard.py close TASK-001
```

### Auto-sync from Teams/email/calendar (requires Claude Code + WorkIQ)

```bash
cd tasknemo
claude
# Then say: "Run a full TaskNemo sync"
```

Or run it headless: `.\full_sync.ps1`

---

## 4. View the Dashboard

Open your vault folder in Obsidian. The dashboard renders as `TaskNemo.md` with sections:

| Section | What's in it |
|---|---|
| **Focus Now** | Your highest-priority open tasks |
| **Open** | All active tasks |
| **Waiting** | Tasks blocked on someone's input |
| **Needs Follow-up** | Stale tasks you should nudge |
| **Waiting on Others** | Things you asked others to do |
| **Recently Closed** | Tasks closed in the last few days |

No Obsidian? The file is standard markdown -- open it in any editor.

---

## 5. Stay Updated

When the repo gets updates:

```powershell
.\update.ps1
```

This pulls code, merges new config keys (without touching your stakeholders), and migrates tasks.

---

## Quick Reference

| Command | What it does |
|---|---|
| `init` | First-time setup |
| `check` | Quick status |
| `list` | Show all active tasks |
| `add "title"` | Create a task (`--sender`, `--due`, `--desc`) |
| `close TASK-ID` | Close a task |
| `pin TASK-ID` | Boost a task's priority |
| `refresh` | Re-run state machine + re-render dashboard |
| `upgrade` | Apply config/schema updates after `git pull` |

All commands: `python task_dashboard.py <command>`

---

## Need Help?

- Full docs: see `INSTALL.md` for detailed setup, architecture, and troubleshooting
- Pipeline internals: see `SKILL.md` for the sync pipeline and item schema
- Tests: `python -m pytest tests/ -v`
