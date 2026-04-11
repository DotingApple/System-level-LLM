from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
import logging
import os

import litellm

from soc_opt_agent.llm.prompts import load_prompt
from soc_opt_agent.llm.schemas import parse_llm_proposal
from soc_opt_agent.models import LLMProposal


def configure_litellm_runtime() -> None:
    litellm.suppress_debug_info = True
    litellm.set_verbose = False
    if not os.environ.get("LITELLM_LOG"):
        os.environ["LITELLM_LOG"] = "ERROR"
    try:
        from litellm._logging import verbose_logger

        verbose_logger.setLevel(logging.CRITICAL)
        verbose_logger.propagate = False
    except Exception:
        pass


configure_litellm_runtime()


@dataclass(slots=True)
class LLMClient:
    system_prompt_name: str = "system.txt"
    suggest_config_prompt_name: str = "suggest_config.txt"
    reflect_on_result_prompt_name: str = "reflect_on_result.txt"
    api_key_env: str = "GEMINI_API_KEY"
    api_base: str = "https://generativelanguage.googleapis.com/v1beta"
    timeout_seconds: int = 60

    def system_prompt(self) -> str:
        return load_prompt(self.system_prompt_name)

    def suggest_config_prompt(self) -> str:
        return load_prompt(self.suggest_config_prompt_name)

    def reflect_on_result_prompt(self) -> str:
        return load_prompt(self.reflect_on_result_prompt_name)

    def parse_proposal(self, raw: Mapping[str, object]) -> LLMProposal:
        return parse_llm_proposal(raw)

    def get_api_key(self) -> str:
        api_key = os.environ.get(self.api_key_env, "").strip()
        if not api_key:
            raise ValueError(f"Missing API key in environment variable {self.api_key_env}")
        return api_key

    def _normalize_model_name(self, model: str) -> str:
        if "/" in model:
            return model
        return f"gemini/{model}"

    def _build_response_schema(self) -> dict[str, object]:
        return {
            "type": "object",
            "properties": {
                "changes": {
                    "type": "object",
                    "additionalProperties": {
                        "anyOf": [
                            {"type": "integer"},
                            {"type": "string"},
                            {
                                "type": "array",
                                "items": {"type": "integer"},
                            },
                        ]
                    },
                },
                "rationale": {"type": "string"},
                "search_intent": {"type": "string"},
            },
            "required": ["changes", "rationale", "search_intent"],
            "propertyOrdering": ["changes", "rationale", "search_intent"],
        }

    def request_proposal(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model: str,
        temperature: float = 0.2,
        response_format: str = "structured_json",
    ) -> LLMProposal:
        configure_litellm_runtime()
        self.get_api_key()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        completion_kwargs: dict[str, object] = {
            "model": self._normalize_model_name(model),
            "messages": messages,
            "temperature": temperature,
            "timeout": self.timeout_seconds,
        }
        if response_format == "structured_json":
            completion_kwargs["response_format"] = {"type": "json_object"}

        response = litellm.completion(**completion_kwargs)
        raw_text = response.choices[0].message.content
        if not isinstance(raw_text, str) or not raw_text.strip():
            raise ValueError("Unable to extract text output from LiteLLM response")
        parsed = json.loads(raw_text)
        if not isinstance(parsed, Mapping):
            raise ValueError("LLM proposal response must be a JSON object")
        return self.parse_proposal(parsed)

__all__ = ["LLMClient", "configure_litellm_runtime"]
