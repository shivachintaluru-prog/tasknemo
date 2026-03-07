"""Unit tests for sync log rendering and writing."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import render_sync_log, write_sync_log


def _make_entry(ts="2026-03-05T09:00:00", new=1, trans=0, merged=0, skipped=0, **extra):
    entry = {
        "timestamp": ts,
        "new_tasks": new,
        "transitions": trans,
        "merged": merged,
        "skipped": skipped,
    }
    entry.update(extra)
    return entry


# ── render_sync_log ─────────────────────────────────────────────────────


class TestRenderSyncLog:
    def test_header_present(self):
        md = render_sync_log([_make_entry()])
        assert "# Sync Log" in md

    def test_empty_entries(self):
        md = render_sync_log([])
        assert "*No syncs recorded yet.*" in md

    def test_max_entries_cap(self):
        entries = [_make_entry(ts=f"2026-03-05T{i:02d}:00:00") for i in range(25)]
        md = render_sync_log(entries, max_entries=5)
        # Should only render 5 entries (the 5 newest)
        assert md.count("[!note] Refresh") == 5

    def test_newest_first(self):
        entries = [
            _make_entry(ts="2026-03-05T08:00:00"),
            _make_entry(ts="2026-03-05T09:00:00"),
        ]
        md = render_sync_log(entries)
        pos_09 = md.index("09:00")
        pos_08 = md.index("08:00")
        assert pos_09 < pos_08, "Newest entry should appear first"

    def test_full_sync_callout(self):
        entry = _make_entry(sources_queried=["teams", "email"])
        md = render_sync_log([entry])
        assert "[!tip] Full Sync" in md

    def test_refresh_callout(self):
        entry = _make_entry()
        md = render_sync_log([entry])
        assert "[!note] Refresh" in md

    def test_obsidian_closed_shown(self):
        entry = _make_entry(obsidian_closed=["TASK-013", "TASK-015"])
        md = render_sync_log([entry])
        assert "Closed from Obsidian: TASK-013, TASK-015" in md

    def test_sources_shown(self):
        entry = _make_entry(sources_queried=["teams", "email", "calendar"])
        md = render_sync_log([entry])
        assert "Sources: teams, email, calendar" in md

    def test_stats_displayed(self):
        entry = _make_entry(new=3, trans=1, merged=2, skipped=4)
        md = render_sync_log([entry])
        assert "+3 new" in md
        assert "1 transitions" in md
        assert "2 merged" in md
        assert "4 skipped" in md


# ── write_sync_log ──────────────────────────────────────────────────────


class TestWriteSyncLog:
    def test_writes_file(self, tmp_path):
        md = "# Sync Log\n\ntest"
        path = write_sync_log(md, str(tmp_path))
        assert os.path.exists(path)
        with open(path) as f:
            assert f.read() == md

    def test_creates_dir(self, tmp_path):
        nested = str(tmp_path / "sub" / "dir")
        path = write_sync_log("# Sync Log", nested)
        assert os.path.exists(path)
