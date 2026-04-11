from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from soc_opt_agent.discovery.accelerators import discover_accelerators
from soc_opt_agent.orchestrator.iteration import CampaignIteration, build_iteration, select_next_accelerator
from soc_opt_agent.orchestrator.state import CampaignState
from soc_opt_agent.paths import get_default_accelerators_root, get_default_soc_root
from soc_opt_agent.scoring.compare import is_plateau


def _default_configs_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "configs"


def load_yaml_file(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, Mapping):
        raise ValueError(f"Expected {path} to contain a YAML mapping")
    return dict(data)


def build_campaign_queue(search_space: dict[str, Any], accelerators_root: Path | None = None) -> list[str]:
    root = accelerators_root or Path(search_space.get("accelerators_root") or get_default_accelerators_root())
    targets = discover_accelerators(root, soc_dir=Path(search_space.get("soc_root") or get_default_soc_root()))
    preferred_order = search_space.get("accelerator_order") or []

    if preferred_order:
        ranked = [name for name in preferred_order if any(target.name == name for target in targets)]
        remainder = [target.name for target in targets if target.name not in ranked]
        return ranked + remainder

    return [target.name for target in targets]


def should_stop_for_plateau(campaign_config: Mapping[str, Any], state: CampaignState, scoring_config: Mapping[str, Any]) -> bool:
    if not campaign_config.get("stop_after_plateau", False):
        return False

    window = int(scoring_config.get("plateau_window", 0))
    min_improvement = float(scoring_config.get("minimum_improvement", 0.0))
    return is_plateau(state.recent_improvements, min_improvement=min_improvement, window=window)


def prepare_iteration(
    campaign_config_path: Path,
    search_space_config_path: Path,
    scoring_config_path: Path | None = None,
    llm_config_path: Path | None = None,
) -> CampaignIteration:
    configs_dir = _default_configs_dir()
    scoring_config_path = scoring_config_path or configs_dir / "scoring.yaml"
    llm_config_path = llm_config_path or configs_dir / "llm.yaml"

    campaign_config = load_yaml_file(campaign_config_path)
    search_space = load_yaml_file(search_space_config_path)
    scoring_config = load_yaml_file(scoring_config_path)
    llm_config = load_yaml_file(llm_config_path)

    state = CampaignState(
        completed_accelerators=list(campaign_config.get("completed_accelerators", [])),
        recent_improvements=list(campaign_config.get("recent_improvements", [])),
    )
    queue = build_campaign_queue(search_space)
    iteration = build_iteration(queue, state, scoring_config=scoring_config, llm_config=llm_config)
    if should_stop_for_plateau(campaign_config, state, scoring_config):
        iteration.accelerator_name = None
    return iteration
