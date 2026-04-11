from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from soc_opt_agent.config_edit.editor import apply_changes
from soc_opt_agent.config_edit.parser import parse_esp_config
from soc_opt_agent.esp_flow.build import build_baremetal_command, build_esp_config_command
from soc_opt_agent.esp_flow.commands import build_sim_command
from soc_opt_agent.esp_flow.executor import CommandResult, run_command
from soc_opt_agent.llm.policy import LLMPolicy
from soc_opt_agent.models import IterationMetrics, LLMProposal
from soc_opt_agent.monitor.resource_parser import load_resource_report
from soc_opt_agent.monitor.transcript_parser import parse_transcript
from soc_opt_agent.orchestrator.progress import AgentTranscript
from soc_opt_agent.paths import (
    get_default_baselines_root,
    get_default_bests_root,
    get_default_benchmark_exe,
    get_default_esp_config_path,
    get_default_runs_root,
    get_default_soc_root,
    get_default_tech_acc_root,
    get_default_transcript_path,
    get_default_utilization_report_paths,
)


DEFAULT_ALLOWED_KEYS = {
    "CONFIG_QUEUE_SIZE",
    "CONFIG_COH_NOC_WIDTH",
    "CONFIG_DMA_NOC_WIDTH",
    "CONFIG_MEM_LINK_WIDTH",
    "CONFIG_CACHE_LINE_SIZE",
    "CONFIG_SLM_KBYTES",
    "CONFIG_CPU_CACHES",
    "CONFIG_ACC_CACHES",
}


@dataclass(slots=True)
class RunOnceResult:
    accelerator_name: str
    mode: str
    proposal: LLMProposal | None
    metrics: IterationMetrics
    run_dir: Path
    config_path: Path
    transcript_path: Path


class CandidateIterationError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        proposal: LLMProposal | None = None,
        run_dir: Path | None = None,
    ) -> None:
        super().__init__(message)
        self.proposal = proposal
        self.run_dir = run_dir
        self.failure_reason = message


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_run_dir(runs_root: Path, accelerator_name: str) -> Path:
    base_name = f"run_{_timestamp()}_{accelerator_name}"
    for index in range(1000):
        suffix = "" if index == 0 else f"_{index}"
        run_dir = runs_root / f"{base_name}{suffix}"
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
            return run_dir
        except FileExistsError:
            continue
    raise RuntimeError(f"Unable to allocate unique run directory for {accelerator_name} under {runs_root}")


def _baseline_dir(baselines_root: Path, accelerator_name: str) -> Path:
    return baselines_root / accelerator_name


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _serialize_command_result(result: CommandResult) -> dict[str, Any]:
    return {
        "command": result.command,
        "cwd": result.cwd,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def _create_agent_transcript(run_dir: Path, runs_root: Path) -> AgentTranscript:
    latest_log_path = runs_root.parent / "agent_transcript.log"
    run_log_path = run_dir / "agent_transcript.log"
    return AgentTranscript(paths=(run_log_path, latest_log_path))


def _build_context(
    *,
    accelerator_name: str,
    current_config: Mapping[str, str],
    scoring_config: Mapping[str, Any],
    baseline_metrics: IterationMetrics | None = None,
    best_metrics: IterationMetrics | None = None,
    last_metrics: IterationMetrics | None = None,
    recent_attempts: list[Mapping[str, Any]] | None = None,
    compatibility: Mapping[str, Any] | None = None,
    last_failure_reason: str | None = None,
) -> dict[str, Any]:
    context = {
        "accelerator_name": accelerator_name,
        "current_config": dict(current_config),
        "scoring_config": dict(scoring_config),
    }
    if baseline_metrics is not None:
        context["baseline_metrics"] = baseline_metrics.model_dump(mode="json", exclude_none=True)
    if best_metrics is not None:
        context["best_metrics"] = best_metrics.model_dump(mode="json", exclude_none=True)
    if last_metrics is not None:
        context["last_metrics"] = last_metrics.model_dump(mode="json", exclude_none=True)
        if best_metrics is not None:
            context["last_improvement_vs_best"] = (
                best_metrics.accelerator_total_cycles - last_metrics.accelerator_total_cycles
            ) / best_metrics.accelerator_total_cycles
            if (
                best_metrics.resource_score is not None
                and last_metrics.resource_score is not None
                and best_metrics.resource_score > 0
            ):
                context["last_resource_improvement_vs_best"] = (
                    best_metrics.resource_score - last_metrics.resource_score
                ) / best_metrics.resource_score
        if baseline_metrics is not None:
            context["last_improvement_vs_baseline"] = (
                baseline_metrics.accelerator_total_cycles - last_metrics.accelerator_total_cycles
            ) / baseline_metrics.accelerator_total_cycles
            if (
                baseline_metrics.resource_score is not None
                and last_metrics.resource_score is not None
                and baseline_metrics.resource_score > 0
            ):
                context["last_resource_improvement_vs_baseline"] = (
                    baseline_metrics.resource_score - last_metrics.resource_score
                ) / baseline_metrics.resource_score
    if recent_attempts:
        context["recent_attempts"] = [dict(item) for item in recent_attempts]
    if compatibility:
        context["compatibility"] = dict(compatibility)
    if last_failure_reason:
        context["last_failure_reason"] = last_failure_reason
    return context


def _load_metrics(path: Path) -> IterationMetrics:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError(f"Expected {path} to contain a JSON object")
    return IterationMetrics(**payload)


def _resource_metrics_payload(soc_root: Path) -> dict[str, float]:
    for candidate in get_default_utilization_report_paths(soc_root):
        if not candidate.exists():
            continue
        try:
            return load_resource_report(candidate)
        except ValueError:
            continue
    return {}


def _supported_dma_widths(accelerator_name: str, tech_acc_root: Path) -> list[int]:
    acc_dir = tech_acc_root / accelerator_name
    if not acc_dir.exists():
        return []

    widths: set[int] = set()
    for candidate in acc_dir.iterdir():
        if not candidate.is_dir():
            continue
        for match in re.finditer(r"dma(\d+)", candidate.name):
            widths.add(int(match.group(1)))
    return sorted(widths)


def _merge_metrics_with_resources(metrics: IterationMetrics, soc_root: Path) -> IterationMetrics:
    resource_payload = _resource_metrics_payload(soc_root)
    if not resource_payload:
        return metrics
    merged = metrics.model_dump(mode="json")
    merged.update(resource_payload)
    return IterationMetrics(**merged)


def _resource_improvement_ratio(reference: IterationMetrics | None, current: IterationMetrics) -> float | None:
    if reference is None or reference.resource_score is None or current.resource_score is None:
        return None
    if reference.resource_score <= 0:
        return None
    return (reference.resource_score - current.resource_score) / reference.resource_score


def refresh_saved_run_resources(
    run_dir: Path,
    *,
    soc_root: Path | None = None,
) -> IterationMetrics | None:
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.exists():
        return None

    resolved_soc_root = soc_root or get_default_soc_root()
    metrics = _load_metrics(metrics_path)
    refreshed_metrics = _merge_metrics_with_resources(metrics, resolved_soc_root)
    _write_json(metrics_path, refreshed_metrics.model_dump(mode="json"))

    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        if isinstance(payload, Mapping):
            updated_payload = dict(payload)
            if "metrics" in updated_payload:
                updated_payload["metrics"] = refreshed_metrics.model_dump(mode="json")
            if "resource_score" in updated_payload:
                updated_payload["resource_score"] = refreshed_metrics.resource_score
            _write_json(summary_path, updated_payload)

    return refreshed_metrics


def refresh_existing_accelerator_resources(
    *,
    accelerator_name: str,
    soc_root: Path | None = None,
    baselines_root: Path | None = None,
    bests_root: Path | None = None,
    status_path: Path | None = None,
) -> dict[str, IterationMetrics | None]:
    resolved_soc_root = soc_root or get_default_soc_root()
    resolved_baselines_root = baselines_root or get_default_baselines_root()
    resolved_bests_root = bests_root or get_default_bests_root()
    baseline_dir = _baseline_dir(resolved_baselines_root, accelerator_name)
    best_dir = resolved_bests_root / accelerator_name

    baseline_metrics = refresh_saved_run_resources(baseline_dir, soc_root=resolved_soc_root) if baseline_dir.exists() else None
    best_metrics = refresh_saved_run_resources(best_dir, soc_root=resolved_soc_root) if best_dir.exists() else None

    resolved_status_path = status_path or get_default_runs_root().parent / "run_all.status.json"
    if resolved_status_path.exists():
        payload = json.loads(resolved_status_path.read_text(encoding="utf-8"))
        if isinstance(payload, Mapping):
            updated_payload = dict(payload)
            if baseline_metrics is not None:
                updated_payload["baseline_resource_score"] = baseline_metrics.resource_score
            if best_metrics is not None:
                updated_payload["best_resource_score"] = best_metrics.resource_score
            _write_json(resolved_status_path, updated_payload)

    return {
        "baseline": baseline_metrics,
        "best": best_metrics,
    }


def _compatibility_context(accelerator_name: str, tech_acc_root: Path) -> dict[str, Any]:
    supported_dma_widths = _supported_dma_widths(accelerator_name, tech_acc_root)
    return {
        "supported_dma_noc_widths": supported_dma_widths,
        "supported_mem_link_widths": supported_dma_widths,
    }


def _resolve_accelerator_tile(
    accelerator_name: str,
    tech_acc_root: Path,
    config: Mapping[str, str] | None = None,
) -> tuple[str, str]:
    acc_dir = tech_acc_root / accelerator_name
    if not acc_dir.exists():
        raise ValueError(f"Unable to locate accelerator implementation directory for {accelerator_name} under {tech_acc_root}")

    implementations = sorted(
        child.name
        for child in acc_dir.iterdir()
        if child.is_dir() and child.name.startswith(f"{accelerator_name}_")
    )
    if not implementations:
        raise ValueError(f"Unable to locate accelerator implementation for {accelerator_name} under {acc_dir}")

    implementation_name: str | None = None
    if config is not None:
        dma_width = config.get("CONFIG_DMA_NOC_WIDTH")
        if dma_width is not None:
            target_token = f"dma{dma_width}"
            for candidate in implementations:
                if target_token in candidate:
                    implementation_name = candidate.removeprefix(f"{accelerator_name}_")
                    break

    if implementation_name is None:
        implementation_name = implementations[0].removeprefix(f"{accelerator_name}_")
    return accelerator_name.upper(), implementation_name


def _apply_accelerator_target(text: str, accelerator_name: str, tech_acc_root: Path) -> str:
    config = parse_esp_config(text)
    accelerator_symbol, implementation_name = _resolve_accelerator_tile(
        accelerator_name,
        tech_acc_root,
        config,
    )
    tile_pattern = re.compile(r"^(TILE_\d+_\d+\s*=\s*\d+\s+acc\s+)([A-Z0-9_]+)(\s+)([A-Za-z0-9_]+)(.*)$")

    updated_lines: list[str] = []
    replaced = False
    for raw_line in text.splitlines(keepends=True):
        match = tile_pattern.match(raw_line.rstrip("\r\n"))
        if match is None or replaced:
            updated_lines.append(raw_line)
            continue

        newline = "\r\n" if raw_line.endswith("\r\n") else "\n" if raw_line.endswith("\n") else ""
        updated_lines.append(
            f"{match.group(1)}{accelerator_symbol}{match.group(3)}{implementation_name}{match.group(5)}{newline}"
        )
        replaced = True

    if not replaced:
        raise ValueError("Unable to locate accelerator tile assignment in .esp_config")

    return "".join(updated_lines)


def _validate_proposal_compatibility(
    *,
    accelerator_name: str,
    proposal: LLMProposal,
    tech_acc_root: Path,
) -> str | None:
    supported_dma_widths = _supported_dma_widths(accelerator_name, tech_acc_root)
    if not supported_dma_widths:
        return None

    proposed_dma_width = proposal.changes.get("CONFIG_DMA_NOC_WIDTH")
    if proposed_dma_width is not None:
        width = int(proposed_dma_width)
        if width not in supported_dma_widths:
            return (
                f"CONFIG_DMA_NOC_WIDTH={width} is incompatible with installed implementations for "
                f"{accelerator_name}; supported widths: {supported_dma_widths}"
            )

    proposed_mem_link_width = proposal.changes.get("CONFIG_MEM_LINK_WIDTH")
    if proposed_mem_link_width is not None:
        width = int(proposed_mem_link_width)
        if width not in supported_dma_widths:
            return (
                f"CONFIG_MEM_LINK_WIDTH={width} is incompatible with installed DMA implementations for "
                f"{accelerator_name}; supported widths: {supported_dma_widths}"
            )

    return None


def _write_failure_summary(
    *,
    run_dir: Path,
    accelerator_name: str,
    mode: str,
    benchmark_exe: Path,
    proposal: LLMProposal | None,
    failure_reason: str,
) -> None:
    payload: dict[str, Any] = {
        "mode": mode,
        "accelerator_name": accelerator_name,
        "benchmark_exe": str(benchmark_exe),
        "status": "failed",
        "failure_reason": failure_reason,
    }
    if proposal is not None:
        payload["proposal"] = proposal.model_dump(mode="json")
    _write_json(run_dir / "summary.json", payload)


def load_saved_baseline(
    *,
    accelerator_name: str,
    baselines_root: Path | None = None,
    soc_root: Path | None = None,
    esp_config_path: Path | None = None,
    transcript_path: Path | None = None,
) -> RunOnceResult | None:
    resolved_soc_root = soc_root or get_default_soc_root()
    config_path = esp_config_path or get_default_esp_config_path(resolved_soc_root)
    resolved_transcript_path = transcript_path or get_default_transcript_path(resolved_soc_root)
    resolved_baselines_root = baselines_root or get_default_baselines_root()
    baseline_dir = _baseline_dir(resolved_baselines_root, accelerator_name)
    metrics_path = baseline_dir / "metrics.json"
    if not metrics_path.exists():
        return None

    return RunOnceResult(
        accelerator_name=accelerator_name,
        mode="baseline",
        proposal=None,
        metrics=_load_metrics(metrics_path),
        run_dir=baseline_dir,
        config_path=config_path,
        transcript_path=resolved_transcript_path,
    )


def _persist_baseline(run_dir: Path, baseline_dir: Path) -> None:
    baseline_dir.mkdir(parents=True, exist_ok=False)
    for source in run_dir.iterdir():
        if source.is_file():
            baseline_dir.joinpath(source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _cleanup_transient_artifacts(transcript_path: Path) -> None:
    if transcript_path.exists():
        transcript_path.unlink()
    trace_log_path = transcript_path.with_name("trace_hart_0.log")
    if trace_log_path.exists():
        trace_log_path.unlink()


def _execute_command(
    *,
    stage_name: str,
    command: list[str],
    cwd: Path,
    command_runner: Callable[[list[str], Path], CommandResult],
    transcript: AgentTranscript,
) -> CommandResult:
    transcript.log(f"START {stage_name}: {' '.join(command)}")
    try:
        if command_runner is run_command:
            result = run_command(
                command,
                cwd,
                on_output=lambda line: transcript.log(f"[{stage_name}] {line}"),
            )
        else:
            result = command_runner(command, cwd)
            if result.stdout:
                for line in result.stdout.splitlines():
                    transcript.log(f"[{stage_name}] {line}")
            if result.stderr:
                for line in result.stderr.splitlines():
                    transcript.log(f"[{stage_name}][stderr] {line}")
        transcript.log(f"END {stage_name}: returncode={result.returncode}")
        return result
    except Exception as exc:
        transcript.log(f"FAIL {stage_name}: {exc}")
        raise


def _restore_runnable_state(
    *,
    original_text: str,
    config_path: Path,
    soc_root: Path,
    command_runner: Callable[[list[str], Path], CommandResult],
    transcript: AgentTranscript,
) -> None:
    config_path.write_text(original_text, encoding="utf-8")
    transcript.log("RESTORE previous runnable .esp_config after candidate failure")
    try:
        _execute_command(
            stage_name="esp-config-restore",
            command=build_esp_config_command(),
            cwd=soc_root,
            command_runner=command_runner,
            transcript=transcript,
        )
    except Exception as restore_exc:
        transcript.log(f"FAIL restore-generated-state: {restore_exc}")


def run_baseline_iteration(
    *,
    accelerator_name: str,
    soc_root: Path | None = None,
    esp_config_path: Path | None = None,
    transcript_path: Path | None = None,
    runs_root: Path | None = None,
    baselines_root: Path | None = None,
    tech_acc_root: Path | None = None,
    command_runner: Callable[[list[str], Path], CommandResult] = run_command,
) -> RunOnceResult:
    resolved_soc_root = soc_root or get_default_soc_root()
    config_path = esp_config_path or get_default_esp_config_path(resolved_soc_root)
    resolved_transcript_path = transcript_path or get_default_transcript_path(resolved_soc_root)
    resolved_runs_root = runs_root or get_default_runs_root()
    resolved_baselines_root = baselines_root or get_default_baselines_root()
    resolved_tech_acc_root = tech_acc_root or get_default_tech_acc_root(resolved_soc_root)
    benchmark_exe = get_default_benchmark_exe(accelerator_name, resolved_soc_root)
    existing_baseline = load_saved_baseline(
        accelerator_name=accelerator_name,
        baselines_root=resolved_baselines_root,
        soc_root=resolved_soc_root,
        esp_config_path=config_path,
        transcript_path=resolved_transcript_path,
    )
    if existing_baseline is not None:
        latest_transcript = AgentTranscript(paths=((resolved_runs_root.parent / "agent_transcript.log"),))
        latest_transcript.log(f"REUSE baseline for {accelerator_name} from {existing_baseline.run_dir}")
        return existing_baseline

    run_dir = _ensure_run_dir(resolved_runs_root, f"{accelerator_name}_baseline")
    agent_transcript = _create_agent_transcript(run_dir, resolved_runs_root)
    original_text = config_path.read_text(encoding="utf-8")
    updated_text = _apply_accelerator_target(original_text, accelerator_name, resolved_tech_acc_root)
    agent_transcript.log(f"START baseline accelerator={accelerator_name}")

    (run_dir / "config_before.esp_config").write_text(original_text, encoding="utf-8")
    (run_dir / "config_after.esp_config").write_text(updated_text, encoding="utf-8")
    config_path.write_text(updated_text, encoding="utf-8")

    _cleanup_transient_artifacts(resolved_transcript_path)

    command_results: list[CommandResult] = []
    command_results.append(
        _execute_command(
            stage_name="esp-config",
            command=build_esp_config_command(),
            cwd=resolved_soc_root,
            command_runner=command_runner,
            transcript=agent_transcript,
        )
    )
    command_results.append(
        _execute_command(
            stage_name="baremetal-build",
            command=build_baremetal_command(accelerator_name),
            cwd=resolved_soc_root,
            command_runner=command_runner,
            transcript=agent_transcript,
        )
    )
    command_results.append(
        _execute_command(
            stage_name="sim",
            command=build_sim_command(str(benchmark_exe)),
            cwd=resolved_soc_root,
            command_runner=command_runner,
            transcript=agent_transcript,
        )
    )

    transcript_text = resolved_transcript_path.read_text(encoding="utf-8")
    (run_dir / "transcript.txt").write_text(transcript_text, encoding="utf-8")
    metrics = _merge_metrics_with_resources(parse_transcript(transcript_text), resolved_soc_root)
    agent_transcript.log(
        "END baseline "
        f"passed={metrics.passed} cycles={metrics.accelerator_total_cycles} "
        f"offchip_memory_accesses={metrics.offchip_memory_accesses} "
        f"resource_score={metrics.resource_score}"
    )
    _write_json(run_dir / "metrics.json", metrics.model_dump(mode="json"))
    _write_json(
        run_dir / "commands.json",
        {"commands": [_serialize_command_result(item) for item in command_results]},
    )
    _write_json(
        run_dir / "summary.json",
        {
            "mode": "baseline",
            "accelerator_name": accelerator_name,
            "benchmark_exe": str(benchmark_exe),
            "metrics": metrics.model_dump(mode="json"),
            "resource_score": metrics.resource_score,
        },
    )
    baseline_dir = _baseline_dir(resolved_baselines_root, accelerator_name)
    _persist_baseline(run_dir, baseline_dir)

    return RunOnceResult(
        accelerator_name=accelerator_name,
        mode="baseline",
        proposal=None,
        metrics=metrics,
        run_dir=baseline_dir,
        config_path=config_path,
        transcript_path=resolved_transcript_path,
    )


def run_candidate_iteration(
    *,
    accelerator_name: str,
    llm_policy: LLMPolicy,
    llm_config: Mapping[str, Any],
    search_space: Mapping[str, Any],
    scoring_config: Mapping[str, Any],
    baseline_metrics: IterationMetrics | None = None,
    best_metrics: IterationMetrics | None = None,
    last_metrics: IterationMetrics | None = None,
    recent_attempts: list[Mapping[str, Any]] | None = None,
    soc_root: Path | None = None,
    esp_config_path: Path | None = None,
    transcript_path: Path | None = None,
    runs_root: Path | None = None,
    tech_acc_root: Path | None = None,
    last_failure_reason: str | None = None,
    command_runner: Callable[[list[str], Path], CommandResult] = run_command,
) -> RunOnceResult:
    resolved_soc_root = soc_root or get_default_soc_root()
    config_path = esp_config_path or get_default_esp_config_path(resolved_soc_root)
    resolved_transcript_path = transcript_path or get_default_transcript_path(resolved_soc_root)
    resolved_runs_root = runs_root or get_default_runs_root()
    resolved_tech_acc_root = tech_acc_root or get_default_tech_acc_root(resolved_soc_root)
    benchmark_exe = get_default_benchmark_exe(accelerator_name, resolved_soc_root)

    original_text = config_path.read_text(encoding="utf-8")
    target_text = _apply_accelerator_target(original_text, accelerator_name, resolved_tech_acc_root)
    current_config = parse_esp_config(target_text)
    allowed_keys = set(search_space.get("allowed_keys", DEFAULT_ALLOWED_KEYS))
    current_subset = {key: value for key, value in current_config.items() if key in allowed_keys}
    proposal = llm_policy.request_proposal(
        model=str(llm_config.get("model", "gemini-2.5-flash")),
        temperature=float(llm_config.get("temperature", 0.2)),
        response_format=str(llm_config.get("response_format", "structured_json")),
        context=_build_context(
            accelerator_name=accelerator_name,
            current_config=current_subset,
            scoring_config=scoring_config,
            baseline_metrics=baseline_metrics,
            best_metrics=best_metrics,
            last_metrics=last_metrics,
            recent_attempts=recent_attempts,
            compatibility=_compatibility_context(accelerator_name, resolved_tech_acc_root),
            last_failure_reason=last_failure_reason,
        ),
    )
    run_dir = _ensure_run_dir(resolved_runs_root, accelerator_name)
    agent_transcript = _create_agent_transcript(run_dir, resolved_runs_root)
    agent_transcript.log(
        f"START candidate accelerator={accelerator_name} changes={json.dumps(proposal.model_dump(mode='json')['changes'], sort_keys=True)}"
    )

    updated_text = apply_changes(
        target_text,
        proposal.changes,
        allowed_keys=allowed_keys,
    )

    (run_dir / "config_before.esp_config").write_text(original_text, encoding="utf-8")
    _write_json(run_dir / "proposal.json", proposal.model_dump(mode="json"))

    compatibility_error = _validate_proposal_compatibility(
        accelerator_name=accelerator_name,
        proposal=proposal,
        tech_acc_root=resolved_tech_acc_root,
    )
    if compatibility_error is not None:
        agent_transcript.log(f"REJECT candidate compatibility_error={compatibility_error}")
        _write_failure_summary(
            run_dir=run_dir,
            accelerator_name=accelerator_name,
            mode="candidate",
            benchmark_exe=benchmark_exe,
            proposal=proposal,
            failure_reason=compatibility_error,
        )
        raise CandidateIterationError(
            compatibility_error,
            proposal=proposal,
            run_dir=run_dir,
        )

    (run_dir / "config_after.esp_config").write_text(updated_text, encoding="utf-8")

    config_path.write_text(updated_text, encoding="utf-8")
    _cleanup_transient_artifacts(resolved_transcript_path)

    command_results: list[CommandResult] = []
    try:
        command_results.append(
            _execute_command(
                stage_name="esp-config",
                command=build_esp_config_command(),
                cwd=resolved_soc_root,
                command_runner=command_runner,
                transcript=agent_transcript,
            )
        )
        command_results.append(
            _execute_command(
                stage_name="baremetal-build",
                command=build_baremetal_command(accelerator_name),
                cwd=resolved_soc_root,
                command_runner=command_runner,
                transcript=agent_transcript,
            )
        )
        command_results.append(
            _execute_command(
                stage_name="sim",
                command=build_sim_command(str(benchmark_exe)),
                cwd=resolved_soc_root,
                command_runner=command_runner,
                transcript=agent_transcript,
            )
        )
    except Exception:
        _restore_runnable_state(
            original_text=original_text,
            config_path=config_path,
            soc_root=resolved_soc_root,
            command_runner=command_runner,
            transcript=agent_transcript,
        )
        _write_failure_summary(
            run_dir=run_dir,
            accelerator_name=accelerator_name,
            mode="candidate",
            benchmark_exe=benchmark_exe,
            proposal=proposal,
            failure_reason="candidate execution failed; restored previous runnable state",
        )
        raise CandidateIterationError(
            "candidate execution failed; restored previous runnable state",
            proposal=proposal,
            run_dir=run_dir,
        )

    transcript_text = resolved_transcript_path.read_text(encoding="utf-8")
    (run_dir / "transcript.txt").write_text(transcript_text, encoding="utf-8")
    metrics = _merge_metrics_with_resources(parse_transcript(transcript_text), resolved_soc_root)
    agent_transcript.log(
        "END candidate "
        f"passed={metrics.passed} cycles={metrics.accelerator_total_cycles} "
        f"offchip_memory_accesses={metrics.offchip_memory_accesses} "
        f"resource_score={metrics.resource_score}"
    )
    _write_json(run_dir / "metrics.json", metrics.model_dump(mode="json"))
    _write_json(
        run_dir / "commands.json",
        {"commands": [_serialize_command_result(item) for item in command_results]},
    )
    _write_json(
        run_dir / "summary.json",
        {
            "mode": "candidate",
            "accelerator_name": accelerator_name,
            "benchmark_exe": str(benchmark_exe),
            "proposal": proposal.model_dump(mode="json"),
            "metrics": metrics.model_dump(mode="json"),
            "cycles_improvement_vs_baseline": (
                (baseline_metrics.accelerator_total_cycles - metrics.accelerator_total_cycles)
                / baseline_metrics.accelerator_total_cycles
                if baseline_metrics is not None
                else None
            ),
            "cycles_improvement_vs_best": (
                (best_metrics.accelerator_total_cycles - metrics.accelerator_total_cycles)
                / best_metrics.accelerator_total_cycles
                if best_metrics is not None
                else None
            ),
            "resource_score": metrics.resource_score,
            "resource_improvement_vs_baseline": _resource_improvement_ratio(baseline_metrics, metrics),
            "resource_improvement_vs_best": _resource_improvement_ratio(best_metrics, metrics),
        },
    )

    return RunOnceResult(
        accelerator_name=accelerator_name,
        mode="candidate",
        proposal=proposal,
        metrics=metrics,
        run_dir=run_dir,
        config_path=config_path,
        transcript_path=resolved_transcript_path,
    )


__all__ = [
    "CandidateIterationError",
    "DEFAULT_ALLOWED_KEYS",
    "RunOnceResult",
    "load_saved_baseline",
    "refresh_existing_accelerator_resources",
    "refresh_saved_run_resources",
    "run_baseline_iteration",
    "run_candidate_iteration",
]
