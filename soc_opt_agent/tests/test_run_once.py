from __future__ import annotations

import json
from pathlib import Path

import pytest

from soc_opt_agent.models import IterationMetrics, LLMProposal
from soc_opt_agent.orchestrator import run_once as run_once_module
from soc_opt_agent.orchestrator.run_once import (
    CandidateIterationError,
    _apply_accelerator_target,
    load_saved_baseline,
    refresh_existing_accelerator_resources,
    run_baseline_iteration,
    run_candidate_iteration,
)


def _write_fixture_soc(tmp_path: Path) -> tuple[Path, Path, Path]:
    soc_root = tmp_path / "soc"
    esp_config_path = soc_root / "socgen" / "esp" / ".esp_config"
    transcript_path = soc_root / "modelsim" / "transcript"
    trace_log_path = soc_root / "modelsim" / "trace_hart_0.log"
    esp_config_path.parent.mkdir(parents=True)
    transcript_path.parent.mkdir(parents=True)
    (soc_root / "soft-build" / "ariane" / "baremetal").mkdir(parents=True)
    (soc_root / "vivado" / f"esp-{soc_root.name}.runs" / "impl_1").mkdir(parents=True)
    esp_config_path.write_text(
        "CPU_ARCH = ariane\n"
        "TILE_1_0 = 2 acc AESCIPHER_RTL basic_dma64 0 0 sld\n"
        "CONFIG_QUEUE_SIZE = 4\n"
        "CONFIG_DMA_NOC_WIDTH = 64\n",
        encoding="utf-8",
    )
    transcript_path.write_text(
        "\n".join(
            [
                "ESP MONITOR STATS",
                "Accelerator 0 total cycles: 63",
                "Off-chip memory accesses at mem tile 0: 186",
                "... PASS",
            ]
        ),
        encoding="utf-8",
    )
    trace_log_path.write_text("stale\n", encoding="utf-8")
    tech_acc_root = tmp_path / "tech" / "virtex7" / "acc" / "aescipher_rtl"
    (tech_acc_root / "aescipher_rtl_basic_dma64").mkdir(parents=True)
    runs_root = tmp_path / "runs"
    return soc_root, esp_config_path, runs_root


def _write_utilization_report(soc_root: Path) -> None:
    report_path = soc_root / "vivado" / f"esp-{soc_root.name}.runs" / "impl_1" / "top_utilization_placed.rpt"
    report_path.write_text(
        "\n".join(
            [
                "| Slice LUTs                 | 133512 |     0 |          0 |    303600 | 43.98 |",
                "| Slice Registers            | 114701 |     0 |          0 |    607200 | 18.89 |",
                "| Block RAM Tile            | 187.5 |     0 |          0 |      1030 | 18.20 |",
                "| DSPs           |   27 |     0 |          0 |      2800 |  0.96 |",
            ]
        ),
        encoding="utf-8",
    )


def test_run_baseline_iteration_executes_commands_and_writes_artifacts(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    _write_utilization_report(soc_root)
    baselines_root = tmp_path / "baselines"
    tech_root = tmp_path / "tech" / "virtex7" / "acc"
    seen_commands: list[list[str]] = []

    class Result:
        def __init__(self, command: list[str], cwd: str) -> None:
            self.command = command
            self.cwd = cwd
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_runner(command: list[str], cwd: Path):
        seen_commands.append(command)
        if command[0:2] == ["make", "sim"]:
            (soc_root / "modelsim" / "transcript").write_text(
                "\n".join(
                    [
                        "ESP MONITOR STATS",
                        "Accelerator 0 total cycles: 63",
                        "Off-chip memory accesses at mem tile 0: 186",
                        "... PASS",
                    ]
                ),
                encoding="utf-8",
            )
        return Result(command, str(cwd))

    result = run_baseline_iteration(
        accelerator_name="aescipher_rtl",
        soc_root=soc_root,
        esp_config_path=esp_config_path,
        transcript_path=soc_root / "modelsim" / "transcript",
        runs_root=runs_root,
        baselines_root=baselines_root,
        tech_acc_root=tech_root,
        command_runner=fake_runner,
    )

    assert seen_commands == [
        ["make", "esp-config"],
        ["make", "aescipher_rtl-baremetal"],
        ["make", "sim", f"TEST_PROGRAM={soc_root / 'soft-build' / 'ariane' / 'baremetal' / 'aescipher_rtl.exe'}"],
    ]
    assert result.metrics == IterationMetrics(
        passed=True,
        accelerator_total_cycles=63,
        offchip_memory_accesses=186,
        lut_utilization=43.98,
        ff_utilization=18.89,
        bram_utilization=18.20,
        dsp_utilization=0.96,
        resource_score=(43.98 + 18.89 + 18.20 + 0.96) / 4.0,
    )
    assert result.mode == "baseline"
    assert result.proposal is None
    assert "CONFIG_QUEUE_SIZE = 4" in esp_config_path.read_text(encoding="utf-8")
    assert not (result.run_dir / "proposal.json").exists()
    assert (result.run_dir / "metrics.json").exists()
    assert (result.run_dir / "agent_transcript.log").exists()
    assert result.run_dir == baselines_root / "aescipher_rtl"
    summary = json.loads((result.run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["mode"] == "baseline"
    assert summary["resource_score"] == pytest.approx((43.98 + 18.89 + 18.20 + 0.96) / 4.0)
    assert not (soc_root / "modelsim" / "trace_hart_0.log").exists()
    run_dirs = list(runs_root.glob("run_*_aescipher_rtl_baseline"))
    assert len(run_dirs) == 1
    assert (run_dirs[0] / "metrics.json").exists()
    latest_agent_transcript = runs_root.parent / "agent_transcript.log"
    assert latest_agent_transcript.exists()
    transcript_text = latest_agent_transcript.read_text(encoding="utf-8")
    assert "START baseline accelerator=aescipher_rtl" in transcript_text
    assert "START esp-config: make esp-config" in transcript_text
    assert "START baremetal-build: make aescipher_rtl-baremetal" in transcript_text
    assert "START sim: make sim TEST_PROGRAM=" in transcript_text
    assert "END baseline passed=True cycles=63 offchip_memory_accesses=186" in transcript_text


def test_run_candidate_iteration_writes_resource_metrics_when_report_exists(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    _write_utilization_report(soc_root)
    tech_root = tmp_path / "tech" / "virtex7" / "acc"

    class StubPolicy:
        def request_proposal(self, **kwargs):
            return LLMProposal(
                changes={"CONFIG_QUEUE_SIZE": 8},
                rationale="Increase buffering",
                search_intent="latency",
            )

    class Result:
        def __init__(self, command: list[str], cwd: str) -> None:
            self.command = command
            self.cwd = cwd
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_runner(command: list[str], cwd: Path):
        if command[0:2] == ["make", "sim"]:
            (soc_root / "modelsim" / "transcript").write_text(
                "\n".join(
                    [
                        "ESP MONITOR STATS",
                        "Accelerator 0 total cycles: 60",
                        "Off-chip memory accesses at mem tile 0: 180",
                        "... PASS",
                    ]
                ),
                encoding="utf-8",
            )
        return Result(command, str(cwd))

    result = run_candidate_iteration(
        accelerator_name="aescipher_rtl",
        llm_policy=StubPolicy(),
        llm_config={},
        search_space={"allowed_keys": ["CONFIG_QUEUE_SIZE"]},
        scoring_config={},
        soc_root=soc_root,
        esp_config_path=esp_config_path,
        transcript_path=soc_root / "modelsim" / "transcript",
        runs_root=runs_root,
        tech_acc_root=tech_root,
        command_runner=fake_runner,
    )

    assert result.metrics.lut_utilization == 43.98
    assert result.metrics.ff_utilization == 18.89
    assert result.metrics.bram_utilization == 18.20
    assert result.metrics.dsp_utilization == 0.96
    assert result.metrics.resource_score == pytest.approx((43.98 + 18.89 + 18.20 + 0.96) / 4.0)
    saved_metrics = json.loads((result.run_dir / "metrics.json").read_text(encoding="utf-8"))
    assert saved_metrics["resource_score"] == pytest.approx((43.98 + 18.89 + 18.20 + 0.96) / 4.0)
    saved_summary = json.loads((result.run_dir / "summary.json").read_text(encoding="utf-8"))
    assert saved_summary["resource_score"] == pytest.approx((43.98 + 18.89 + 18.20 + 0.96) / 4.0)
    assert saved_summary["resource_improvement_vs_baseline"] is None
    assert saved_summary["resource_improvement_vs_best"] is None


def test_run_candidate_iteration_does_not_fallback_to_synth_report(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    synth_report = soc_root / "vivado" / f"esp-{soc_root.name}.runs" / "synth_1" / "top_utilization_synth.rpt"
    synth_report.parent.mkdir(parents=True, exist_ok=True)
    synth_report.write_text(
        "\n".join(
            [
                "| Slice LUTs*                | 482595 |     0 |          0 |    303600 | 158.96 |",
                "| Slice Registers            | 111517 |     0 |          0 |    607200 | 18.37 |",
                "| Block RAM Tile    | 187.5 |     0 |          0 |      1030 | 18.20 |",
                "| DSPs           |   27 |     0 |          0 |      2800 |  0.96 |",
            ]
        ),
        encoding="utf-8",
    )
    tech_root = tmp_path / "tech" / "virtex7" / "acc"

    class StubPolicy:
        def request_proposal(self, **kwargs):
            return LLMProposal(
                changes={"CONFIG_QUEUE_SIZE": 8},
                rationale="Increase buffering",
                search_intent="latency",
            )

    class Result:
        def __init__(self, command: list[str], cwd: str) -> None:
            self.command = command
            self.cwd = cwd
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_runner(command: list[str], cwd: Path):
        if command[0:2] == ["make", "sim"]:
            (soc_root / "modelsim" / "transcript").write_text(
                "\n".join(
                    [
                        "ESP MONITOR STATS",
                        "Accelerator 0 total cycles: 60",
                        "Off-chip memory accesses at mem tile 0: 180",
                        "... PASS",
                    ]
                ),
                encoding="utf-8",
            )
        return Result(command, str(cwd))

    result = run_candidate_iteration(
        accelerator_name="aescipher_rtl",
        llm_policy=StubPolicy(),
        llm_config={},
        search_space={"allowed_keys": ["CONFIG_QUEUE_SIZE"]},
        scoring_config={},
        soc_root=soc_root,
        esp_config_path=esp_config_path,
        transcript_path=soc_root / "modelsim" / "transcript",
        runs_root=runs_root,
        tech_acc_root=tech_root,
        command_runner=fake_runner,
    )

    assert result.metrics.lut_utilization is None
    assert result.metrics.resource_score is None


def test_refresh_existing_accelerator_resources_updates_baseline_best_and_status(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    _write_utilization_report(soc_root)
    baselines_root = tmp_path / "baselines"
    bests_root = tmp_path / "bests"
    baseline_dir = baselines_root / "aescipher_rtl"
    best_dir = bests_root / "aescipher_rtl"
    baseline_dir.mkdir(parents=True)
    best_dir.mkdir(parents=True)

    stale_metrics = {
        "passed": True,
        "accelerator_total_cycles": 63,
        "offchip_memory_accesses": 186,
        "lut_utilization": 158.96,
        "ff_utilization": 18.37,
        "bram_utilization": 18.20,
        "dsp_utilization": 0.96,
        "resource_score": 49.1225,
    }
    stale_summary = {
        "mode": "baseline",
        "accelerator_name": "aescipher_rtl",
        "benchmark_exe": str(soc_root / "soft-build" / "ariane" / "baremetal" / "aescipher_rtl.exe"),
        "metrics": stale_metrics,
        "resource_score": 49.1225,
    }
    for target in (baseline_dir, best_dir):
        (target / "metrics.json").write_text(json.dumps(stale_metrics), encoding="utf-8")
        (target / "summary.json").write_text(json.dumps(stale_summary), encoding="utf-8")

    status_path = tmp_path / "run_all.status.json"
    status_path.write_text(
        json.dumps(
            {
                "current_accelerator": "aescipher_rtl",
                "phase": "baseline-ready",
                "baseline_resource_score": 49.1225,
                "best_resource_score": 49.1225,
            }
        ),
        encoding="utf-8",
    )

    refreshed = refresh_existing_accelerator_resources(
        accelerator_name="aescipher_rtl",
        soc_root=soc_root,
        baselines_root=baselines_root,
        bests_root=bests_root,
        status_path=status_path,
    )

    assert refreshed["baseline"] is not None
    assert refreshed["baseline"].lut_utilization == 43.98
    assert refreshed["baseline"].resource_score == pytest.approx((43.98 + 18.89 + 18.20 + 0.96) / 4.0)

    baseline_metrics = json.loads((baseline_dir / "metrics.json").read_text(encoding="utf-8"))
    assert baseline_metrics["lut_utilization"] == 43.98
    baseline_summary = json.loads((baseline_dir / "summary.json").read_text(encoding="utf-8"))
    assert baseline_summary["resource_score"] == pytest.approx((43.98 + 18.89 + 18.20 + 0.96) / 4.0)
    assert baseline_summary["metrics"]["lut_utilization"] == 43.98

    status_payload = json.loads(status_path.read_text(encoding="utf-8"))
    assert status_payload["baseline_resource_score"] == pytest.approx((43.98 + 18.89 + 18.20 + 0.96) / 4.0)
    assert status_payload["best_resource_score"] == pytest.approx((43.98 + 18.89 + 18.20 + 0.96) / 4.0)


def test_run_baseline_iteration_switches_tile_accelerator_to_target(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    baselines_root = tmp_path / "baselines"
    esp_config_path.write_text(
        "CPU_ARCH = ariane\n"
        "TILE_1_0 = 2 acc AESCIPHER_RTL basic_dma64 0 0 sld\n",
        encoding="utf-8",
    )
    tech_root = tmp_path / "tech" / "virtex7" / "acc"
    acc_dir = tech_root / "aesdecipher_v2_rtl" / "aesdecipher_v2_rtl_basic_dma64"
    acc_dir.mkdir(parents=True, exist_ok=True)

    class Result:
        def __init__(self, command: list[str], cwd: str) -> None:
            self.command = command
            self.cwd = cwd
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_runner(command: list[str], cwd: Path):
        if command[0:2] == ["make", "sim"]:
            (soc_root / "modelsim" / "transcript").write_text(
                "\n".join(
                    [
                        "ESP MONITOR STATS",
                        "Accelerator 0 total cycles: 63",
                        "Off-chip memory accesses at mem tile 0: 186",
                        "... PASS",
                    ]
                ),
                encoding="utf-8",
            )
        return Result(command, str(cwd))

    run_baseline_iteration(
        accelerator_name="aesdecipher_v2_rtl",
        soc_root=soc_root,
        esp_config_path=esp_config_path,
        transcript_path=soc_root / "modelsim" / "transcript",
        runs_root=runs_root,
        baselines_root=baselines_root,
        tech_acc_root=tech_root,
        command_runner=fake_runner,
    )

    config_text = esp_config_path.read_text(encoding="utf-8")
    assert "TILE_1_0 = 2 acc AESDECIPHER_V2_RTL basic_dma64 0 0 sld" in config_text


def test_apply_accelerator_target_prefers_implementation_matching_dma_width(tmp_path: Path):
    tech_root = tmp_path / "tech" / "virtex7" / "acc"
    acc_dir = tech_root / "aescipher_rtl"
    (acc_dir / "aescipher_rtl_basic_dma32").mkdir(parents=True, exist_ok=True)
    (acc_dir / "aescipher_rtl_basic_dma64").mkdir(parents=True, exist_ok=True)

    config_text = (
        "CPU_ARCH = ariane\n"
        "CONFIG_DMA_NOC_WIDTH = 64\n"
        "TILE_1_0 = 2 acc AESCIPHER_RTL basic_dma32 0 0 sld\n"
    )

    updated = _apply_accelerator_target(config_text, "aescipher_rtl", tech_root)

    assert "TILE_1_0 = 2 acc AESCIPHER_RTL basic_dma64 0 0 sld" in updated


def test_run_baseline_iteration_keeps_config_on_command_failure(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    baselines_root = tmp_path / "baselines"
    tech_root = tmp_path / "tech" / "virtex7" / "acc"
    original_text = esp_config_path.read_text(encoding="utf-8")

    def failing_runner(command: list[str], cwd: Path):
        raise RuntimeError("sim failed")

    with pytest.raises(RuntimeError, match="sim failed"):
        run_baseline_iteration(
            accelerator_name="aescipher_rtl",
            soc_root=soc_root,
            esp_config_path=esp_config_path,
            transcript_path=soc_root / "modelsim" / "transcript",
            runs_root=runs_root,
            baselines_root=baselines_root,
            tech_acc_root=tech_root,
            command_runner=failing_runner,
        )

    assert esp_config_path.read_text(encoding="utf-8") == original_text
    assert not (baselines_root / "aescipher_rtl").exists()


def test_run_baseline_iteration_reuses_saved_baseline_without_rerunning(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    baselines_root = tmp_path / "baselines"
    tech_root = tmp_path / "tech" / "virtex7" / "acc"
    baseline_dir = baselines_root / "aescipher_rtl"
    baseline_dir.mkdir(parents=True)
    (baseline_dir / "metrics.json").write_text(
        json.dumps(
            {
                "passed": True,
                "accelerator_total_cycles": 101,
                "offchip_memory_accesses": 202,
            }
        ),
        encoding="utf-8",
    )
    (baseline_dir / "summary.json").write_text(
        json.dumps({"mode": "baseline", "accelerator_name": "aescipher_rtl"}),
        encoding="utf-8",
    )

    def failing_runner(command: list[str], cwd: Path):
        raise AssertionError("baseline should have been reused instead of rerun")

    result = run_baseline_iteration(
        accelerator_name="aescipher_rtl",
        soc_root=soc_root,
        esp_config_path=esp_config_path,
        transcript_path=soc_root / "modelsim" / "transcript",
        runs_root=runs_root,
        baselines_root=baselines_root,
        tech_acc_root=tech_root,
        command_runner=failing_runner,
    )

    assert result.metrics == IterationMetrics(
        passed=True,
        accelerator_total_cycles=101,
        offchip_memory_accesses=202,
    )
    assert result.run_dir == baseline_dir
    assert not list(runs_root.glob("run_*"))


def test_load_saved_baseline_returns_none_when_missing(tmp_path: Path):
    soc_root, esp_config_path, _runs_root = _write_fixture_soc(tmp_path)
    baselines_root = tmp_path / "baselines"

    result = load_saved_baseline(
        accelerator_name="aescipher_rtl",
        baselines_root=baselines_root,
        soc_root=soc_root,
        esp_config_path=esp_config_path,
        transcript_path=soc_root / "modelsim" / "transcript",
    )

    assert result is None


def test_run_candidate_iteration_uses_unique_run_dir_when_same_second_repeats(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    transcript_path = soc_root / "modelsim" / "transcript"
    tech_acc_root = tmp_path / "tech" / "virtex7" / "acc"

    class StubPolicy:
        def request_proposal(self, **kwargs):
            return LLMProposal(
                changes={"CONFIG_QUEUE_SIZE": 8},
                rationale="test repeated timestamp directories",
                search_intent="ensure run dir naming is collision-safe",
            )

    class Result:
        def __init__(self, command: list[str], cwd: str) -> None:
            self.command = command
            self.cwd = cwd
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_runner(command: list[str], cwd: Path):
        if command[0:2] == ["make", "sim"]:
            transcript_path.write_text(
                "\n".join(
                    [
                        "ESP MONITOR STATS",
                        "Accelerator 0 total cycles: 63",
                        "Off-chip memory accesses at mem tile 0: 186",
                        "... PASS",
                    ]
                ),
                encoding="utf-8",
            )
        return Result(command, str(cwd))

    monkeypatch.setattr(run_once_module, "_timestamp", lambda: "20260407_120000")

    first = run_candidate_iteration(
        accelerator_name="aescipher_rtl",
        llm_policy=StubPolicy(),  # type: ignore[arg-type]
        llm_config={"model": "gemini-3-pro-preview"},
        search_space={"allowed_keys": ["CONFIG_QUEUE_SIZE"]},
        scoring_config={},
        soc_root=soc_root,
        esp_config_path=esp_config_path,
        transcript_path=transcript_path,
        runs_root=runs_root,
        tech_acc_root=tech_acc_root,
        command_runner=fake_runner,
    )
    second = run_candidate_iteration(
        accelerator_name="aescipher_rtl",
        llm_policy=StubPolicy(),  # type: ignore[arg-type]
        llm_config={"model": "gemini-3-pro-preview"},
        search_space={"allowed_keys": ["CONFIG_QUEUE_SIZE"]},
        scoring_config={},
        soc_root=soc_root,
        esp_config_path=esp_config_path,
        transcript_path=transcript_path,
        runs_root=runs_root,
        tech_acc_root=tech_acc_root,
        command_runner=fake_runner,
    )

    assert first.run_dir.name == "run_20260407_120000_aescipher_rtl"
    assert second.run_dir.name == "run_20260407_120000_aescipher_rtl_1"


def test_run_candidate_iteration_does_not_create_run_dir_when_proposal_request_fails(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    transcript_path = soc_root / "modelsim" / "transcript"
    tech_acc_root = tmp_path / "tech" / "virtex7" / "acc"

    class FailingPolicy:
        def request_proposal(self, **kwargs):
            raise TimeoutError("The read operation timed out")

    with pytest.raises(TimeoutError, match="The read operation timed out"):
        run_candidate_iteration(
            accelerator_name="aescipher_rtl",
            llm_policy=FailingPolicy(),  # type: ignore[arg-type]
            llm_config={"model": "gemini-3-pro-preview"},
            search_space={"allowed_keys": ["CONFIG_QUEUE_SIZE"]},
            scoring_config={},
            soc_root=soc_root,
            esp_config_path=esp_config_path,
            transcript_path=transcript_path,
            runs_root=runs_root,
            tech_acc_root=tech_acc_root,
        )

    assert not list(runs_root.glob("run_*"))


def test_run_candidate_iteration_restores_previous_runnable_generated_state_on_failure(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    transcript_path = soc_root / "modelsim" / "transcript"
    derived_state_path = soc_root / "socgen" / "esp" / "esp_global.vhd"
    derived_state_path.write_text("DMA_NOC_WIDTH=64\n", encoding="utf-8")

    class StubPolicy:
        def request_proposal(self, **kwargs):
            return LLMProposal(
                changes={"CONFIG_QUEUE_SIZE": 8},
                rationale="test compatible queue size change",
                search_intent="force a later-stage failure after esp-config succeeds",
            )

    seen_commands: list[list[str]] = []

    class Result:
        def __init__(self, command: list[str], cwd: str) -> None:
            self.command = command
            self.cwd = cwd
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_runner(command: list[str], cwd: Path):
        seen_commands.append(command)
        if command == ["make", "esp-config"]:
            current_text = esp_config_path.read_text(encoding="utf-8")
            if "CONFIG_QUEUE_SIZE = 8" in current_text:
                derived_state_path.write_text("QUEUE_SIZE=8\n", encoding="utf-8")
            else:
                derived_state_path.write_text("QUEUE_SIZE=4\n", encoding="utf-8")
            return Result(command, str(cwd))
        if command[0:2] == ["make", "aescipher_rtl-baremetal"]:
            return Result(command, str(cwd))
        raise RuntimeError("sim compile failed")

    with pytest.raises(CandidateIterationError, match="candidate execution failed; restored previous runnable state"):
        run_candidate_iteration(
            accelerator_name="aescipher_rtl",
            llm_policy=StubPolicy(),  # type: ignore[arg-type]
            llm_config={"model": "gemini-3-pro-preview"},
            search_space={"allowed_keys": ["CONFIG_QUEUE_SIZE"]},
            scoring_config={},
            soc_root=soc_root,
            esp_config_path=esp_config_path,
            transcript_path=transcript_path,
            runs_root=runs_root,
            tech_acc_root=tmp_path / "tech" / "virtex7" / "acc",
            command_runner=fake_runner,
        )

    assert esp_config_path.read_text(encoding="utf-8") == (
        "CPU_ARCH = ariane\n"
        "TILE_1_0 = 2 acc AESCIPHER_RTL basic_dma64 0 0 sld\n"
        "CONFIG_QUEUE_SIZE = 4\n"
        "CONFIG_DMA_NOC_WIDTH = 64\n"
    )
    assert derived_state_path.read_text(encoding="utf-8") == "QUEUE_SIZE=4\n"
    assert seen_commands == [
        ["make", "esp-config"],
        ["make", "aescipher_rtl-baremetal"],
        ["make", "sim", f"TEST_PROGRAM={soc_root / 'soft-build' / 'ariane' / 'baremetal' / 'aescipher_rtl.exe'}"],
        ["make", "esp-config"],
    ]


def test_run_candidate_iteration_rejects_incompatible_dma_width_before_execution(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    transcript_path = soc_root / "modelsim" / "transcript"
    llm_context: dict[str, object] = {}

    class StubPolicy:
        def request_proposal(self, **kwargs):
            llm_context.update(kwargs["context"])
            return LLMProposal(
                changes={
                    "CONFIG_DMA_NOC_WIDTH": 128,
                    "CONFIG_MEM_LINK_WIDTH": 128,
                },
                rationale="try unsupported wide dma path",
                search_intent="stress bandwidth",
            )

    def failing_runner(command: list[str], cwd: Path):
        raise AssertionError("No build command should run for an incompatible proposal")

    with pytest.raises(CandidateIterationError, match="supported widths: \\[64\\]"):
        run_candidate_iteration(
            accelerator_name="aescipher_rtl",
            llm_policy=StubPolicy(),  # type: ignore[arg-type]
            llm_config={"model": "gemini-3-pro-preview"},
            search_space={"allowed_keys": ["CONFIG_DMA_NOC_WIDTH", "CONFIG_MEM_LINK_WIDTH"]},
            scoring_config={},
            soc_root=soc_root,
            esp_config_path=esp_config_path,
            transcript_path=transcript_path,
            runs_root=runs_root,
            tech_acc_root=tmp_path / "tech" / "virtex7" / "acc",
            command_runner=failing_runner,
        )

    assert llm_context["compatibility"] == {
        "supported_dma_noc_widths": [64],
        "supported_mem_link_widths": [64],
    }
    assert "CONFIG_DMA_NOC_WIDTH = 64" in esp_config_path.read_text(encoding="utf-8")
    run_dir = next(runs_root.glob("run_*_aescipher_rtl"))
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "failed"
    assert "supported widths: [64]" in summary["failure_reason"]


def test_run_candidate_iteration_passes_monitor_history_context_to_llm(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    transcript_path = soc_root / "modelsim" / "transcript"
    tech_acc_root = tmp_path / "tech" / "virtex7" / "acc"
    captured_context: dict[str, object] = {}

    class StubPolicy:
        def request_proposal(self, **kwargs):
            captured_context.update(kwargs["context"])
            return LLMProposal(
                changes={"CONFIG_QUEUE_SIZE": 8},
                rationale="test monitor-aware context",
                search_intent="verify llm sees baseline best and recent attempts",
            )

    class Result:
        def __init__(self, command: list[str], cwd: str) -> None:
            self.command = command
            self.cwd = cwd
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_runner(command: list[str], cwd: Path):
        if command[0:2] == ["make", "sim"]:
            transcript_path.write_text(
                "\n".join(
                    [
                        "ESP MONITOR STATS",
                        "Accelerator 0 TLB-loading cycles: 21",
                        "Accelerator 0 mem cycles: 34",
                        "Accelerator 0 total cycles: 63",
                        "Accelerator 0 invocations: 1",
                        "Off-chip memory accesses at mem tile 0: 186",
                        "... PASS",
                    ]
                ),
                encoding="utf-8",
            )
        return Result(command, str(cwd))

    baseline_metrics = IterationMetrics(
        passed=True,
        accelerator_total_cycles=63,
        offchip_memory_accesses=184,
        accelerator_tlb_loading_cycles=21,
        accelerator_mem_cycles=34,
        accelerator_invocations=1,
        resource_score=25.0,
    )
    best_metrics = IterationMetrics(
        passed=True,
        accelerator_total_cycles=60,
        offchip_memory_accesses=180,
        accelerator_tlb_loading_cycles=20,
        accelerator_mem_cycles=31,
        accelerator_invocations=1,
        resource_score=22.0,
    )
    last_metrics = IterationMetrics(
        passed=True,
        accelerator_total_cycles=61,
        offchip_memory_accesses=182,
        accelerator_tlb_loading_cycles=20,
        accelerator_mem_cycles=32,
        accelerator_invocations=1,
        resource_score=23.0,
    )

    run_candidate_iteration(
        accelerator_name="aescipher_rtl",
        llm_policy=StubPolicy(),  # type: ignore[arg-type]
        llm_config={"model": "gemini-3-flash-preview"},
        search_space={"allowed_keys": ["CONFIG_QUEUE_SIZE"]},
        scoring_config={"minimum_improvement": 0.02},
        baseline_metrics=baseline_metrics,
        best_metrics=best_metrics,
        last_metrics=last_metrics,
        recent_attempts=[
            {
                "status": "passed",
                "proposal": {"changes": {"CONFIG_QUEUE_SIZE": 16}},
                "metrics": {"accelerator_total_cycles": 61},
                "improvement_vs_baseline": 0.031746,
            }
        ],
        soc_root=soc_root,
        esp_config_path=esp_config_path,
        transcript_path=transcript_path,
        runs_root=runs_root,
        tech_acc_root=tech_acc_root,
        command_runner=fake_runner,
    )

    assert captured_context["baseline_metrics"] == baseline_metrics.model_dump(mode="json", exclude_none=True)
    assert captured_context["best_metrics"] == best_metrics.model_dump(mode="json", exclude_none=True)
    assert captured_context["last_metrics"] == last_metrics.model_dump(mode="json", exclude_none=True)
    assert captured_context["recent_attempts"] == [
        {
            "status": "passed",
            "proposal": {"changes": {"CONFIG_QUEUE_SIZE": 16}},
            "metrics": {"accelerator_total_cycles": 61},
            "improvement_vs_baseline": 0.031746,
        }
    ]
    assert captured_context["last_improvement_vs_best"] == pytest.approx((60 - 61) / 60)
    assert captured_context["last_improvement_vs_baseline"] == pytest.approx((63 - 61) / 63)
    assert captured_context["last_resource_improvement_vs_best"] == pytest.approx((22.0 - 23.0) / 22.0)
    assert captured_context["last_resource_improvement_vs_baseline"] == pytest.approx((25.0 - 23.0) / 25.0)


def test_run_candidate_iteration_raises_structured_error_for_failed_execution(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    transcript_path = soc_root / "modelsim" / "transcript"
    tech_acc_root = tmp_path / "tech" / "virtex7" / "acc"

    class StubPolicy:
        def request_proposal(self, **kwargs):
            return LLMProposal(
                changes={"CONFIG_QUEUE_SIZE": 8},
                rationale="test failure propagation",
                search_intent="verify structured candidate errors",
            )

    def failing_runner(command: list[str], cwd: Path):
        raise RuntimeError("sim failed")

    with pytest.raises(CandidateIterationError, match="candidate execution failed; restored previous runnable state") as exc_info:
        run_candidate_iteration(
            accelerator_name="aescipher_rtl",
            llm_policy=StubPolicy(),  # type: ignore[arg-type]
            llm_config={"model": "gemini-3-flash-preview"},
            search_space={"allowed_keys": ["CONFIG_QUEUE_SIZE"]},
            scoring_config={},
            soc_root=soc_root,
            esp_config_path=esp_config_path,
            transcript_path=transcript_path,
            runs_root=runs_root,
            tech_acc_root=tech_acc_root,
            command_runner=failing_runner,
        )

    assert exc_info.value.proposal is not None
    assert exc_info.value.run_dir is not None


def test_run_candidate_iteration_switches_tile_accelerator_to_target(tmp_path: Path):
    soc_root, esp_config_path, runs_root = _write_fixture_soc(tmp_path)
    transcript_path = soc_root / "modelsim" / "transcript"
    tech_root = tmp_path / "tech" / "virtex7" / "acc"
    (tech_root / "aesdecipher_v2_rtl" / "aesdecipher_v2_rtl_basic_dma64").mkdir(parents=True, exist_ok=True)
    esp_config_path.write_text(
        "CPU_ARCH = ariane\n"
        "TILE_1_0 = 2 acc AESCIPHER_RTL basic_dma64 0 0 sld\n"
        "CONFIG_QUEUE_SIZE = 4\n",
        encoding="utf-8",
    )

    class StubPolicy:
        def request_proposal(self, **kwargs):
            return LLMProposal(
                changes={"CONFIG_QUEUE_SIZE": 8},
                rationale="switch accelerator target",
                search_intent="verify accelerator tile follows campaign target",
            )

    class Result:
        def __init__(self, command: list[str], cwd: str) -> None:
            self.command = command
            self.cwd = cwd
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    def fake_runner(command: list[str], cwd: Path):
        if command[0:2] == ["make", "sim"]:
            transcript_path.write_text(
                "\n".join(
                    [
                        "ESP MONITOR STATS",
                        "Accelerator 0 total cycles: 63",
                        "Off-chip memory accesses at mem tile 0: 186",
                        "... PASS",
                    ]
                ),
                encoding="utf-8",
            )
        return Result(command, str(cwd))

    run_candidate_iteration(
        accelerator_name="aesdecipher_v2_rtl",
        llm_policy=StubPolicy(),  # type: ignore[arg-type]
        llm_config={"model": "gemini-3-flash-preview"},
        search_space={"allowed_keys": ["CONFIG_QUEUE_SIZE"]},
        scoring_config={},
        soc_root=soc_root,
        esp_config_path=esp_config_path,
        transcript_path=transcript_path,
        runs_root=runs_root,
        tech_acc_root=tech_root,
        command_runner=fake_runner,
    )

    config_text = esp_config_path.read_text(encoding="utf-8")
    assert "TILE_1_0 = 2 acc AESDECIPHER_V2_RTL basic_dma64 0 0 sld" in config_text
