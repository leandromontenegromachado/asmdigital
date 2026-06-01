"""Read-only Redmine project advisor agent."""

__version__ = "0.1.0"

from .integration import avaliar_projeto_redmine, tool_definition

__all__ = ["avaliar_projeto_redmine", "tool_definition"]
