import re

from soc_opt_agent.models import IterationMetrics

_CYCLES_PATTERN = re.compile(r"Accelerator\s+\d+\s+total cycles:\s+(\d+)")
_OFFCHIP_PATTERN = re.compile(r"Off-chip memory accesses at mem tile\s+\d+:\s+(\d+)")
_TLB_LOADING_PATTERN = re.compile(r"Accelerator\s+\d+\s+TLB-loading cycles:\s+(\d+)")
_MEM_CYCLES_PATTERN = re.compile(r"Accelerator\s+\d+\s+mem cycles:\s+(\d+)")
_INVOCATIONS_PATTERN = re.compile(r"Accelerator\s+\d+\s+invocations:\s+(\d+)")
_COH_REQ_PATTERN = re.compile(r"Coherence requests to LLC\s+\d+:\s+(\d+)")
_COH_FWD_PATTERN = re.compile(r"Coherence forwards from LLC\s+\d+:\s+(\d+)")
_COH_RSP_RECV_PATTERN = re.compile(r"Coherence responses received by LLC\s+\d+:\s+(\d+)")
_COH_RSP_SENT_PATTERN = re.compile(r"Coherence responses sent by LLC\s+\d+:\s+(\d+)")
_DMA_REQ_PATTERN = re.compile(r"DMA requests to mem tile\s+\d+:\s+(\d+)")
_DMA_RSP_PATTERN = re.compile(r"DMA responses from mem tile\s+\d+:\s+(\d+)")
_COH_DMA_REQ_PATTERN = re.compile(r"Coherent DMA requests to LLC\s+\d+:\s+(\d+)")
_COH_DMA_RSP_PATTERN = re.compile(r"Coherent DMA responses from LLC\s+\d+:\s+(\d+)")


def _parse_optional_metric(pattern: re.Pattern[str], text: str, metric_name: str) -> int | None:
    matches = pattern.findall(text)
    if not matches:
        return None
    if len(matches) > 1:
        raise ValueError(f"Unable to parse {metric_name} from transcript: multiple {metric_name} lines found")
    return int(matches[0])


def parse_transcript(text: str) -> IterationMetrics:
    passed = "... PASS" in text and "ESP MONITOR STATS" in text

    cycles_matches = _CYCLES_PATTERN.findall(text)
    if not cycles_matches:
        raise ValueError("Unable to parse accelerator total cycles from transcript")
    if len(cycles_matches) > 1:
        raise ValueError("Unable to parse accelerator total cycles from transcript: multiple accelerator total cycles lines found")

    offchip_matches = _OFFCHIP_PATTERN.findall(text)
    if not offchip_matches:
        raise ValueError("Unable to parse off-chip memory accesses from transcript")
    if len(offchip_matches) > 1:
        raise ValueError("Unable to parse off-chip memory accesses from transcript: multiple off-chip memory accesses lines found")

    return IterationMetrics(
        passed=passed,
        accelerator_total_cycles=int(cycles_matches[0]),
        offchip_memory_accesses=int(offchip_matches[0]),
        accelerator_tlb_loading_cycles=_parse_optional_metric(
            _TLB_LOADING_PATTERN,
            text,
            "accelerator TLB-loading cycles",
        ),
        accelerator_mem_cycles=_parse_optional_metric(
            _MEM_CYCLES_PATTERN,
            text,
            "accelerator mem cycles",
        ),
        accelerator_invocations=_parse_optional_metric(
            _INVOCATIONS_PATTERN,
            text,
            "accelerator invocations",
        ),
        coherence_requests_to_llc=_parse_optional_metric(
            _COH_REQ_PATTERN,
            text,
            "coherence requests to LLC",
        ),
        coherence_forwards_from_llc=_parse_optional_metric(
            _COH_FWD_PATTERN,
            text,
            "coherence forwards from LLC",
        ),
        coherence_responses_received_by_llc=_parse_optional_metric(
            _COH_RSP_RECV_PATTERN,
            text,
            "coherence responses received by LLC",
        ),
        coherence_responses_sent_by_llc=_parse_optional_metric(
            _COH_RSP_SENT_PATTERN,
            text,
            "coherence responses sent by LLC",
        ),
        dma_requests_to_mem=_parse_optional_metric(
            _DMA_REQ_PATTERN,
            text,
            "DMA requests to mem tile",
        ),
        dma_responses_from_mem=_parse_optional_metric(
            _DMA_RSP_PATTERN,
            text,
            "DMA responses from mem tile",
        ),
        coherent_dma_requests_to_llc=_parse_optional_metric(
            _COH_DMA_REQ_PATTERN,
            text,
            "coherent DMA requests to LLC",
        ),
        coherent_dma_responses_from_llc=_parse_optional_metric(
            _COH_DMA_RSP_PATTERN,
            text,
            "coherent DMA responses from LLC",
        ),
    )
