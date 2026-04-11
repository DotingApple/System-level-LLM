from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictInt


class AcceleratorTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    benchmark_exe: str


class IterationMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: Annotated[bool, Field(strict=True)]
    accelerator_total_cycles: Annotated[int, Field(ge=0, strict=True)]
    offchip_memory_accesses: Annotated[int, Field(ge=0, strict=True)]
    accelerator_tlb_loading_cycles: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    accelerator_mem_cycles: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    accelerator_invocations: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    coherence_requests_to_llc: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    coherence_forwards_from_llc: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    coherence_responses_received_by_llc: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    coherence_responses_sent_by_llc: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    dma_requests_to_mem: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    dma_responses_from_mem: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    coherent_dma_requests_to_llc: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    coherent_dma_responses_from_llc: Annotated[int | None, Field(default=None, ge=0, strict=True)]
    lut_utilization: Annotated[float | None, Field(default=None, ge=0.0, strict=True)]
    ff_utilization: Annotated[float | None, Field(default=None, ge=0.0, strict=True)]
    bram_utilization: Annotated[float | None, Field(default=None, ge=0.0, strict=True)]
    dsp_utilization: Annotated[float | None, Field(default=None, ge=0.0, strict=True)]
    resource_score: Annotated[float | None, Field(default=None, ge=0.0, strict=True)]


class LLMProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    changes: dict[str, StrictInt | str | list[StrictInt]]
    rationale: str
    search_intent: str
