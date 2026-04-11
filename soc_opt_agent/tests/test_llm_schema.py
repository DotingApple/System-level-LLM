import os

import pytest

from pydantic import ValidationError

from soc_opt_agent.esp_flow.commands import build_esp_config_command, build_sim_command
from soc_opt_agent.llm.client import LLMClient, configure_litellm_runtime
from soc_opt_agent.llm.policy import LLMPolicy, build_policy_from_config
from soc_opt_agent.llm.prompts import (
    load_prompt,
    load_reflect_on_result_prompt,
    load_suggest_config_prompt,
)
from soc_opt_agent.llm.schemas import parse_llm_proposal
from soc_opt_agent.models import AcceleratorTarget, IterationMetrics, LLMProposal
from soc_opt_agent.paths import find_repo_root, get_default_soc_root


def test_llm_proposal_accepts_structured_changes():
    proposal = LLMProposal(
        changes={"CONFIG_QUEUE_SIZE": 8, "CONFIG_DMA_NOC_WIDTH": 128},
        rationale="Increase buffering and bandwidth",
        search_intent="Probe interconnect limits",
    )

    assert proposal.changes["CONFIG_QUEUE_SIZE"] == 8
    assert proposal.search_intent == "Probe interconnect limits"


def test_build_commands_match_esp_flow():
    assert build_esp_config_command() == ["make", "esp-config"]
    assert build_sim_command("/soc/soft-build/ariane/baremetal/aescipher_rtl.exe") == [
        "make",
        "sim",
        "TEST_PROGRAM=/soc/soft-build/ariane/baremetal/aescipher_rtl.exe",
    ]


def test_parse_llm_proposal_validates_required_fields():
    raw = {
        "changes": {"CONFIG_QUEUE_SIZE": 8},
        "rationale": "Increase buffering",
        "search_intent": "Probe network queue sensitivity",
    }
    proposal = parse_llm_proposal(raw)
    assert proposal.changes["CONFIG_QUEUE_SIZE"] == 8


def test_prompt_loader_reads_packaged_templates():
    system_prompt = load_prompt("system.txt")
    assert "structured" in system_prompt.lower()
    assert "reflect on the latest esp run result" in load_prompt("reflect_on_result.txt").lower()
    suggest_prompt = load_suggest_config_prompt()
    assert "changes" in suggest_prompt
    assert "rationale" in suggest_prompt
    assert "search_intent" in suggest_prompt
    assert "Reflect on the latest ESP run result." in load_reflect_on_result_prompt()


def test_build_reflect_on_result_prompt_includes_metric_values():
    metrics = IterationMetrics(
        passed=True,
        accelerator_total_cycles=63,
        offchip_memory_accesses=186,
        accelerator_tlb_loading_cycles=21,
    )

    prompt = LLMPolicy().build_reflect_on_result_prompt(metrics)

    assert "passed: True" in prompt
    assert "Reflect on the latest ESP run result." in prompt
    assert "accelerator_total_cycles: 63" in prompt
    assert "offchip_memory_accesses: 186" in prompt
    assert "accelerator_tlb_loading_cycles: 21" in prompt


def test_load_prompt_rejects_path_traversal():
    with pytest.raises(ValueError, match="PROMPTS_DIR"):
        load_prompt("../secret.txt")


def test_iteration_metrics_tracks_required_fields():
    metrics = IterationMetrics(
        passed=True,
        accelerator_total_cycles=63,
        offchip_memory_accesses=186,
        lut_utilization=43.98,
        ff_utilization=18.89,
        bram_utilization=18.20,
        dsp_utilization=0.96,
        resource_score=20.5075,
    )

    assert metrics.passed is True
    assert metrics.accelerator_total_cycles == 63
    assert metrics.resource_score == 20.5075


def test_iteration_metrics_accepts_overutilized_resource_percentages():
    metrics = IterationMetrics(
        passed=True,
        accelerator_total_cycles=63,
        offchip_memory_accesses=184,
        lut_utilization=158.96,
        ff_utilization=18.37,
        bram_utilization=18.20,
        dsp_utilization=0.96,
        resource_score=(158.96 + 18.37 + 18.20 + 0.96) / 4.0,
    )

    assert metrics.lut_utilization == 158.96


def test_iteration_metrics_rejects_non_bool_passed_value():
    with pytest.raises(ValidationError):
        IterationMetrics(
            passed=1,
            accelerator_total_cycles=63,
            offchip_memory_accesses=186,
        )


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        ("accelerator_total_cycles", {"passed": True, "accelerator_total_cycles": -1, "offchip_memory_accesses": 186}),
        ("offchip_memory_accesses", {"passed": True, "accelerator_total_cycles": 63, "offchip_memory_accesses": -1}),
    ],
)
def test_iteration_metrics_rejects_negative_values(field_name, kwargs):
    with pytest.raises(ValidationError):
        IterationMetrics(**kwargs)


def test_llm_proposal_rejects_bool_change_values():
    with pytest.raises(ValidationError):
        LLMProposal(
            changes={"CONFIG_QUEUE_SIZE": True},
            rationale="Increase buffering",
            search_intent="Probe buffering",
        )


def test_llm_policy_validate_proposal_uses_client_path():
    class StubClient:
        def parse_proposal(self, raw):
            self.raw = raw
            return LLMProposal(
                changes={"CONFIG_QUEUE_SIZE": 8},
                rationale="Increase buffering",
                search_intent="Probe buffering",
            )

    client = StubClient()
    policy = LLMPolicy(client=client)
    raw = {
        "changes": {"CONFIG_QUEUE_SIZE": 8},
        "rationale": "Increase buffering",
        "search_intent": "Probe buffering",
    }

    proposal = policy.validate_proposal(raw)

    assert client.raw == raw
    assert proposal.changes["CONFIG_QUEUE_SIZE"] == 8


def test_llm_client_request_proposal_parses_json_response(monkeypatch):
    client = LLMClient()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    class FakeMessage:
        content = (
            '{"changes":{"CONFIG_QUEUE_SIZE":8},'
            '"rationale":"Increase buffering",'
            '"search_intent":"Probe buffering"}'
        )

    class FakeChoice:
        message = FakeMessage()

    class FakeResponse:
        choices = [FakeChoice()]

    def fake_completion(**kwargs):
        assert kwargs["model"] == "gemini/gemini-2.5-flash"
        assert kwargs["temperature"] == 0.2
        assert kwargs["timeout"] == client.timeout_seconds
        assert kwargs["messages"][0]["role"] == "system"
        assert kwargs["messages"][0]["content"] == "Return JSON."
        assert kwargs["messages"][1]["role"] == "user"
        assert kwargs["messages"][1]["content"] == "Context JSON: {}"
        return FakeResponse()

    monkeypatch.setattr("soc_opt_agent.llm.client.litellm.completion", fake_completion)

    proposal = client.request_proposal(
        system_prompt="Return JSON.",
        user_prompt="Context JSON: {}",
        model="gemini-2.5-flash",
    )

    assert proposal.changes["CONFIG_QUEUE_SIZE"] == 8


def test_build_policy_from_config_passes_runtime_client_settings():
    policy = build_policy_from_config(
        {
            "api_key_env": "CUSTOM_GEMINI_KEY",
            "api_base": "https://example.invalid/v1beta",
            "timeout_seconds": 12,
        }
    )

    assert policy.client.api_key_env == "CUSTOM_GEMINI_KEY"
    assert policy.client.api_base == "https://example.invalid/v1beta"
    assert policy.client.timeout_seconds == 12


def test_configure_litellm_runtime_suppresses_debug_banner(monkeypatch):
    monkeypatch.delenv("LITELLM_LOG", raising=False)
    monkeypatch.setattr("soc_opt_agent.llm.client.litellm.suppress_debug_info", False)
    monkeypatch.setattr("soc_opt_agent.llm.client.litellm.set_verbose", True)

    configure_litellm_runtime()

    assert os.environ["LITELLM_LOG"] == "ERROR"
    from soc_opt_agent.llm.client import litellm as configured_litellm

    assert configured_litellm.suppress_debug_info is True
    assert configured_litellm.set_verbose is False


@pytest.mark.parametrize(
    ("model", "kwargs"),
    [
        (AcceleratorTarget, {"name": "demo", "benchmark_exe": "demo.exe", "unexpected": 1}),
        (
            IterationMetrics,
            {"passed": True, "accelerator_total_cycles": 63, "offchip_memory_accesses": 186, "unexpected": 1},
        ),
        (
            LLMProposal,
            {
                "changes": {"CONFIG_QUEUE_SIZE": 8},
                "rationale": "Increase buffering",
                "search_intent": "Probe buffering",
                "unexpected": 1,
            },
        ),
    ],
)
def test_schema_objects_reject_unknown_fields(model, kwargs):
    with pytest.raises(ValidationError):
        model(**kwargs)


def test_default_soc_root_raises_outside_checkout(tmp_path):
    with pytest.raises(RuntimeError, match="Unable to locate the ESP repository root"):
        get_default_soc_root(tmp_path)


def test_find_repo_root_accepts_checkout_without_docs_directory(tmp_path):
    repo_root = tmp_path / "esp"
    (repo_root / "socs").mkdir(parents=True)
    (repo_root / "accelerators").mkdir()
    (repo_root / "tech").mkdir()
    (repo_root / "tools").mkdir()

    nested_path = repo_root / "soc_opt_agent" / "src"
    nested_path.mkdir(parents=True)

    assert find_repo_root(nested_path) == repo_root
