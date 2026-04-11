from __future__ import annotations

from pathlib import Path
import json
import os
import signal
import shutil
import subprocess
from typing import Any

import yaml

from soc_opt_agent.llm.policy import build_policy_from_config
from soc_opt_agent.orchestrator.campaign_loop import build_campaign_queue, load_yaml_file
from soc_opt_agent.orchestrator.progress import AgentTranscript
from soc_opt_agent.orchestrator.run_once import CandidateIterationError, run_baseline_iteration, run_candidate_iteration
from soc_opt_agent.orchestrator.state import CampaignState
from soc_opt_agent.paths import PROJECT_ROOT, get_default_bests_root
from soc_opt_agent.scoring.compare import improvement_ratio, is_plateau


PID_PATH = PROJECT_ROOT / "run_all.pid"
STOP_PATH = PROJECT_ROOT / "run_all.stop"
STATUS_PATH = PROJECT_ROOT / "run_all.status.json"
TRANSCRIPT_PATH = PROJECT_ROOT / "agent_transcript.log"


def _write_campaign_config(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _write_status(payload: dict[str, Any]) -> None:
    STATUS_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _best_dir(accelerator_name: str) -> Path:
    return get_default_bests_root() / accelerator_name


def _is_daily_llm_quota_error(message: str | None) -> bool:
    if not message:
        return False
    lowered = message.lower()
    return (
        "resource_exhausted" in lowered
        and "quota exceeded" in lowered
        and (
            "generaterequestsperdayperprojectpermodel-freetier" in lowered
            or "generate_content_free_tier_requests" in lowered and "perday" in lowered
            or "quota exceeded for metric" in lowered and "perday" in lowered
        )
    )


def _metrics_payload(metrics: Any) -> dict[str, Any]:
    if hasattr(metrics, "model_dump"):
        return metrics.model_dump(mode="json", exclude_none=True)
    if hasattr(metrics, "__dict__"):
        return {key: value for key, value in vars(metrics).items() if not key.startswith("_") and value is not None}
    raise TypeError(f"Unable to serialize metrics object of type {type(metrics)!r}")


def _resource_score(metrics: Any) -> float | None:
    return getattr(metrics, "resource_score", None)


def _resource_improvement(reference: Any, current: Any) -> float | None:
    reference_score = _resource_score(reference)
    current_score = _resource_score(current)
    if reference_score is None or current_score is None or reference_score <= 0:
        return None
    return (reference_score - current_score) / reference_score


def _copy_run_snapshot(source_run_dir: Path, target_dir: Path) -> None:
    target_dir.mkdir(parents=True, exist_ok=False)
    for source in source_run_dir.iterdir():
        if source.is_file():
            shutil.copy2(source, target_dir / source.name)


def _snapshot_best(accelerator_name: str, source_run_dir: Path) -> Path:
    target_dir = _best_dir(accelerator_name)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    _copy_run_snapshot(source_run_dir, target_dir)
    return target_dir


def _pareto_dir(accelerator_name: str) -> Path:
    return _best_dir(accelerator_name) / "pareto"


def _pareto_manifest_path(accelerator_name: str) -> Path:
    return _best_dir(accelerator_name) / "pareto_front.json"


def _is_pareto_eligible(metrics: Any) -> bool:
    passed = getattr(metrics, "passed", True)
    cycles = getattr(metrics, "accelerator_total_cycles", None)
    resource_score = _resource_score(metrics)
    return bool(passed) and cycles is not None and resource_score is not None


def _pareto_entry(metrics: Any, run_dir: Path) -> dict[str, Any]:
    return {
        "cycles": int(metrics.accelerator_total_cycles),
        "resource_score": float(_resource_score(metrics)),
        "run_dir": run_dir,
    }


def _dominates(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return (
        left["cycles"] <= right["cycles"]
        and left["resource_score"] <= right["resource_score"]
        and (left["cycles"] < right["cycles"] or left["resource_score"] < right["resource_score"])
    )


def _update_pareto_front(
    front: list[dict[str, Any]],
    *,
    metrics: Any,
    run_dir: Path,
) -> list[dict[str, Any]]:
    if not _is_pareto_eligible(metrics):
        return sorted(front, key=lambda entry: (entry["cycles"], entry["resource_score"]))

    candidate = _pareto_entry(metrics, run_dir)
    if any(_dominates(existing, candidate) for existing in front):
        return sorted(front, key=lambda entry: (entry["cycles"], entry["resource_score"]))

    updated = [existing for existing in front if not _dominates(candidate, existing)]
    updated.append(candidate)
    return sorted(updated, key=lambda entry: (entry["cycles"], entry["resource_score"]))


def _pareto_status_payload(front: list[dict[str, Any]], accelerator_name: str) -> list[dict[str, Any]]:
    pareto_root = _pareto_dir(accelerator_name)
    payload: list[dict[str, Any]] = []
    for entry in front:
        run_dir = Path(entry["run_dir"])
        payload.append(
            {
                "cycles": entry["cycles"],
                "resource_score": entry["resource_score"],
                "run_dir": str(run_dir),
                "snapshot_dir": str(pareto_root / run_dir.name),
            }
        )
    return payload


def _refresh_pareto_snapshots(accelerator_name: str, front: list[dict[str, Any]]) -> Path:
    pareto_root = _pareto_dir(accelerator_name)
    if pareto_root.exists():
        shutil.rmtree(pareto_root)
    pareto_root.mkdir(parents=True, exist_ok=True)
    for entry in front:
        run_dir = Path(entry["run_dir"])
        _copy_run_snapshot(run_dir, pareto_root / run_dir.name)
    _pareto_manifest_path(accelerator_name).write_text(
        json.dumps(_pareto_status_payload(front, accelerator_name), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return pareto_root


def _read_pid() -> int | None:
    if not PID_PATH.exists():
        return None
    try:
        return int(PID_PATH.read_text(encoding="utf-8").strip())
    except ValueError:
        return None


def _stop_requested() -> bool:
    return STOP_PATH.exists()


def _pid_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_process_tree() -> dict[int, list[int]]:
    completed = subprocess.run(
        ["ps", "-eo", "pid,ppid"],
        check=True,
        capture_output=True,
        text=True,
    )
    tree: dict[int, list[int]] = {}
    for line in completed.stdout.splitlines()[1:]:
        parts = line.strip().split()
        if len(parts) != 2:
            continue
        pid = int(parts[0])
        ppid = int(parts[1])
        tree.setdefault(ppid, []).append(pid)
    return tree


def _list_descendants(pid: int) -> list[int]:
    tree = _read_process_tree()
    descendants: list[int] = []
    stack = list(tree.get(pid, []))
    while stack:
        child = stack.pop()
        descendants.append(child)
        stack.extend(tree.get(child, []))
    return descendants


def _terminate_pid(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def request_stop(*, immediate: bool = True) -> bool:
    pid = _read_pid()
    if pid is None:
        return False
    if not _pid_is_running(pid):
        if PID_PATH.exists():
            PID_PATH.unlink()
        if STOP_PATH.exists():
            STOP_PATH.unlink()
        return False
    STOP_PATH.write_text("stop\n", encoding="utf-8")
    if immediate:
        for child_pid in _list_descendants(pid):
            _terminate_pid(child_pid)
        _terminate_pid(pid)
    return True


def run_all(
    *,
    campaign_config_path: Path,
    search_space_config_path: Path,
    scoring_config_path: Path,
    llm_config_path: Path,
) -> int:
    if PID_PATH.exists():
        existing_pid = _read_pid()
        if existing_pid is not None and _pid_is_running(existing_pid):
            raise RuntimeError(f"run-all already active with pid file at {PID_PATH}")
        PID_PATH.unlink()

    campaign_config = load_yaml_file(campaign_config_path)
    search_space = load_yaml_file(search_space_config_path)
    scoring_config = load_yaml_file(scoring_config_path)
    llm_config = load_yaml_file(llm_config_path)
    state = CampaignState(
        completed_accelerators=list(campaign_config.get("completed_accelerators", [])),
        recent_improvements=list(campaign_config.get("recent_improvements", [])),
    )
    queue = build_campaign_queue(search_space)
    llm_policy = build_policy_from_config(llm_config)
    transcript = AgentTranscript(paths=(TRANSCRIPT_PATH,))
    PID_PATH.write_text(f"{os.getpid()}\n", encoding="utf-8")
    if STOP_PATH.exists():
        STOP_PATH.unlink()

    stop_campaign = False
    try:
        for accelerator_name in queue:
            if state.has_completed(accelerator_name):
                continue
            if _stop_requested():
                transcript.log(f"STOP requested before accelerator {accelerator_name}")
                print(f"Stopped campaign before accelerator {accelerator_name}: stop requested.")
                break

            transcript.log(f"RUN-ALL start accelerator={accelerator_name}")
            print(f"Starting accelerator: {accelerator_name}")
            baseline = run_baseline_iteration(accelerator_name=accelerator_name)
            baseline_cycles = baseline.metrics.accelerator_total_cycles
            best_cycles = baseline_cycles
            baseline_metrics = baseline.metrics
            best_metrics = baseline.metrics
            last_metrics = baseline.metrics
            best_run_dir = _snapshot_best(accelerator_name, baseline.run_dir)
            pareto_front = _update_pareto_front([], metrics=baseline.metrics, run_dir=baseline.run_dir)
            pareto_front_dir = _refresh_pareto_snapshots(accelerator_name, pareto_front)
            recent_improvements: list[float] = []
            recent_attempts: list[dict[str, Any]] = []
            iteration_count = 0
            last_failure_reason: str | None = None
            _write_status(
                {
                    "mode": "run-all",
                    "current_accelerator": accelerator_name,
                    "phase": "baseline-ready",
                    "baseline_cycles": baseline_cycles,
                    "best_cycles": best_cycles,
                    "baseline_resource_score": _resource_score(baseline_metrics),
                    "best_resource_score": _resource_score(best_metrics),
                    "best_run_dir": str(best_run_dir),
                    "pareto_front_dir": str(pareto_front_dir),
                    "pareto_front_size": len(pareto_front),
                    "pareto_front": _pareto_status_payload(pareto_front, accelerator_name),
                    "last_failure_reason": last_failure_reason,
                    "completed_accelerators": state.completed_accelerators,
                    "recent_improvements": recent_improvements,
                }
            )

            while not is_plateau(
                recent_improvements,
                min_improvement=float(scoring_config.get("minimum_improvement", 0.0)),
                window=int(scoring_config.get("plateau_window", 0)),
            ):
                if _stop_requested():
                    transcript.log(f"STOP requested during accelerator {accelerator_name}")
                    print(f"Stopped accelerator {accelerator_name}: stop requested.")
                    break

                try:
                    candidate = run_candidate_iteration(
                        accelerator_name=accelerator_name,
                        llm_policy=llm_policy,
                        llm_config=llm_config,
                        search_space=search_space,
                        scoring_config=scoring_config,
                        baseline_metrics=baseline_metrics,
                        best_metrics=best_metrics,
                        last_metrics=last_metrics,
                        recent_attempts=recent_attempts[-5:],
                        last_failure_reason=last_failure_reason,
                    )
                except Exception as exc:
                    last_failure_reason = str(exc)
                    if _is_daily_llm_quota_error(last_failure_reason):
                        transcript.log(
                            f"RUN-ALL stop accelerator={accelerator_name} reason=daily-llm-quota-exhausted"
                        )
                        _write_status(
                            {
                                "mode": "run-all",
                                "current_accelerator": accelerator_name,
                                "phase": "stopped-rate-limit",
                                "iteration": iteration_count,
                                "baseline_cycles": baseline_cycles,
                                "best_cycles": best_cycles,
                                "baseline_resource_score": _resource_score(baseline_metrics),
                                "best_resource_score": _resource_score(best_metrics),
                                "best_run_dir": str(best_run_dir),
                                "pareto_front_dir": str(pareto_front_dir),
                                "pareto_front_size": len(pareto_front),
                                "pareto_front": _pareto_status_payload(pareto_front, accelerator_name),
                                "last_failure_reason": last_failure_reason,
                                "completed_accelerators": state.completed_accelerators,
                                "recent_improvements": recent_improvements,
                            }
                        )
                        print(
                            "Stopped accelerator "
                            f"{accelerator_name}: daily LLM quota exhausted. "
                            "Waiting for quota reset or changing model/API key is required."
                        )
                        stop_campaign = True
                        break
                    if isinstance(exc, CandidateIterationError):
                        recent_attempts.append(
                            {
                                "status": "failed",
                                "proposal": exc.proposal.model_dump(mode="json") if exc.proposal is not None else None,
                                "failure_reason": exc.failure_reason,
                            }
                        )
                        recent_attempts[:] = recent_attempts[-5:]
                    transcript.log(
                        f"RUN-ALL iter accelerator={accelerator_name} "
                        f"iteration={iteration_count} failed_reason={last_failure_reason}"
                    )
                    _write_status(
                        {
                            "mode": "run-all",
                            "current_accelerator": accelerator_name,
                            "phase": "candidate-failed",
                            "iteration": iteration_count,
                            "baseline_cycles": baseline_cycles,
                            "best_cycles": best_cycles,
                            "baseline_resource_score": _resource_score(baseline_metrics),
                            "best_resource_score": _resource_score(best_metrics),
                            "best_run_dir": str(best_run_dir),
                            "pareto_front_dir": str(pareto_front_dir),
                            "pareto_front_size": len(pareto_front),
                            "pareto_front": _pareto_status_payload(pareto_front, accelerator_name),
                            "last_failure_reason": last_failure_reason,
                            "completed_accelerators": state.completed_accelerators,
                            "recent_improvements": recent_improvements,
                        }
                    )
                    continue

                last_failure_reason = None
                iteration_count += 1
                ratio = improvement_ratio(best_cycles, candidate.metrics.accelerator_total_cycles)
                baseline_ratio = improvement_ratio(baseline_cycles, candidate.metrics.accelerator_total_cycles)
                resource_ratio_best = _resource_improvement(best_metrics, candidate.metrics)
                resource_ratio_baseline = _resource_improvement(baseline_metrics, candidate.metrics)
                recent_improvements.append(ratio)
                last_metrics = candidate.metrics
                if candidate.metrics.passed and candidate.metrics.accelerator_total_cycles < best_cycles:
                    best_cycles = candidate.metrics.accelerator_total_cycles
                    best_metrics = candidate.metrics
                    best_run_dir = _snapshot_best(accelerator_name, candidate.run_dir)
                pareto_front = _update_pareto_front(pareto_front, metrics=candidate.metrics, run_dir=candidate.run_dir)
                pareto_front_dir = _refresh_pareto_snapshots(accelerator_name, pareto_front)
                recent_attempts.append(
                    {
                        "status": "passed" if candidate.metrics.passed else "failed",
                        "proposal": candidate.proposal.model_dump(mode="json") if candidate.proposal is not None else None,
                        "metrics": _metrics_payload(candidate.metrics),
                        "improvement_vs_best_before_attempt": ratio,
                        "improvement_vs_baseline": baseline_ratio,
                        "resource_improvement_vs_best_before_attempt": resource_ratio_best,
                        "resource_improvement_vs_baseline": resource_ratio_baseline,
                    }
                )
                recent_attempts[:] = recent_attempts[-5:]
                transcript.log(
                    f"RUN-ALL iter accelerator={accelerator_name} "
                    f"iteration={iteration_count} cycles={candidate.metrics.accelerator_total_cycles} "
                    f"improvement_vs_best={ratio:.6f} best_cycles={best_cycles}"
                )
                _write_status(
                    {
                        "mode": "run-all",
                        "current_accelerator": accelerator_name,
                        "phase": "candidate",
                        "iteration": iteration_count,
                        "baseline_cycles": baseline_cycles,
                        "best_cycles": best_cycles,
                        "baseline_resource_score": _resource_score(baseline_metrics),
                        "best_resource_score": _resource_score(best_metrics),
                        "best_run_dir": str(best_run_dir),
                        "pareto_front_dir": str(pareto_front_dir),
                        "pareto_front_size": len(pareto_front),
                        "pareto_front": _pareto_status_payload(pareto_front, accelerator_name),
                        "last_cycles": candidate.metrics.accelerator_total_cycles,
                        "last_resource_score": _resource_score(candidate.metrics),
                        "last_resource_improvement_vs_best": resource_ratio_best,
                        "last_resource_improvement_vs_baseline": resource_ratio_baseline,
                        "last_failure_reason": last_failure_reason,
                        "completed_accelerators": state.completed_accelerators,
                        "recent_improvements": recent_improvements,
                    }
                )

            accelerator_completed = is_plateau(
                recent_improvements,
                min_improvement=float(scoring_config.get("minimum_improvement", 0.0)),
                window=int(scoring_config.get("plateau_window", 0)),
            )

            if stop_campaign:
                break

            state.recent_improvements = list(recent_improvements)

            if accelerator_completed:
                state.mark_completed(accelerator_name)
                transcript.log(f"RUN-ALL complete accelerator={accelerator_name}")
                print(
                    "Stopped accelerator "
                    f"{accelerator_name}: plateau detected after "
                    f"{int(scoring_config.get('plateau_window', 0))} consecutive non-improving iterations."
                )
            else:
                transcript.log(f"RUN-ALL paused accelerator={accelerator_name}")

            campaign_config["completed_accelerators"] = list(state.completed_accelerators)
            campaign_config["recent_improvements"] = list(state.recent_improvements)
            _write_campaign_config(campaign_config_path, campaign_config)

            if _stop_requested():
                break

            next_accelerator = next((name for name in queue if not state.has_completed(name)), None)
            if next_accelerator is not None:
                print(f"Next accelerator: {next_accelerator}")

        transcript.log("RUN-ALL finished")
        print("Run-all finished.")
        return 0
    finally:
        if PID_PATH.exists():
            PID_PATH.unlink()
        if STOP_PATH.exists():
            STOP_PATH.unlink()


__all__ = ["PID_PATH", "STATUS_PATH", "STOP_PATH", "request_stop", "run_all"]
