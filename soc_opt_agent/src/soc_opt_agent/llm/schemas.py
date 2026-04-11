from __future__ import annotations

from collections.abc import Mapping

from soc_opt_agent.models import LLMProposal


def parse_llm_proposal(raw: Mapping[str, object]) -> LLMProposal:
    return LLMProposal.model_validate(raw)


__all__ = ["LLMProposal", "parse_llm_proposal"]
