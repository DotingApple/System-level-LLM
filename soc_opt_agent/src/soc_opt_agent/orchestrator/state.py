from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class CampaignState:
    completed_accelerators: list[str] = field(default_factory=list)
    recent_improvements: list[float] = field(default_factory=list)

    def has_completed(self, accelerator_name: str) -> bool:
        return accelerator_name in self.completed_accelerators

    def mark_completed(self, accelerator_name: str) -> None:
        if accelerator_name not in self.completed_accelerators:
            self.completed_accelerators.append(accelerator_name)

    def record_improvement(self, improvement: float) -> None:
        self.recent_improvements.append(improvement)
