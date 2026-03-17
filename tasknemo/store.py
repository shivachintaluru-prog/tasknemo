"""Store I/O — paths, config, tasks, analytics, run_log."""

import json
import os
import tempfile

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")
TASKS_PATH = os.path.join(DATA_DIR, "tasks.json")
RUN_LOG_PATH = os.path.join(DATA_DIR, "run_log.json")
ANALYTICS_PATH = os.path.join(DATA_DIR, "analytics.json")

_ANALYTICS_DEFAULT = {"response_times": {}, "escalation_history": {}, "user_pins": []}

# ---------------------------------------------------------------------------
# Generic JSON I/O
# ---------------------------------------------------------------------------


def load_json(path):
    """Read JSON, retrying once on FileNotFoundError for atomic-replace window."""
    import time
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        time.sleep(0.05)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)


def save_json(path, data):
    """Write JSON atomically — write to temp file, then rename."""
    dir_name = os.path.dirname(path)
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        # Atomic replace (Windows: os.replace is atomic on same volume)
        os.replace(tmp_path, path)
    except Exception:
        # Clean up temp file on failure
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_config():
    return load_json(CONFIG_PATH)


def save_config(config):
    save_json(CONFIG_PATH, config)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


def load_tasks():
    return load_json(TASKS_PATH)


def save_tasks(store):
    save_json(TASKS_PATH, store)


# ---------------------------------------------------------------------------
# Run Log
# ---------------------------------------------------------------------------


def load_run_log():
    return load_json(RUN_LOG_PATH)


def save_run_log(log):
    save_json(RUN_LOG_PATH, log)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


def load_analytics():
    """Load analytics.json, returning defaults only if the file doesn't exist.

    Any other error (corrupt JSON, permission denied) is raised — silently
    returning empty defaults would wipe user_pins on the next save.
    """
    try:
        return load_json(ANALYTICS_PATH)
    except FileNotFoundError:
        # File truly doesn't exist (first run) — seed it with defaults
        defaults = dict(_ANALYTICS_DEFAULT)
        save_json(ANALYTICS_PATH, defaults)
        return defaults


def save_analytics(data):
    """Persist analytics data."""
    save_json(ANALYTICS_PATH, data)
