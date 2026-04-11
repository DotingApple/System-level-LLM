from types import SimpleNamespace
from pathlib import Path

import pytest

from soc_opt_agent.models import IterationMetrics
from soc_opt_agent.discovery.accelerators import discover_accelerators
from soc_opt_agent.paths import get_default_benchmark_exe
from soc_opt_agent.orchestrator.campaign_loop import build_campaign_queue, load_yaml_file, prepare_iteration
from soc_opt_agent.orchestrator.campaign_loop import select_next_accelerator
from soc_opt_agent.cli import main
from soc_opt_agent.orchestrator.state import CampaignState


def test_discover_accelerators_skips_common_and_sorts(tmp_path: Path):
    for name in ["lstm_rtl", "common", "aescipher_rtl"]:
        (tmp_path / name).mkdir()

    names = [item.name for item in discover_accelerators(tmp_path)]
    assert names == ["aescipher_rtl", "lstm_rtl"]


def test_discover_accelerators_ignores_hidden_directories(tmp_path: Path):
    for name in ["aescipher_rtl", ".git", ".cache"]:
        (tmp_path / name).mkdir()

    names = [item.name for item in discover_accelerators(tmp_path)]
    assert names == ["aescipher_rtl"]


def test_first_benchmark_path_matches_ariane_baremetal_layout(tmp_path: Path):
    (tmp_path / "aescipher_rtl").mkdir()
    target = discover_accelerators(tmp_path, soc_dir=Path("/soc"))[0]

    assert target.benchmark_exe == "/soc/soft-build/ariane/baremetal/aescipher_rtl.exe"


def test_default_benchmark_exe_helper_uses_explicit_soc_root():
    assert get_default_benchmark_exe("aescipher_rtl", Path("/soc")) == Path(
        "/soc/soft-build/ariane/baremetal/aescipher_rtl.exe"
    )


def test_select_next_accelerator_starts_with_aescipher_rtl():
    state = CampaignState(completed_accelerators=[])
    queue = ["aescipher_rtl", "aesdecipher_v2_rtl", "lstm_rtl"]

    assert select_next_accelerator(queue, state) == "aescipher_rtl"


def test_load_yaml_file_rejects_missing_and_non_mapping_content(tmp_path: Path):
    missing = tmp_path / "missing.yaml"
    scalar = tmp_path / "scalar.yaml"
    scalar.write_text("- aescipher_rtl\n- lstm_rtl\n")

    with pytest.raises(FileNotFoundError):
        load_yaml_file(missing)

    with pytest.raises(ValueError, match="mapping"):
        load_yaml_file(scalar)


def test_build_campaign_queue_honors_preferred_order_plus_discovered_remainder(monkeypatch):
    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_loop.discover_accelerators",
        lambda root, soc_dir=None: [
            SimpleNamespace(name="lstm_rtl"),
            SimpleNamespace(name="aescipher_rtl"),
            SimpleNamespace(name="aesdecipher_v2_rtl"),
        ],
    )

    queue = build_campaign_queue({"accelerator_order": ["aescipher_rtl", "missing", "lstm_rtl"]})

    assert queue == ["aescipher_rtl", "lstm_rtl", "aesdecipher_v2_rtl"]


def test_select_next_accelerator_skips_completed_and_returns_none_when_exhausted():
    state = CampaignState(completed_accelerators=["aescipher_rtl", "aesdecipher_v2_rtl"])
    queue = ["aescipher_rtl", "aesdecipher_v2_rtl"]

    assert select_next_accelerator(queue, state) is None


def test_cli_surfaces_loaded_scoring_and_llm_configs(tmp_path: Path, monkeypatch, capsys):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements:\n  - 0.05\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text(
        "accelerator_order:\n"
        "  - aescipher_rtl\n"
        "soc_root: /soc\n"
        "accelerators_root: /accelerators\n"
    )
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 3\nminimum_improvement: 0.05\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text(
        "model: gemini-2.5-flash\n"
        "temperature: 0.1\n"
        "response_format: structured_json\n"
        "api_key_env: GEMINI_API_KEY\n"
    )

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_loop.discover_accelerators",
        lambda root, soc_dir=None: [SimpleNamespace(name="aescipher_rtl")],
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
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Next accelerator: aescipher_rtl" in captured
    assert "Scoring config: minimum_improvement=0.05, plateau_window=3" in captured
    assert (
        "LLM config: api_key_env=GEMINI_API_KEY, model=gemini-2.5-flash, "
        "response_format=structured_json, temperature=0.1" in captured
    )


def test_prepare_iteration_stops_when_plateau_config_is_triggered(tmp_path: Path, monkeypatch):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text(
        "completed_accelerators: []\n"
        "recent_improvements:\n"
        "  - 0.01\n"
        "  - 0.015\n"
        "  - 0.0\n"
        "  - 0.019\n"
        "  - 0.005\n"
        "stop_after_plateau: true\n"
    )
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text("accelerator_order:\n  - aescipher_rtl\n")
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 5\nminimum_improvement: 0.02\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-2.5-flash\ntemperature: 0.1\n")

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_loop.discover_accelerators",
        lambda root, soc_dir=None: [SimpleNamespace(name="aescipher_rtl")],
    )

    iteration = prepare_iteration(campaign, search_space, scoring, llm)

    assert iteration.accelerator_name is None


def test_cli_baseline_uses_baseline_runner(tmp_path: Path, monkeypatch, capsys):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text("accelerator_order:\n  - aescipher_rtl\n")
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 5\nminimum_improvement: 0.02\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-2.5-flash\ntemperature: 0.1\n")

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_loop.discover_accelerators",
        lambda root, soc_dir=None: [SimpleNamespace(name="aescipher_rtl")],
    )

    def fake_run_baseline_iteration(*, accelerator_name):
        return SimpleNamespace(
            accelerator_name=accelerator_name,
            mode="baseline",
            proposal=None,
            metrics=IterationMetrics(
                passed=True,
                accelerator_total_cycles=63,
                offchip_memory_accesses=186,
            ),
            run_dir=Path("/tmp/run"),
        )

    monkeypatch.setattr("soc_opt_agent.cli.run_baseline_iteration", fake_run_baseline_iteration)

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
            "baseline",
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Ran baseline accelerator: aescipher_rtl" in captured
    assert "Accelerator total cycles: 63" in captured


def test_cli_run_once_uses_candidate_runner(tmp_path: Path, monkeypatch, capsys):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text("accelerator_order:\n  - aescipher_rtl\nallowed_keys:\n  - CONFIG_QUEUE_SIZE\n")
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 5\nminimum_improvement: 0.02\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-2.5-flash\ntemperature: 0.1\n")

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_loop.discover_accelerators",
        lambda root, soc_dir=None: [SimpleNamespace(name="aescipher_rtl")],
    )

    def fake_run_candidate_iteration(*, accelerator_name, llm_policy, llm_config, search_space, scoring_config):
        assert accelerator_name == "aescipher_rtl"
        assert llm_config["model"] == "gemini-2.5-flash"
        assert search_space["allowed_keys"] == ["CONFIG_QUEUE_SIZE"]
        assert scoring_config["plateau_window"] == 5
        assert llm_policy is not None
        return SimpleNamespace(
            accelerator_name=accelerator_name,
            mode="candidate",
            proposal={"changes": {"CONFIG_QUEUE_SIZE": 8}},
            metrics=IterationMetrics(
                passed=True,
                accelerator_total_cycles=61,
                offchip_memory_accesses=180,
            ),
            run_dir=Path("/tmp/run"),
        )

    monkeypatch.setattr("soc_opt_agent.cli.run_candidate_iteration", fake_run_candidate_iteration)

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
            "run_once",
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Ran candidate accelerator: aescipher_rtl" in captured
    assert "Accelerator total cycles: 61" in captured


def test_cli_status_command_matches_default_output(tmp_path: Path, monkeypatch, capsys):
    campaign = tmp_path / "campaign.yaml"
    campaign.write_text("completed_accelerators: []\nrecent_improvements: []\n")
    search_space = tmp_path / "search_space.yaml"
    search_space.write_text("accelerator_order:\n  - aescipher_rtl\n")
    scoring = tmp_path / "scoring.yaml"
    scoring.write_text("plateau_window: 5\nminimum_improvement: 0.02\n")
    llm = tmp_path / "llm.yaml"
    llm.write_text("model: gemini-2.5-flash\ntemperature: 0.1\n")

    monkeypatch.setattr(
        "soc_opt_agent.orchestrator.campaign_loop.discover_accelerators",
        lambda root, soc_dir=None: [SimpleNamespace(name="aescipher_rtl")],
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
            "status",
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Next accelerator: aescipher_rtl" in captured
