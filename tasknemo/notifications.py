"""Notifications — desktop toasts and change summaries."""


def _notify(title, message):
    """Show a desktop toast notification. Silently no-ops on failure."""
    try:
        from win11toast import notify
        notify(title, message)
    except Exception:
        pass


def _build_change_summary(new_count=0, closed_count=0, transition_count=0):
    """Return a human-readable change summary string, or None if nothing changed."""
    if new_count == 0 and closed_count == 0 and transition_count == 0:
        return None
    parts = []
    if new_count:
        parts.append(f"+{new_count} new {'task' if new_count == 1 else 'tasks'}")
    if closed_count:
        parts.append(f"{closed_count} closed")
    if transition_count:
        s = "" if transition_count == 1 else "s"
        parts.append(f"{transition_count} transition{s}")
    return ", ".join(parts)
