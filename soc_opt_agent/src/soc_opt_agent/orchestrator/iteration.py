from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from soc_opt_agent.orchestrator.state import CampaignState


def select_next_accelerator(queue: list[str], state: CampaignState) -> str | None:
    for name in queue:
        if not state.has_completed(name):
            return name
    return None


@dataclass(slots=True)
class CampaignIteration:
    accelerator_name: str | None
    queue: list[str]
    state: CampaignState
    scoring_config: dict[str, Any] = field(default_factory=dict)
    llm_config: dict[str, Any] = field(default_factory=dict)


def build_iteration(
    queue: list[str],
    state: CampaignState,
    *,
    scoring_config: Mapping[str, Any] | None = None,
    llm_config: Mapping[str, Any] | None = None,
) -> CampaignIteration:
    return CampaignIteration(
        accelerator_name=select_next_accelerator(queue, state),
        queue=list(queue),
        state=state,
        scoring_config=dict(scoring_config or {}),
        llm_config=dict(llm_config or {}),
    )
