from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import json
from typing import Any

from soc_opt_agent.llm.client import LLMClient
from soc_opt_agent.models import IterationMetrics, LLMProposal


@dataclass(slots=True)
class LLMPolicy:
    client: LLMClient = field(default_factory=LLMClient)

    def build_system_prompt(self) -> str:
        return self.client.system_prompt()

    def build_suggest_config_prompt(self) -> str:
        return self.client.suggest_config_prompt()

    def build_reflect_on_result_prompt(self, metrics: IterationMetrics) -> str:
        base_prompt = self.client.reflect_on_result_prompt()
        metric_lines = "\n".join(
            ["Metrics:", *[f"{key}: {value}" for key, value in metrics.model_dump(mode="json", exclude_none=True).items()]]
        )
        return f"{base_prompt}\n\n{metric_lines}"

    def validate_proposal(self, raw: Mapping[str, object]) -> LLMProposal:
        return self.client.parse_proposal(raw)

    def request_proposal(
        self,
        *,
        model: str,
        context: Mapping[str, object],
        temperature: float = 0.2,
        response_format: str = "structured_json",
    ) -> LLMProposal:
        system_prompt = self.build_system_prompt()
        user_prompt = "\n\n".join(
            [
                self.build_suggest_config_prompt(),
                "Context JSON:",
                json.dumps(context, indent=2, sort_keys=True),
            ]
        )
        return self.client.request_proposal(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature,
            response_format=response_format,
        )


def build_policy_from_config(llm_config: Mapping[str, Any]) -> LLMPolicy:
    return LLMPolicy(
        client=LLMClient(
            api_key_env=str(llm_config.get("api_key_env", "GEMINI_API_KEY")),
            api_base=str(llm_config.get("api_base", "https://generativelanguage.googleapis.com/v1beta")),
            timeout_seconds=int(llm_config.get("timeout_seconds", 60)),
        )
    )


DEFAULT_POLICY = LLMPolicy()


def build_system_prompt() -> str:
    return DEFAULT_POLICY.build_system_prompt()


def build_suggest_config_prompt() -> str:
    return DEFAULT_POLICY.build_suggest_config_prompt()


def build_reflect_on_result_prompt(metrics: IterationMetrics) -> str:
    return DEFAULT_POLICY.build_reflect_on_result_prompt(metrics)


def validate_proposal(raw: Mapping[str, object]) -> LLMProposal:
    return DEFAULT_POLICY.validate_proposal(raw)


__all__ = [
    "DEFAULT_POLICY",
    "LLMPolicy",
    "build_policy_from_config",
    "build_reflect_on_result_prompt",
    "build_suggest_config_prompt",
    "build_system_prompt",
    "validate_proposal",
]
