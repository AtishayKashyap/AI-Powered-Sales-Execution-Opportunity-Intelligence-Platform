"""
SalesForge provider adapter template.

Set your provider credentials in environment variables and implement
generate_json() for the selected provider. Do not put API keys in source code.
"""

import json
import os

from ai.explain import LLMProvider


class ExampleProvider(LLMProvider):
    def generate_json(self, prompt):
        """
        Replace this method with your selected model SDK call.

        The model must return a JSON object with:
        summary, why_it_matters, recommended_action,
        evidence_used, confidence.
        """
        raise NotImplementedError(
            "Connect your selected structured-output LLM here."
        )


if __name__ == "__main__":
    print("SALESFORGE AI PROVIDER ADAPTER")
    print("No external model was called.")
    print("Set up your provider here, then run the explanation pipeline.")
