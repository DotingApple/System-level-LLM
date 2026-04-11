from pathlib import Path

import pytest

from soc_opt_agent.monitor.transcript_parser import parse_transcript

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_parse_transcript_extracts_key_metrics():
    text = (FIXTURES_DIR / "sample_transcript_pass.txt").read_text()
    metrics = parse_transcript(text)
    assert metrics.passed is True
    assert metrics.accelerator_total_cycles == 63
    assert metrics.offchip_memory_accesses == 186
    assert metrics.accelerator_tlb_loading_cycles == 21
    assert metrics.accelerator_mem_cycles == 34
    assert metrics.accelerator_invocations == 1
    assert metrics.coherence_requests_to_llc == 178
    assert metrics.coherence_forwards_from_llc == 0
    assert metrics.coherence_responses_received_by_llc == 0
    assert metrics.coherence_responses_sent_by_llc == 360
    assert metrics.dma_requests_to_mem == 11
    assert metrics.dma_responses_from_mem == 5
    assert metrics.coherent_dma_requests_to_llc == 0
    assert metrics.coherent_dma_responses_from_llc == 0


def test_parse_transcript_marks_missing_pass_as_false():
    text = "\n".join(
        [
            "ESP MONITOR STATS",
            "Accelerator 3 total cycles: 63",
            "Off-chip memory accesses at mem tile 7: 186",
            "Program Completed!",
        ]
    )

    metrics = parse_transcript(text)

    assert metrics.passed is False
    assert metrics.accelerator_total_cycles == 63
    assert metrics.offchip_memory_accesses == 186
    assert metrics.accelerator_tlb_loading_cycles is None


def test_parse_transcript_accepts_nonzero_indices():
    text = "\n".join(
        [
            "ESP MONITOR STATS",
            "Accelerator 12 total cycles: 63",
            "Off-chip memory accesses at mem tile 4: 186",
            "... PASS",
        ]
    )

    metrics = parse_transcript(text)

    assert metrics.passed is True
    assert metrics.accelerator_total_cycles == 63
    assert metrics.offchip_memory_accesses == 186


def test_parse_transcript_rejects_multiple_optional_metric_lines():
    text = "\n".join(
        [
            "ESP MONITOR STATS",
            "Accelerator 0 total cycles: 63",
            "Off-chip memory accesses at mem tile 0: 186",
            "DMA requests to mem tile 0: 11",
            "DMA requests to mem tile 1: 12",
            "... PASS",
        ]
    )

    with pytest.raises(ValueError, match="multiple DMA requests to mem tile lines"):
        parse_transcript(text)


def test_parse_transcript_rejects_multiple_accelerator_total_cycle_lines():
    text = "\n".join(
        [
            "ESP MONITOR STATS",
            "Accelerator 3 total cycles: 63",
            "Accelerator 3 total cycles: 64",
            "Off-chip memory accesses at mem tile 7: 186",
            "... PASS",
        ]
    )

    with pytest.raises(ValueError, match="multiple accelerator total cycles"):
        parse_transcript(text)


def test_parse_transcript_rejects_multiple_offchip_memory_access_lines():
    text = "\n".join(
        [
            "ESP MONITOR STATS",
            "Accelerator 3 total cycles: 63",
            "Off-chip memory accesses at mem tile 7: 186",
            "Off-chip memory accesses at mem tile 7: 187",
            "... PASS",
        ]
    )

    with pytest.raises(ValueError, match="multiple off-chip memory accesses"):
        parse_transcript(text)


@pytest.mark.parametrize(
    "text",
    [
        "ESP MONITOR STATS\nOff-chip memory accesses at mem tile 0: 186\n... PASS",
        "ESP MONITOR STATS\nAccelerator 0 total cycles: 63\n... PASS",
    ],
)
def test_parse_transcript_raises_on_missing_metrics(text):
    with pytest.raises(ValueError):
        parse_transcript(text)
