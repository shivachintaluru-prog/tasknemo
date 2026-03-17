"""Agent runner — execute agent and log results."""

from datetime import datetime

from .base import AgentBase, AgentResult
from ..pipeline import log_run


def run_agent(agent: AgentBase, context: dict | None = None) -> AgentResult:
    """Execute an agent, log the run, and return the result."""
    context = context or {}
    started = datetime.now()

    try:
        result = agent.run(context)
    except Exception as e:
        result = AgentResult(
            agent_id=agent.agent_id,
            started=started,
            finished=datetime.now(),
            success=False,
            errors=[str(e)],
        )

    # Log agent run to run_log.json
    log_run({
        "agent_id": agent.agent_id,
        "success": result.success,
        "duration_s": (result.finished - result.started).total_seconds(),
        "stats": result.stats,
        "errors": result.errors,
    })

    return result
