"""Dependency injection — config, store, analytics loaders for FastAPI."""

from ..store import load_config, load_tasks, load_analytics, load_run_log


def get_config():
    return load_config()


def get_tasks():
    return load_tasks()


def get_analytics():
    return load_analytics()


def get_run_log():
    return load_run_log()
