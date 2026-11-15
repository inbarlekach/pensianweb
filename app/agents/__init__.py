import os

from .base import FeeAnalystAgent


def get_agent() -> FeeAnalystAgent:
    """Select the provider via PENSION_AI_PROVIDER. Only the template stand-in exists
    today; asking for anything else fails loudly instead of faking an AI result."""
    provider = os.environ.get("PENSION_AI_PROVIDER", "template")
    if provider == "template":
        from .mock_provider import TemplateAgent
        return TemplateAgent()
    raise RuntimeError(f"ספק AI '{provider}' עדיין לא מומש")
