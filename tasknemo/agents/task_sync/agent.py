"""TaskSyncAgent — wraps existing pipeline as an agent."""

from datetime import datetime

from ...agent.base import AgentBase, AgentResult


class TaskSyncAgent(AgentBase):
    agent_id = "task_sync"
    display_name = "Task Sync (Refresh)"

    def get_schedule(self):
        return "every 30m"

    def run(self, context):
        started = datetime.now()
        errors = []
        stats = {}

        try:
            from ...cli import cmd_refresh
            from ...store import load_tasks

            # Capture pre-state
            pre_tasks = load_tasks()
            pre_count = len(pre_tasks.get("tasks", []))

            # Run refresh (the lightweight no-WorkIQ sync)
            cmd_refresh()

            # Capture post-state
            post_tasks = load_tasks()
            post_count = len(post_tasks.get("tasks", []))

            stats = {
                "tasks_before": pre_count,
                "tasks_after": post_count,
                "net_change": post_count - pre_count,
            }

        except Exception as e:
            errors.append(str(e))

        return AgentResult(
            agent_id=self.agent_id,
            started=started,
            finished=datetime.now(),
            success=len(errors) == 0,
            stats=stats,
            errors=errors,
        )
