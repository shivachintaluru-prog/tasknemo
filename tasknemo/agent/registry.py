"""Convention-based agent discovery and registry."""

from .base import AgentBase


class AgentRegistry:
    """Registry that discovers and manages agents."""

    def __init__(self):
        self._agents: dict[str, AgentBase] = {}
        self._discover()

    def _discover(self):
        """Scan agents/*/agent.py for AgentBase subclasses."""
        try:
            from ..agents.task_sync.agent import TaskSyncAgent
            agent = TaskSyncAgent()
            self._agents[agent.agent_id] = agent
        except ImportError:
            pass

        try:
            from ..agents.quality_eval.agent import QualityEvalAgent
            agent = QualityEvalAgent()
            self._agents[agent.agent_id] = agent
        except ImportError:
            pass

    def list_agents(self) -> list[AgentBase]:
        """Return all registered agents."""
        return list(self._agents.values())

    def get_agent(self, agent_id: str) -> AgentBase | None:
        """Get agent by ID."""
        return self._agents.get(agent_id)


_registry = None


def get_registry() -> AgentRegistry:
    """Get or create the singleton registry."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry
