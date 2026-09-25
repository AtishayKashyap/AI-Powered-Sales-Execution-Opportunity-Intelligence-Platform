"""
SalesForge AI adapter.

Provider-neutral interface. The project can connect OpenAI, another model
provider, or an internal endpoint without changing the SalesForge detector.

This file intentionally does not contain a hard-coded API key or provider
credential.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from .prompts import build_prompt
from .validate import validate_grounding


class LLMProvider(ABC):
    @abstractmethod
    def generate_json(self, prompt: Dict[str, Any]) -> Dict[str, Any]:
        """Return one JSON object matching the SalesForge explanation schema."""
        raise NotImplementedError


class SalesForgeExplainer:
    def __init__(self, provider: LLMProvider):
        self.provider = provider

    def explain(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        prompt = build_prompt(opportunity)
        result = self.provider.generate_json(prompt)

        evidence = opportunity.get("evidence", {})
        explanation = validate_grounding(result, evidence)

        return {
            "opportunity_id": opportunity.get("opportunity_id"),
            "outlet_id": opportunity.get("outlet_id"),
            "opportunity_type": opportunity.get("opportunity_type"),
            **explanation.to_dict(),
        }
