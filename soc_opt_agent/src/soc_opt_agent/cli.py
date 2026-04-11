from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from soc_opt_agent.llm.policy import build_policy_from_config
from soc_opt_agent.orchestrator.campaign_loop import load_yaml_file
from soc_opt_agent.orchestrator.campaign_loop import prepare_iteration
from soc_opt_agent.orchestrator.campaign_runner import STATUS_PATH, request_stop, run_all
from soc_opt_agent.orchestrator.run_once import run_baseline_iteration, run_candidate_iteration


def _default_configs_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "configs"


def build_parser(prog: str = "agentsoc") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    configs_dir = _default_configs_dir()
    parser.add_argument("--campaign-config", type=Path, default=configs_dir / "campaign.yaml")
    parser.add_argument("--search-space-config", type=Path, default=configs_dir / "search_space.yaml")
    parser.add_argument("--scoring-config", type=Path, default=configs_dir / "scoring.yaml")
    parser.add_argument("--llm-config", type=Path, default=configs_dir / "llm.yaml")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["status", "baseline", "run_once", "run_all", "stop"],
        help="Simple command interface",
    )
    parser.add_argument("--baseline", action="store_true", help="Run or reuse the saved baseline for the next accelerator")
    parser.add_argument("--run-once", action="store_true", help="Run one LLM-driven candidate iteration")
    parser.add_argument("--run-all", action="store_true", help="Run the full optimization loop")
    parser.add_argument("--stop", action="store_true", help="Stop the active run-all loop immediately")
    return parser


def _format_config(config: dict[str, object]) -> str:
    if not config:
        return "none"
    return ", ".join(f"{key}={config[key]}" for key in sorted(config))


def _resolve_action(args: argparse.Namespace) -> str:
    selected_actions = {
        "baseline": args.baseline,
        "run_once": args.run_once,
        "run_all": args.run_all,
        "stop": args.stop,
    }
    explicit_flags = [name for name, enabled in selected_actions.items() if enabled]
    if args.command and explicit_flags:
        raise SystemExit("Choose either a positional command or legacy flags, not both.")
    if len(explicit_flags) > 1:
        raise SystemExit("Choose only one of --baseline, --run-once, --run-all, or --stop.")
    if args.command:
        return str(args.command)
    if explicit_flags:
        return explicit_flags[0]
    return "status"


def _print_status(iteration: Any) -> int:
    print(f"Next accelerator: {iteration.accelerator_name}")
    print(f"Completed accelerators: {', '.join(iteration.state.completed_accelerators) or 'none'}")
    print(f"Queue size: {len(iteration.queue)}")
    print(f"Scoring config: {_format_config(iteration.scoring_config)}")
    print(f"LLM config: {_format_config(iteration.llm_config)}")
    if STATUS_PATH.exists():
        print(f"Run-all status file: {STATUS_PATH}")
    return 0


def main(argv: list[str] | None = None, *, prog: str = "agentsoc") -> int:
    args = build_parser(prog=prog).parse_args(argv)
    action = _resolve_action(args)

    if action == "stop":
        if request_stop():
            print("Stop requested for active run-all loop. Sent termination to current run-all process tree.")
            return 0
        print("No active run-all loop.")
        return 1

    if action == "run_all":
        return run_all(
            campaign_config_path=args.campaign_config,
            search_space_config_path=args.search_space_config,
            scoring_config_path=args.scoring_config,
            llm_config_path=args.llm_config,
        )

    iteration = prepare_iteration(
        args.campaign_config,
        args.search_space_config,
        args.scoring_config,
        args.llm_config,
    )

    if iteration.accelerator_name is None:
        print("No accelerators remaining.")
        return 0

    if action == "baseline":
        result = run_baseline_iteration(
            accelerator_name=iteration.accelerator_name,
        )
        print(f"Ran baseline accelerator: {result.accelerator_name}")
        print(f"Run dir: {result.run_dir}")
        print(f"Passed: {result.metrics.passed}")
        print(f"Accelerator total cycles: {result.metrics.accelerator_total_cycles}")
        print(f"Off-chip memory accesses: {result.metrics.offchip_memory_accesses}")
        return 0

    if action == "run_once":
        search_space = load_yaml_file(args.search_space_config)
        result = run_candidate_iteration(
            accelerator_name=iteration.accelerator_name,
            llm_policy=build_policy_from_config(iteration.llm_config),
            llm_config=iteration.llm_config,
            search_space=search_space,
            scoring_config=iteration.scoring_config,
        )
        print(f"Ran candidate accelerator: {result.accelerator_name}")
        print(f"Run dir: {result.run_dir}")
        print(f"Passed: {result.metrics.passed}")
        print(f"Accelerator total cycles: {result.metrics.accelerator_total_cycles}")
        print(f"Off-chip memory accesses: {result.metrics.offchip_memory_accesses}")
        return 0

    return _print_status(iteration)


def main_agentrtl(argv: list[str] | None = None) -> int:
    return main(argv, prog="agentrtl")


if __name__ == "__main__":
    raise SystemExit(main())
