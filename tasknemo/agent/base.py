"""AgentBase ABC and AgentResult dataclass."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class AgentResult:
    """Result of an agent run."""
    agent_id: str
    started: datetime
    finished: datetime
    success: bool
    stats: dict = field(default_factory=dict)
    outputs: list = field(default_factory=list)
    errors: list = field(default_factory=list)


class AgentBase(ABC):
    """Abstract base class for TaskNemo agents."""

    agent_id: str = ""
    display_name: str = ""

    @abstractmethod
    def run(self, context: dict) -> AgentResult:
        """Execute the agent. Returns AgentResult."""
        ...

    def is_enabled(self) -> bool:
        """Check if the agent is enabled in config."""
        try:
            from ..store import load_config
            config = load_config()
            agents_cfg = config.get("agents", {})
            agent_cfg = agents_cfg.get(self.agent_id, {})
            return agent_cfg.get("enabled", True)
        except Exception:
            return True

    def get_schedule(self) -> str | None:
        """Return schedule string (e.g. 'daily 7:00') or None for manual-only."""
        return None
