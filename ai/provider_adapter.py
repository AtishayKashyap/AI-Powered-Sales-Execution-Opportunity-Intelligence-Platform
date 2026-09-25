import json
from typing import Any, Dict

import requests

from .explain import LLMProvider


class OllamaProvider(LLMProvider):
    """
    Local Ollama provider for SalesForge.

    No API key.
    No cloud call.
    Runs against Ollama on localhost.
    """

    def __init__(
        self,
        model: str = "qwen3:8b",
        base_url: str = "http://localhost:11434",
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate_json(self, prompt: Dict[str, Any]) -> Dict[str, Any]:
        schema = {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "string"
                },
                "why_it_matters": {
                    "type": "string"
                },
                "recommended_action": {
                    "type": "string"
                },
                "evidence_used": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low"]
                },
            },
            "required": [
                "summary",
                "why_it_matters",
                "recommended_action",
                "evidence_used",
                "confidence",
            ],
            "additionalProperties": False,
        }

        payload = {
            "model": self.model,

            "system": prompt["system"],

            "prompt": json.dumps(
                {
                    "opportunity": prompt["input"],
                    "output_requirements": prompt["output_requirements"],
                },
                ensure_ascii=False,
            ),

            "stream": False,

            # Qwen3 reasoning is unnecessary for these short explanations.
            "think": False,

            # Force structured JSON.
            "format": schema,

            "options": {
                "temperature": 0.2,
            },
        }

        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=120,
            )
        except requests.RequestException as exc:
            raise RuntimeError(
                "Could not connect to Ollama at "
                f"{self.base_url}. Make sure Ollama is running."
            ) from exc

        if response.status_code != 200:
            raise RuntimeError(
                f"Ollama returned HTTP {response.status_code}: "
                f"{response.text}"
            )

        data = response.json()

        output = data.get("response")

        if not output:
            raise RuntimeError(
                f"Ollama returned an empty response: {data}"
            )

        try:
            result = json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "Ollama returned invalid JSON:\n"
                f"{output}"
            ) from exc

        if not isinstance(result, dict):
            raise RuntimeError(
                "Ollama response is not a JSON object."
            )

        return result