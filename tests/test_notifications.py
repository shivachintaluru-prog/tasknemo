"""Unit tests for desktop notification helpers."""

import os
import sys
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from task_dashboard import _build_change_summary, _notify


# ── _build_change_summary ───────────────────────────────────────────────


class TestBuildChangeSummary:
    def test_no_changes_returns_none(self):
        assert _build_change_summary(0, 0, 0) is None

    def test_new_only(self):
        result = _build_change_summary(new_count=3)
        assert result == "+3 new tasks"

    def test_closed_only(self):
        result = _build_change_summary(closed_count=2)
        assert result == "2 closed"

    def test_transitions_only(self):
        result = _build_change_summary(transition_count=4)
        assert result == "4 transitions"

    def test_combined(self):
        result = _build_change_summary(new_count=2, closed_count=1, transition_count=3)
        assert "+2 new tasks" in result
        assert "1 closed" in result
        assert "3 transitions" in result

    def test_singular(self):
        result = _build_change_summary(new_count=1, transition_count=1)
        assert "+1 new task" in result
        assert "1 transition" in result
        assert "tasks" not in result
        assert "transitions" not in result


# ── _notify ─────────────────────────────────────────────────────────────


class TestNotify:
    def test_graceful_failure_when_library_missing(self):
        """_notify should silently no-op if win11toast is not installed."""
        with patch.dict("sys.modules", {"win11toast": None}):
            # Should not raise
            _notify("Test", "message")

    def test_calls_notify_when_available(self):
        mock_module = MagicMock()
        with patch.dict("sys.modules", {"win11toast": mock_module}):
            _notify("Title", "Body")
            mock_module.notify.assert_called_once_with("Title", "Body")
