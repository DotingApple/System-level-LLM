from __future__ import annotations

from pathlib import Path

from soc_opt_agent.models import AcceleratorTarget
from soc_opt_agent.paths import get_default_benchmark_exe


def discover_accelerators(root: Path, soc_dir: Path | None = None) -> list[AcceleratorTarget]:
    targets: list[AcceleratorTarget] = []

    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name == "common" or child.name.startswith(".") or child.name.startswith("__"):
            continue

        targets.append(
            AcceleratorTarget(
                name=child.name,
                benchmark_exe=str(get_default_benchmark_exe(child.name, soc_dir)),
            )
        )

    return targets
