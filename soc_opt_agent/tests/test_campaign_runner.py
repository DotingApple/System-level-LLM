from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from soc_opt_agent.cli import main


def test_run_all_runs_baseline_then_candidates_until_plateau(tmp_path: Path, monkeypatch):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text("accelerator_order:\n  - aescipher_rtl\nallowed_keys:\n  - CONFIG_QUEUE_SIZE\n")
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 2\nminimum_improvement: 0.05\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-2.5-flash\ntemperature: 0.1\n")

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.PID_PATH",
        tmp_path / "run_all.pid",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.STOP_PATH",
        tmp_path / "run_all.stop",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.STATUS_PATH",
        tmp_path / "run_all.status.json",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.TRANSCRIPT_PATH",
        tmp_path / "agent_transcript.log",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.get_default_bests_root",
        lambda: tmp_path / "bests",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_campaign_queue",
        lambda search_space: ["aescipher_rtl"],
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_policy_from_config",
        lambda llm_config: object(),
    )

    baseline_run_dir = tmp_path / "baseline_run"
    baseline_run_dir.mkdir()
    (baseline_run_dir / "summary.json").write_text(
        json.dumps({"mode": "baseline", "cycles": 100}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_baseline_iteration",
        lambda accelerator_name: SimpleNamespace(
            metrics=SimpleNamespace(accelerator_total_cycles=100, resource_score=25.0),
            run_dir=baseline_run_dir,
        ),
    )

    cycle_values = iter([90, 89, 88])
    candidate_index = {"value": 0}

    def fake_candidate_iteration(**kwargs):
        candidate_index["value"] += 1
        cycle = next(cycle_values)
        candidate_run_dir = tmp_path / f"candidate_{candidate_index['value']}"
        candidate_run_dir.mkdir()
        (candidate_run_dir / "summary.json").write_text(
            json.dumps({"mode": "candidate", "cycles": cycle}),
            encoding="utf-8",
        )
        (candidate_run_dir / "config_after.esp_config").write_text(
            f"CONFIG_QUEUE_SIZE = {candidate_index['value']}\n",
            encoding="utf-8",
        )
        return SimpleNamespace(
            metrics=SimpleNamespace(
                passed=True,
                accelerator_total_cycles=cycle,
                resource_score=24.0 - candidate_index["value"],
            ),
            proposal=None,
            run_dir=candidate_run_dir,
        )

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_candidate_iteration",
        fake_candidate_iteration,
    )

    exit_code = main(
        [
            "--campaign-config",
            str(campaign),
            "--search-space-config",
            str(search_space),
            "--scoring-config",
            str(scoring),
            "--llm-config",
            str(llm),
            "--run-all",
        ]
    )

    assert exit_code == 0
    updated_campaign = campaign.read_text(encoding="utf-8")
    assert "aescipher_rtl" in updated_campaign
    status = json.loads((tmp_path / "run_all.status.json").read_text(encoding="utf-8"))
    assert status["best_cycles"] == 88
    assert status["baseline_resource_score"] == 25.0
    assert status["best_resource_score"] == 21.0
    assert status["last_resource_score"] == 21.0
    assert status["best_run_dir"] == str(tmp_path / "bests" / "aescipher_rtl")
    assert len(status["recent_improvements"]) == 3
    best_summary = json.loads(((tmp_path / "bests" / "aescipher_rtl") / "summary.json").read_text(encoding="utf-8"))
    assert best_summary["cycles"] == 88
    transcript_text = (tmp_path / "agent_transcript.log").read_text(encoding="utf-8")
    assert "RUN-ALL start accelerator=aescipher_rtl" in transcript_text
    assert "RUN-ALL complete accelerator=aescipher_rtl" in transcript_text


def test_run_all_persists_all_pareto_optimal_points(tmp_path: Path, monkeypatch):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text("accelerator_order:\n  - aescipher_rtl\nallowed_keys:\n  - CONFIG_QUEUE_SIZE\n")
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 10\nminimum_improvement: 0.05\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-2.5-flash\ntemperature: 0.1\n")

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.PID_PATH",
        tmp_path / "run_all.pid",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.STOP_PATH",
        tmp_path / "run_all.stop",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.STATUS_PATH",
        tmp_path / "run_all.status.json",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.TRANSCRIPT_PATH",
        tmp_path / "agent_transcript.log",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.get_default_bests_root",
        lambda: tmp_path / "bests",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_campaign_queue",
        lambda search_space: ["aescipher_rtl"],
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_policy_from_config",
        lambda llm_config: object(),
    )

    baseline_run_dir = tmp_path / "baseline_run"
    baseline_run_dir.mkdir()
    (baseline_run_dir / "summary.json").write_text(
        json.dumps({"mode": "baseline", "cycles": 100}),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_baseline_iteration",
        lambda accelerator_name: SimpleNamespace(
            metrics=SimpleNamespace(accelerator_total_cycles=100, resource_score=30.0),
            run_dir=baseline_run_dir,
        ),
    )

    candidate_results = [
        (90, 40.0, "candidate_tradeoff_fast"),
        (95, 20.0, "candidate_tradeoff_small"),
        (110, 50.0, "candidate_dominated"),
    ]
    call_count = {"value": 0}

    def fake_candidate_iteration(**kwargs):
        cycle, resource_score, run_name = candidate_results[call_count["value"]]
        call_count["value"] += 1
        candidate_run_dir = tmp_path / run_name
        candidate_run_dir.mkdir()
        (candidate_run_dir / "summary.json").write_text(
            json.dumps({"mode": "candidate", "cycles": cycle}),
            encoding="utf-8",
        )
        if call_count["value"] == len(candidate_results):
            (tmp_path / "run_all.stop").write_text("stop\n", encoding="utf-8")
        return SimpleNamespace(
            metrics=SimpleNamespace(
                passed=True,
                accelerator_total_cycles=cycle,
                resource_score=resource_score,
            ),
            proposal=None,
            run_dir=candidate_run_dir,
        )

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_candidate_iteration",
        fake_candidate_iteration,
    )

    exit_code = main(
        [
            "--campaign-config",
            str(campaign),
            "--search-space-config",
            str(search_space),
            "--scoring-config",
            str(scoring),
            "--llm-config",
            str(llm),
            "--run-all",
        ]
    )

    assert exit_code == 0
    status = json.loads((tmp_path / "run_all.status.json").read_text(encoding="utf-8"))
    assert status["iteration"] == 3
    assert status["pareto_front_size"] == 2
    assert {(entry["cycles"], entry["resource_score"]) for entry in status["pareto_front"]} == {
        (90, 40.0),
        (95, 20.0),
    }
    assert status["pareto_front_dir"] == str(tmp_path / "bests" / "aescipher_rtl" / "pareto")
    pareto_root = tmp_path / "bests" / "aescipher_rtl" / "pareto"
    assert (pareto_root / "candidate_tradeoff_fast" / "summary.json").exists()
    assert (pareto_root / "candidate_tradeoff_small" / "summary.json").exists()
    assert not (pareto_root / "candidate_dominated").exists()


def test_run_all_prints_stop_reason_for_plateau_and_continues_to_next_accelerator(tmp_path: Path, monkeypatch, capsys):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\nstop_after_plateau: true\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text(
        "accelerator_order:\n"
        "  - aescipher_rtl\n"
        "  - aesdecipher_v2_rtl\n"
        "allowed_keys:\n"
        "  - CONFIG_QUEUE_SIZE\n"
    )
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 2\nminimum_improvement: 0.05\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-3-flash-preview\ntemperature: 0.1\n")

    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.PID_PATH", tmp_path / "run_all.pid")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STOP_PATH", tmp_path / "run_all.stop")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STATUS_PATH", tmp_path / "run_all.status.json")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.TRANSCRIPT_PATH", tmp_path / "agent_transcript.log")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.get_default_bests_root",
        lambda: tmp_path / "bests",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_campaign_queue",
        lambda search_space: ["aescipher_rtl", "aesdecipher_v2_rtl"],
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_policy_from_config",
        lambda llm_config: object(),
    )

    def fake_baseline(accelerator_name):
        run_dir = tmp_path / f"{accelerator_name}_baseline"
        run_dir.mkdir(exist_ok=True)
        (run_dir / "summary.json").write_text(json.dumps({"mode": "baseline"}), encoding="utf-8")
        return SimpleNamespace(metrics=SimpleNamespace(accelerator_total_cycles=100), run_dir=run_dir)

    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.run_baseline_iteration", fake_baseline)

    call_log: list[str] = []

    def fake_candidate_iteration(**kwargs):
        accelerator_name = kwargs["accelerator_name"]
        call_log.append(accelerator_name)
        run_dir = tmp_path / f"{accelerator_name}_{len(call_log)}"
        run_dir.mkdir(exist_ok=True)
        (run_dir / "summary.json").write_text(json.dumps({"mode": "candidate"}), encoding="utf-8")
        return SimpleNamespace(
            metrics=SimpleNamespace(passed=True, accelerator_total_cycles=100),
            proposal=None,
            run_dir=run_dir,
        )

    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.run_candidate_iteration", fake_candidate_iteration)

    exit_code = main(
        [
            "--campaign-config",
            str(campaign),
            "--search-space-config",
            str(search_space),
            "--scoring-config",
            str(scoring),
            "--llm-config",
            str(llm),
            "run_all",
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Stopped accelerator aescipher_rtl: plateau detected after 2 consecutive non-improving iterations." in captured
    assert "Next accelerator: aesdecipher_v2_rtl" in captured
    assert call_log == ["aescipher_rtl", "aescipher_rtl", "aesdecipher_v2_rtl", "aesdecipher_v2_rtl"]


def test_cli_stop_requests_active_run_all(tmp_path: Path, monkeypatch, capsys):
    pid_path = tmp_path / "run_all.pid"
    stop_path = tmp_path / "run_all.stop"
    pid_path.write_text("123\n", encoding="utf-8")
    killed: list[int] = []

    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.PID_PATH", pid_path)
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STOP_PATH", stop_path)
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner._list_descendants", lambda pid: [456, 789])
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner._pid_is_running", lambda pid: True)
    monkeypatch.setattr("os.kill", lambda pid, sig: killed.append(pid))

    exit_code = main(["stop"])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Stop requested for active run-all loop. Sent termination to current run-all process tree." in captured
    assert stop_path.exists()
    assert killed == [456, 789, 123]


def test_run_all_cleans_stale_pid_file_before_start(tmp_path: Path, monkeypatch):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text("accelerator_order:\n  - aescipher_rtl\nallowed_keys:\n  - CONFIG_QUEUE_SIZE\n")
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 1\nminimum_improvement: 0.05\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-3-pro-preview\ntemperature: 0.1\n")

    pid_path = tmp_path / "run_all.pid"
    pid_path.write_text("999999\n", encoding="utf-8")

    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.PID_PATH", pid_path)
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STOP_PATH", tmp_path / "run_all.stop")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STATUS_PATH", tmp_path / "run_all.status.json")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.TRANSCRIPT_PATH", tmp_path / "agent_transcript.log")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.get_default_bests_root",
        lambda: tmp_path / "bests",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_campaign_queue",
        lambda search_space: ["aescipher_rtl"],
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_policy_from_config",
        lambda llm_config: object(),
    )
    baseline_run_dir = tmp_path / "baseline_run"
    baseline_run_dir.mkdir()
    (baseline_run_dir / "summary.json").write_text(json.dumps({"mode": "baseline"}), encoding="utf-8")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_baseline_iteration",
        lambda accelerator_name: SimpleNamespace(
            metrics=SimpleNamespace(accelerator_total_cycles=100),
            run_dir=baseline_run_dir,
        ),
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_candidate_iteration",
        lambda **kwargs: SimpleNamespace(
            metrics=SimpleNamespace(passed=True, accelerator_total_cycles=100),
            proposal=None,
            run_dir=baseline_run_dir,
        ),
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner._pid_is_running",
        lambda pid: False,
    )

    exit_code = main(
        [
            "--campaign-config",
            str(campaign),
            "--search-space-config",
            str(search_space),
            "--scoring-config",
            str(scoring),
            "--llm-config",
            str(llm),
            "run_all",
        ]
    )

    assert exit_code == 0
    assert not pid_path.exists()


def test_run_all_continues_after_candidate_failure_and_passes_failure_reason_to_next_try(tmp_path: Path, monkeypatch):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text("accelerator_order:\n  - aescipher_rtl\nallowed_keys:\n  - CONFIG_QUEUE_SIZE\n")
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 2\nminimum_improvement: 0.05\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-3-pro-preview\ntemperature: 0.1\n")

    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.PID_PATH", tmp_path / "run_all.pid")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STOP_PATH", tmp_path / "run_all.stop")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STATUS_PATH", tmp_path / "run_all.status.json")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.TRANSCRIPT_PATH", tmp_path / "agent_transcript.log")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.get_default_bests_root",
        lambda: tmp_path / "bests",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_campaign_queue",
        lambda search_space: ["aescipher_rtl"],
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_policy_from_config",
        lambda llm_config: object(),
    )

    baseline_run_dir = tmp_path / "baseline_run"
    baseline_run_dir.mkdir()
    (baseline_run_dir / "summary.json").write_text(json.dumps({"mode": "baseline", "cycles": 100}), encoding="utf-8")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_baseline_iteration",
        lambda accelerator_name: SimpleNamespace(
            metrics=SimpleNamespace(accelerator_total_cycles=100),
            run_dir=baseline_run_dir,
        ),
    )

    candidate_contexts: list[str | None] = []
    baseline_contexts: list[int] = []
    recent_attempt_contexts: list[list[dict[str, object]]] = []

    def fake_candidate_iteration(**kwargs):
        candidate_contexts.append(kwargs.get("last_failure_reason"))
        baseline_contexts.append(kwargs["baseline_metrics"].accelerator_total_cycles)
        recent_attempt_contexts.append(list(kwargs.get("recent_attempts", [])))
        if len(candidate_contexts) == 1:
            raise ValueError("unsupported dma width")
        candidate_run_dir = tmp_path / "candidate_success"
        candidate_run_dir.mkdir(exist_ok=True)
        (candidate_run_dir / "summary.json").write_text(
            json.dumps({"mode": "candidate", "cycles": 95}),
            encoding="utf-8",
        )
        return SimpleNamespace(
            metrics=SimpleNamespace(passed=True, accelerator_total_cycles=95),
            proposal=None,
            run_dir=candidate_run_dir,
        )

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_candidate_iteration",
        fake_candidate_iteration,
    )

    exit_code = main(
        [
            "--campaign-config",
            str(campaign),
            "--search-space-config",
            str(search_space),
            "--scoring-config",
            str(scoring),
            "--llm-config",
            str(llm),
            "run_all",
        ]
    )

    assert exit_code == 0
    assert candidate_contexts[0:2] == [None, "unsupported dma width"]
    assert baseline_contexts[0:2] == [100, 100]
    assert recent_attempt_contexts[0] == []
    assert recent_attempt_contexts[1] == []
    status = json.loads((tmp_path / "run_all.status.json").read_text(encoding="utf-8"))
    assert status["best_cycles"] == 95
    assert status["last_failure_reason"] is None


def test_run_all_does_not_count_failures_toward_plateau(tmp_path: Path, monkeypatch):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text("accelerator_order:\n  - aescipher_rtl\nallowed_keys:\n  - CONFIG_QUEUE_SIZE\n")
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 2\nminimum_improvement: 0.05\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-3-pro-preview\ntemperature: 0.1\n")

    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.PID_PATH", tmp_path / "run_all.pid")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STOP_PATH", tmp_path / "run_all.stop")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STATUS_PATH", tmp_path / "run_all.status.json")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.TRANSCRIPT_PATH", tmp_path / "agent_transcript.log")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.get_default_bests_root",
        lambda: tmp_path / "bests",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_campaign_queue",
        lambda search_space: ["aescipher_rtl"],
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_policy_from_config",
        lambda llm_config: object(),
    )

    baseline_run_dir = tmp_path / "baseline_run"
    baseline_run_dir.mkdir()
    (baseline_run_dir / "summary.json").write_text(json.dumps({"mode": "baseline", "cycles": 100}), encoding="utf-8")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_baseline_iteration",
        lambda accelerator_name: SimpleNamespace(
            metrics=SimpleNamespace(accelerator_total_cycles=100),
            run_dir=baseline_run_dir,
        ),
    )

    calls = {"count": 0}

    def fake_candidate_iteration(**kwargs):
        calls["count"] += 1
        if calls["count"] in (1, 2):
            raise ValueError(f"transient failure {calls['count']}")
        candidate_run_dir = tmp_path / f"candidate_{calls['count']}"
        candidate_run_dir.mkdir(exist_ok=True)
        (candidate_run_dir / "summary.json").write_text(
            json.dumps({"mode": "candidate", "cycles": 100}),
            encoding="utf-8",
        )
        if calls["count"] == 4:
            (tmp_path / "run_all.stop").write_text("stop\n", encoding="utf-8")
        return SimpleNamespace(
            metrics=SimpleNamespace(passed=True, accelerator_total_cycles=100),
            proposal=None,
            run_dir=candidate_run_dir,
        )

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_candidate_iteration",
        fake_candidate_iteration,
    )

    exit_code = main(
        [
            "--campaign-config",
            str(campaign),
            "--search-space-config",
            str(search_space),
            "--scoring-config",
            str(scoring),
            "--llm-config",
            str(llm),
            "run_all",
        ]
    )

    assert exit_code == 0
    assert calls["count"] == 4
    updated_campaign = campaign.read_text(encoding="utf-8")
    assert "aescipher_rtl" in updated_campaign
    status = json.loads((tmp_path / "run_all.status.json").read_text(encoding="utf-8"))
    assert status["recent_improvements"] == [0.0, 0.0]
    assert status["iteration"] == 2


def test_run_all_does_not_mark_accelerator_completed_when_candidate_never_starts(tmp_path: Path, monkeypatch):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text("accelerator_order:\n  - aescipher_rtl\nallowed_keys:\n  - CONFIG_QUEUE_SIZE\n")
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 10\nminimum_improvement: 0.05\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-3-flash-preview\ntemperature: 0.1\n")

    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.PID_PATH", tmp_path / "run_all.pid")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STOP_PATH", tmp_path / "run_all.stop")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STATUS_PATH", tmp_path / "run_all.status.json")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.TRANSCRIPT_PATH", tmp_path / "agent_transcript.log")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.get_default_bests_root",
        lambda: tmp_path / "bests",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_campaign_queue",
        lambda search_space: ["aescipher_rtl", "aesdecipher_v2_rtl"],
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_policy_from_config",
        lambda llm_config: object(),
    )

    baseline_run_dir = tmp_path / "baseline_run"
    baseline_run_dir.mkdir()
    (baseline_run_dir / "summary.json").write_text(json.dumps({"mode": "baseline"}), encoding="utf-8")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_baseline_iteration",
        lambda accelerator_name: SimpleNamespace(
            metrics=SimpleNamespace(accelerator_total_cycles=100),
            run_dir=baseline_run_dir,
        ),
    )

    def fake_candidate_iteration(**kwargs):
        (tmp_path / "run_all.stop").write_text("stop\n", encoding="utf-8")
        raise RuntimeError("Missing API key in environment variable GEMINI_API_KEY")

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_candidate_iteration",
        fake_candidate_iteration,
    )

    exit_code = main(
        [
            "--campaign-config",
            str(campaign),
            "--search-space-config",
            str(search_space),
            "--scoring-config",
            str(scoring),
            "--llm-config",
            str(llm),
            "run_all",
        ]
    )

    assert exit_code == 0
    updated_campaign = campaign.read_text(encoding="utf-8")
    assert "completed_accelerators: []" in updated_campaign


def test_run_all_stops_immediately_on_daily_llm_quota_error(tmp_path: Path, monkeypatch, capsys):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text(
        "accelerator_order:\n"
        "  - aescipher_rtl\n"
        "  - aesdecipher_v2_rtl\n"
        "allowed_keys:\n"
        "  - CONFIG_QUEUE_SIZE\n"
    )
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 10\nminimum_improvement: 0.05\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-3-flash-preview\ntemperature: 0.1\n")

    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.PID_PATH", tmp_path / "run_all.pid")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STOP_PATH", tmp_path / "run_all.stop")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.STATUS_PATH", tmp_path / "run_all.status.json")
    monkeypatch.setattr("soc_opt_agent.orchestrator.campaign_runner.TRANSCRIPT_PATH", tmp_path / "agent_transcript.log")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.get_default_bests_root",
        lambda: tmp_path / "bests",
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_campaign_queue",
        lambda search_space: ["aescipher_rtl", "aesdecipher_v2_rtl"],
    )
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.build_policy_from_config",
        lambda llm_config: object(),
    )

    baseline_run_dir = tmp_path / "baseline_run"
    baseline_run_dir.mkdir()
    (baseline_run_dir / "summary.json").write_text(json.dumps({"mode": "baseline", "cycles": 100}), encoding="utf-8")
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_baseline_iteration",
        lambda accelerator_name: SimpleNamespace(
            metrics=SimpleNamespace(accelerator_total_cycles=100),
            run_dir=baseline_run_dir,
        ),
    )

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_runner.run_candidate_iteration",
        lambda **kwargs: (_ for _ in ()).throw(
            RuntimeError(
                "litellm.RateLimitError: RESOURCE_EXHAUSTED quota exceeded "
                "GenerateRequestsPerDayPerProjectPerModel-FreeTier"
            )
        ),
    )

    exit_code = main(
        [
            "--campaign-config",
            str(campaign),
            "--search-space-config",
            str(search_space),
            "--scoring-config",
            str(scoring),
            "--llm-config",
            str(llm),
            "run_all",
        ]
    )

    captured = capsys.readouterr().out
    status = json.loads((tmp_path / "run_all.status.json").read_text(encoding="utf-8"))
    assert exit_code == 0
    assert "daily LLM quota exhausted" in captured
    assert status["phase"] == "stopped-rate-limit"
    assert status["iteration"] == 0
    assert "aescipher_rtl" not in campaign.read_text(encoding="utf-8")
