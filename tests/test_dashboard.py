"""Unit tests for dashboard rendering."""

import sys
import os
import json
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import render_dashboard_v1 as render_dashboard, write_dashboard, _render_task_item_v1 as _render_task_item, _format_age, sync_dashboard_completions, _CHECKED_TASK_RE, cmd_add, sync_inbox, cmd_init, cmd_upgrade, _deep_merge_defaults
from datetime import datetime, timedelta


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_fixture_tasks():
    with open(os.path.join(FIXTURES_DIR, "sample_tasks.json"), "r") as f:
        return json.load(f)["tasks"]


def _make_config():
    return {
        "vault_path": tempfile.mkdtemp(),
        "dashboard_filename": "TaskNemo.md",
    }


class TestFormatAge:
    def test_just_now(self):
        now = datetime.now().isoformat()
        assert _format_age(now) == "just now"

    def test_hours_ago(self):
        three_hours_ago = (datetime.now() - timedelta(hours=3)).isoformat()
        assert _format_age(three_hours_ago) == "3h ago"

    def test_one_day_ago(self):
        one_day_ago = (datetime.now() - timedelta(days=1)).isoformat()
        assert _format_age(one_day_ago) == "1d ago"

    def test_multiple_days_ago(self):
        five_days_ago = (datetime.now() - timedelta(days=5)).isoformat()
        assert _format_age(five_days_ago) == "5d ago"


class TestRenderTaskItem:
    def test_open_task_has_unchecked_box(self):
        task = {
            "id": "TASK-001",
            "title": "Reply to Alex",
            "score": 82,
            "description": "Status update needed",
            "next_step": "Send summary",
            "sender": "Alex Morgan",
            "created": datetime.now().isoformat(),
            "teams_link": "https://teams.microsoft.com/l/message/123",
            "state": "open",
        }
        result = _render_task_item(task)
        assert "- [ ]" in result
        assert "**TASK-001 | Reply to Alex**" in result
        assert "`Score: 82`" in result
        assert "\U0001f4ac Status update needed" in result
        assert "Next: Send summary" in result
        assert "\U0001f464 Alex Morgan" in result
        assert "[Open in Teams]" in result

    def test_closed_task_has_checked_box(self):
        task = {
            "title": "Done task",
            "score": 0,
            "sender": "Someone",
            "created": datetime.now().isoformat(),
            "state": "closed",
        }
        result = _render_task_item(task)
        assert "- [x]" in result

    def test_no_teams_link_omits_link_line(self):
        task = {
            "title": "Task without link",
            "score": 10,
            "sender": "Someone",
            "created": datetime.now().isoformat(),
            "teams_link": "",
            "state": "open",
        }
        result = _render_task_item(task)
        assert "[Open in Teams]" not in result

    def test_search_fallback_rendered(self):
        task = {
            "title": "Complete Compass Connect content items",
            "score": 24,
            "sender": "Sri Varsha Nadella",
            "created": datetime.now().isoformat(),
            "teams_link": "https://teams.microsoft.com/l/message/19:abc@thread.v2/123",
            "state": "open",
        }
        result = _render_task_item(task)
        assert "Search" in result
        assert "Sri Varsha Nadella" in result

    def test_indent_adds_prefix(self):
        task = {
            "title": "Child task",
            "score": 10,
            "sender": "Someone",
            "created": datetime.now().isoformat(),
            "state": "open",
        }
        result = _render_task_item(task, indent=2)
        # indent=2 means 4 spaces prefix
        assert result.startswith("    - [ ]")

    def test_email_source_renders_outlook_link(self):
        task = {
            "title": "Review budget proposal",
            "score": 42,
            "sender": "Alex Morgan",
            "created": datetime.now().isoformat(),
            "state": "open",
            "source": "email",
            "source_link": "https://outlook.office.com/mail/deeplink/compose/AAMkAGI2",
            "source_metadata": {},
            "teams_link": "",
        }
        result = _render_task_item(task)
        assert "[Open in Outlook]" in result
        assert "outlook.office.com" in result
        assert "[Open in Teams]" not in result

    def test_calendar_source_renders_meeting_link(self):
        task = {
            "title": "Prepare demo script",
            "score": 46,
            "sender": "Pat Rivera",
            "created": datetime.now().isoformat(),
            "state": "open",
            "source": "calendar",
            "source_link": "https://teams.microsoft.com/l/meetup-join/19:meeting_abc",
            "source_metadata": {},
            "teams_link": "",
        }
        result = _render_task_item(task)
        assert "[Open Meeting]" in result
        assert "[Open in Teams]" not in result

    def test_legacy_task_without_source_renders_teams_link(self):
        task = {
            "title": "Reply to Alex",
            "score": 82,
            "sender": "Alex Morgan",
            "created": datetime.now().isoformat(),
            "teams_link": "https://teams.microsoft.com/l/message/123",
            "state": "open",
        }
        result = _render_task_item(task)
        assert "[Open in Teams]" in result

    def test_alternate_links_rendered(self):
        task = {
            "title": "API schema mapping",
            "score": 30,
            "sender": "Jordan Kim",
            "created": datetime.now().isoformat(),
            "state": "open",
            "source": "teams",
            "source_link": "",
            "source_metadata": {
                "alternate_links": [
                    {"source": "email", "link": "https://outlook.office.com/mail/456"},
                    {"source": "calendar", "link": "https://teams.microsoft.com/l/meetup-join/789"},
                ]
            },
            "teams_link": "https://teams.microsoft.com/l/message/123",
        }
        result = _render_task_item(task)
        assert "[Open in Teams]" in result
        assert "[Open in Outlook]" in result
        assert "[Open Meeting]" in result

    def test_subtasks_rendered_nested(self):
        child = {
            "id": "TASK-002",
            "title": "Polish demo videos",
            "score": 14,
            "sender": "Sri Varsha Nadella",
            "created": datetime.now().isoformat(),
            "next_step": "Review and polish the recordings",
            "state": "open",
            "subtask_ids": [],
        }
        parent = {
            "id": "TASK-001",
            "title": "Complete Compass Connect content items",
            "score": 29,
            "description": "Sri Varsha asked for help with content",
            "sender": "Sri Varsha Nadella",
            "created": datetime.now().isoformat(),
            "teams_link": "",
            "state": "open",
            "subtask_ids": ["TASK-002"],
        }
        all_tasks = {"TASK-001": parent, "TASK-002": child}
        result = _render_task_item(parent, all_tasks=all_tasks)
        assert "Subtasks:" in result
        assert "Polish demo videos" in result


class TestRenderDashboard:
    def test_contains_all_sections(self):
        tasks = _load_fixture_tasks()
        config = _make_config()
        md = render_dashboard(tasks, config)
        assert "# TaskNemo" in md
        assert "[!warning] Focus Now" in md
        assert "[!todo] Open" in md
        assert "[!example] Waiting" in md
        assert "[!question] Needs Follow-up" in md
        assert "[!info] Waiting on Others" in md
        assert "[!success] Recently Closed" in md

    def test_last_updated_present(self):
        md = render_dashboard([], _make_config())
        assert "Last synced" in md

    def test_run_stats_displayed(self):
        md = render_dashboard([], _make_config(), run_stats={"new_tasks": 3, "transitions": 2})
        assert "+3 new" in md
        assert "2 transitions" in md

    def test_empty_tasks_shows_placeholders(self):
        md = render_dashboard([], _make_config())
        assert "*No high-priority tasks right now.*" in md
        assert "*No other open tasks.*" in md
        assert "*Nothing waiting on others.*" in md
        assert "*No pending requests to others.*" in md

    def test_outbound_task_in_waiting_on_others_section(self):
        outbound_task = {
            "id": "TASK-OUT-1",
            "title": "Waiting for Casey to call back",
            "score": 10,
            "sender": "Casey Ng",
            "created": datetime.now().isoformat(),
            "state": "open",
            "direction": "outbound",
            "source": "teams",
            "teams_link": "https://teams.microsoft.com/l/message/123",
            "subtask_ids": [],
        }
        config = _make_config()
        md = render_dashboard([outbound_task], config)
        # Should be in Waiting on Others, NOT in Open
        assert "[!info] Waiting on Others" in md
        # The task should appear after the Waiting on Others heading
        woo_idx = md.index("[!info] Waiting on Others")
        open_idx = md.index("[!todo] Open")
        assert "Waiting for Casey to call back" in md[woo_idx:]
        # Should NOT appear in Open section
        assert "Waiting for Casey to call back" not in md[open_idx:woo_idx]

    def test_focus_section_has_high_score_tasks(self):
        tasks = _load_fixture_tasks()
        config = _make_config()
        md = render_dashboard(tasks, config)
        # TASK-001 has score 82 and is open → should be in Focus Now
        assert "Reply to Alex: status update on product roadmap" in md

    def test_waiting_section_has_waiting_tasks(self):
        tasks = _load_fixture_tasks()
        config = _make_config()
        md = render_dashboard(tasks, config)
        # TASK-003 is in waiting state
        assert "Review COGS analysis from Taylor" in md


class TestWriteDashboard:
    def test_writes_file(self):
        vault = tempfile.mkdtemp()
        md = "# Test Dashboard\n\nHello world."
        path = write_dashboard(md, vault, "Test.md")
        assert os.path.exists(path)
        with open(path, "r") as f:
            assert f.read() == md

    def test_creates_vault_dir_if_missing(self):
        vault = os.path.join(tempfile.mkdtemp(), "new_vault")
        write_dashboard("# Test", vault)
        assert os.path.isdir(vault)


class TestSyncDashboardCompletions:
    def test_checked_task_gets_closed(self, tmp_path, monkeypatch):
        """Simulate user checking [x] in Obsidian -> task should close."""
        vault = str(tmp_path)
        # Write a dashboard with one checked task (inside callout)
        md = '> - [x] **TASK-042 | Do the thing** `Score: 50`\n'
        with open(os.path.join(vault, "TaskNemo.md"), "w") as f:
            f.write(md)
        # Create a matching task store
        store = {"tasks": [{
            "id": "TASK-042", "title": "Do the thing", "state": "open",
            "state_history": [{"state": "open", "reason": "test", "date": "2026-03-01"}],
        }]}
        # Monkeypatch load/save to use in-memory store
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        saved = []
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: saved.append(s))

        closed = sync_dashboard_completions(vault)
        assert closed == ["TASK-042"]
        assert store["tasks"][0]["state"] == "closed"
        assert len(saved) == 1

    def test_already_closed_task_not_re_closed(self, tmp_path, monkeypatch):
        vault = str(tmp_path)
        md = '> - [x] ~~TASK-042 | Done thing~~ \u00b7 closed just now\n'
        with open(os.path.join(vault, "TaskNemo.md"), "w", encoding="utf-8") as f:
            f.write(md)
        store = {"tasks": [{
            "id": "TASK-042", "title": "Done thing", "state": "closed",
            "state_history": [],
        }]}
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: None)

        closed = sync_dashboard_completions(vault)
        assert closed == []

    def test_unchecked_task_not_closed(self, tmp_path, monkeypatch):
        vault = str(tmp_path)
        md = '> - [ ] **TASK-042 | Open thing** `Score: 50`\n'
        with open(os.path.join(vault, "TaskNemo.md"), "w") as f:
            f.write(md)
        store = {"tasks": [{
            "id": "TASK-042", "title": "Open thing", "state": "open",
            "state_history": [],
        }]}
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: None)

        closed = sync_dashboard_completions(vault)
        assert closed == []

    def test_no_dashboard_file_returns_empty(self):
        closed = sync_dashboard_completions("/nonexistent/path")
        assert closed == []

    def test_task_id_embedded_in_render(self):
        task = {
            "id": "TASK-099",
            "title": "Test task",
            "score": 10,
            "sender": "Someone",
            "created": datetime.now().isoformat(),
            "state": "open",
        }
        result = _render_task_item(task)
        assert "TASK-099 |" in result


class TestCheckedTaskRegex:
    def test_regex_matches_v2_plain_format(self):
        """v2 renders plain: - [x] TASK-114 | Title"""
        m = _CHECKED_TASK_RE.search("- [x] TASK-114 | Do something")
        assert m is not None
        assert m.group(1) == "TASK-114"

    def test_regex_matches_v1_bold_format(self):
        """v1 renders bold: - [x] **TASK-042 | Title**"""
        m = _CHECKED_TASK_RE.search("- [x] **TASK-042 | Do the thing**")
        assert m is not None
        assert m.group(1) == "TASK-042"

    def test_regex_matches_closed_strikethrough(self):
        """Closed tasks render with strikethrough: - [x] ~~TASK-099 | ...~~"""
        m = _CHECKED_TASK_RE.search("- [x] ~~TASK-099 | Done thing~~")
        assert m is not None
        assert m.group(1) == "TASK-099"

    def test_regex_does_not_match_unchecked(self):
        """Unchecked boxes should NOT match."""
        m = _CHECKED_TASK_RE.search("- [ ] TASK-114 | Open thing")
        assert m is None


class TestV2CheckboxCompletion:
    def test_v2_checked_task_gets_closed(self, tmp_path, monkeypatch):
        """v2 plain format checkbox -> task closes."""
        vault = str(tmp_path)
        md = '> - [x] TASK-114 | Ship feature `Score: 80`\n'
        with open(os.path.join(vault, "TaskNemo.md"), "w") as f:
            f.write(md)
        store = {"tasks": [{
            "id": "TASK-114", "title": "Ship feature", "state": "open",
            "state_history": [{"state": "open", "reason": "test", "date": "2026-03-01"}],
        }]}
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        saved = []
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: saved.append(s))

        closed = sync_dashboard_completions(vault)
        assert closed == ["TASK-114"]
        assert store["tasks"][0]["state"] == "closed"
        assert len(saved) == 1

    def test_v1_checked_task_still_works(self, tmp_path, monkeypatch):
        """v1 bold format still works after regex change."""
        vault = str(tmp_path)
        md = '> - [x] **TASK-042 | Do the thing** `Score: 50`\n'
        with open(os.path.join(vault, "TaskNemo.md"), "w") as f:
            f.write(md)
        store = {"tasks": [{
            "id": "TASK-042", "title": "Do the thing", "state": "open",
            "state_history": [{"state": "open", "reason": "test", "date": "2026-03-01"}],
        }]}
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        saved = []
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: saved.append(s))

        closed = sync_dashboard_completions(vault)
        assert closed == ["TASK-042"]
        assert store["tasks"][0]["state"] == "closed"
        assert len(saved) == 1


class TestCmdAdd:
    def _make_env(self, monkeypatch):
        store = {"tasks": []}
        config = {"next_task_id": 1}
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: None)
        monkeypatch.setattr("task_dashboard.load_config", lambda: config)
        monkeypatch.setattr("task_dashboard.save_config", lambda c: None)
        return store, config

    def test_cmd_add_creates_task(self, monkeypatch):
        store, config = self._make_env(monkeypatch)
        task_id = cmd_add("Review proposal")
        assert task_id == "TASK-001"
        assert len(store["tasks"]) == 1
        assert store["tasks"][0]["title"] == "Review proposal"
        assert store["tasks"][0]["source"] == "manual"

    def test_cmd_add_with_sender(self, monkeypatch):
        store, config = self._make_env(monkeypatch)
        cmd_add("Fix bug", sender="Alice")
        assert store["tasks"][0]["sender"] == "Alice"

    def test_cmd_add_with_due_hint(self, monkeypatch):
        store, config = self._make_env(monkeypatch)
        cmd_add("Ship feature", due_hint="next Friday")
        assert store["tasks"][0]["due_hint"] == "next Friday"

    def test_cmd_add_returns_task_id(self, monkeypatch):
        store, config = self._make_env(monkeypatch)
        tid = cmd_add("Something")
        assert tid.startswith("TASK-")


class TestSyncInbox:
    def _make_env(self, monkeypatch):
        store = {"tasks": []}
        config = {"next_task_id": 1}
        monkeypatch.setattr("task_dashboard.load_tasks", lambda: store)
        monkeypatch.setattr("task_dashboard.save_tasks", lambda s: None)
        monkeypatch.setattr("task_dashboard.load_config", lambda: config)
        monkeypatch.setattr("task_dashboard.save_config", lambda c: None)
        return store, config

    def test_inbox_imports_plain_lines(self, tmp_path, monkeypatch):
        store, config = self._make_env(monkeypatch)
        inbox = tmp_path / "Task Inbox.md"
        inbox.write_text("# Task Inbox\n\n- Review proposal\n- Ship feature\n")
        ids = sync_inbox(str(tmp_path))
        assert len(ids) == 2
        assert store["tasks"][0]["title"] == "Review proposal"
        assert store["tasks"][1]["title"] == "Ship feature"

    def test_inbox_imports_checkbox_lines(self, tmp_path, monkeypatch):
        store, config = self._make_env(monkeypatch)
        inbox = tmp_path / "Task Inbox.md"
        inbox.write_text("# Task Inbox\n\n- [ ] Check email\n")
        ids = sync_inbox(str(tmp_path))
        assert len(ids) == 1
        assert store["tasks"][0]["title"] == "Check email"

    def test_inbox_skips_headers_and_blanks(self, tmp_path, monkeypatch):
        store, config = self._make_env(monkeypatch)
        inbox = tmp_path / "Task Inbox.md"
        inbox.write_text("# Task Inbox\nAdd tasks below.\n\n# Section\n\n- Real task\n")
        ids = sync_inbox(str(tmp_path))
        assert len(ids) == 1
        assert store["tasks"][0]["title"] == "Real task"

    def test_inbox_clears_after_import(self, tmp_path, monkeypatch):
        store, config = self._make_env(monkeypatch)
        inbox = tmp_path / "Task Inbox.md"
        inbox.write_text("# Task Inbox\nAdd tasks below.\n\n- Task one\n- Task two\n")
        sync_inbox(str(tmp_path))
        content = inbox.read_text()
        assert "- Task one" not in content
        assert "# Task Inbox" in content

    def test_inbox_no_file_returns_empty(self, tmp_path, monkeypatch):
        store, config = self._make_env(monkeypatch)
        ids = sync_inbox(str(tmp_path))
        assert ids == []

    def test_inbox_parses_inline_sender(self, tmp_path, monkeypatch):
        store, config = self._make_env(monkeypatch)
        inbox = tmp_path / "Task Inbox.md"
        inbox.write_text("# Task Inbox\n\n- Follow up on AI roadmap --sender Juhee --due Friday\n")
        ids = sync_inbox(str(tmp_path))
        assert len(ids) == 1
        assert store["tasks"][0]["sender"] == "Juhee"
        assert store["tasks"][0]["due_hint"] == "Friday"
        assert "--sender" not in store["tasks"][0]["title"]


class TestCmdInit:
    def _patch_paths(self, monkeypatch, tmp_path):
        import task_dashboard as td
        data_dir = str(tmp_path / "data")
        monkeypatch.setattr(td, "DATA_DIR", data_dir)
        monkeypatch.setattr(td, "CONFIG_PATH", os.path.join(data_dir, "config.json"))
        monkeypatch.setattr(td, "TASKS_PATH", os.path.join(data_dir, "tasks.json"))
        monkeypatch.setattr(td, "RUN_LOG_PATH", os.path.join(data_dir, "run_log.json"))
        return data_dir

    def test_init_creates_all_data_files(self, tmp_path, monkeypatch):
        data_dir = self._patch_paths(monkeypatch, tmp_path)
        cmd_init(vault_path=str(tmp_path / "vault"))
        for name in ["config.json", "tasks.json", "run_log.json"]:
            path = os.path.join(data_dir, name)
            assert os.path.exists(path), f"{name} not created"
            with open(path) as f:
                json.load(f)  # valid JSON

    def test_init_config_has_expected_keys(self, tmp_path, monkeypatch):
        self._patch_paths(monkeypatch, tmp_path)
        cmd_init(vault_path=str(tmp_path / "vault"))
        import task_dashboard as td
        config = json.load(open(td.CONFIG_PATH))
        for key in ["vault_path", "stakeholders", "sources_enabled", "next_task_id"]:
            assert key in config, f"Missing key: {key}"

    def test_init_tasks_empty(self, tmp_path, monkeypatch):
        self._patch_paths(monkeypatch, tmp_path)
        cmd_init(vault_path=str(tmp_path / "vault"))
        import task_dashboard as td
        tasks = json.load(open(td.TASKS_PATH))
        assert tasks == {"tasks": []}

    def test_init_refuses_overwrite_without_force(self, tmp_path, monkeypatch, capsys):
        self._patch_paths(monkeypatch, tmp_path)
        cmd_init(vault_path=str(tmp_path / "vault"))
        cmd_init(vault_path=str(tmp_path / "vault2"))
        out = capsys.readouterr().out
        assert "already exists" in out

    def test_init_force_overwrites(self, tmp_path, monkeypatch):
        data_dir = self._patch_paths(monkeypatch, tmp_path)
        cmd_init(vault_path=str(tmp_path / "vault"))
        import task_dashboard as td
        config = json.load(open(td.CONFIG_PATH))
        config["custom_key"] = "test"
        with open(td.CONFIG_PATH, "w") as f:
            json.dump(config, f)
        cmd_init(force=True, vault_path=str(tmp_path / "vault2"))
        config = json.load(open(td.CONFIG_PATH))
        assert "custom_key" not in config
        assert config["vault_path"] == str(tmp_path / "vault2")


class TestDeepMergeDefaults:
    def test_adds_missing_keys(self):
        current = {"a": 1}
        added = _deep_merge_defaults({"a": 99, "b": 2}, current)
        assert current == {"a": 1, "b": 2}
        assert added == ["b"]

    def test_preserves_existing_values(self):
        current = {"x": "mine", "y": "also mine"}
        _deep_merge_defaults({"x": "template", "y": "template"}, current)
        assert current == {"x": "mine", "y": "also mine"}

    def test_nested_dict_merge(self):
        current = {"scoring": {"calendar_boost": 10}}
        added = _deep_merge_defaults({"scoring": {"calendar_boost": 5, "new_factor": 3}}, current)
        assert current["scoring"]["calendar_boost"] == 10
        assert current["scoring"]["new_factor"] == 3
        assert "scoring.new_factor" in added

    def test_empty_current(self):
        current = {}
        _deep_merge_defaults({"a": 1, "b": {"c": 2}}, current)
        assert current == {"a": 1, "b": {"c": 2}}

    def test_empty_template(self):
        current = {"a": 1}
        added = _deep_merge_defaults({}, current)
        assert added == []
        assert current == {"a": 1}


class TestCmdUpgrade:
    def _setup(self, monkeypatch, tmp_path):
        import task_dashboard as td
        data_dir = str(tmp_path / "data")
        os.makedirs(data_dir, exist_ok=True)
        monkeypatch.setattr(td, "DATA_DIR", data_dir)
        monkeypatch.setattr(td, "CONFIG_PATH", os.path.join(data_dir, "config.json"))
        monkeypatch.setattr(td, "TASKS_PATH", os.path.join(data_dir, "tasks.json"))
        monkeypatch.setattr(td, "RUN_LOG_PATH", os.path.join(data_dir, "run_log.json"))
        monkeypatch.setattr(td, "ANALYTICS_PATH", os.path.join(data_dir, "analytics.json"))
        return data_dir, td

    def test_upgrade_adds_new_template_keys(self, tmp_path, monkeypatch, capsys):
        data_dir, td = self._setup(monkeypatch, tmp_path)
        # Create a minimal config (missing some template keys)
        config = {"vault_path": "/my/vault", "stakeholders": {"alice": {"weight": 5}}, "next_task_id": 5}
        with open(td.CONFIG_PATH, "w") as f:
            json.dump(config, f)
        with open(td.TASKS_PATH, "w") as f:
            json.dump({"tasks": []}, f)
        with open(td.RUN_LOG_PATH, "w") as f:
            json.dump({"runs": []}, f)
        # Create a template with extra keys
        template = dict(config)
        template["new_feature_flag"] = True
        template["overlap_days"] = 2
        with open(os.path.join(data_dir, "config.template.json"), "w") as f:
            json.dump(template, f)
        cmd_upgrade()
        updated = json.load(open(td.CONFIG_PATH))
        # New key added
        assert updated["new_feature_flag"] is True
        # Existing values preserved
        assert updated["vault_path"] == "/my/vault"
        assert updated["stakeholders"] == {"alice": {"weight": 5}}
        assert updated["next_task_id"] == 5

    def test_upgrade_preserves_user_stakeholders(self, tmp_path, monkeypatch, capsys):
        data_dir, td = self._setup(monkeypatch, tmp_path)
        config = {"vault_path": "/v", "stakeholders": {"bob": {"weight": 7}}, "next_task_id": 10, "last_run": "2026-01-01"}
        with open(td.CONFIG_PATH, "w") as f:
            json.dump(config, f)
        with open(td.TASKS_PATH, "w") as f:
            json.dump({"tasks": []}, f)
        with open(td.RUN_LOG_PATH, "w") as f:
            json.dump({"runs": []}, f)
        # Template has empty stakeholders
        template = {"vault_path": "", "stakeholders": {}, "next_task_id": 1, "last_run": None}
        with open(os.path.join(data_dir, "config.template.json"), "w") as f:
            json.dump(template, f)
        cmd_upgrade()
        updated = json.load(open(td.CONFIG_PATH))
        assert updated["stakeholders"] == {"bob": {"weight": 7}}
        assert updated["next_task_id"] == 10
        assert updated["last_run"] == "2026-01-01"

    def test_upgrade_no_config_prints_error(self, tmp_path, monkeypatch, capsys):
        data_dir, td = self._setup(monkeypatch, tmp_path)
        cmd_upgrade()
        out = capsys.readouterr().out
        assert "init" in out.lower()
