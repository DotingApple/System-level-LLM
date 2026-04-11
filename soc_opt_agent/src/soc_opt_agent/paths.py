from __future__ import annotations

from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    candidate = (start or Path(__file__)).resolve()
    markers = ("socs", "accelerators", "tech", "tools")

    for current in (candidate, *candidate.parents):
        if current.is_dir() and all((current / marker).exists() for marker in markers):
            return current

    checked = ", ".join(str(path) for path in (candidate, *candidate.parents))
    raise RuntimeError(
        "Unable to locate the ESP repository root. "
        f"Looked for directories containing {', '.join(markers)} starting from {checked}."
    )


PACKAGE_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PACKAGE_ROOT.parent
PROJECT_ROOT = SRC_ROOT.parent


def get_esp_root(start: Path | None = None) -> Path:
    return find_repo_root(start or PROJECT_ROOT)


def get_default_soc_root(start: Path | None = None) -> Path:
    return get_esp_root(start) / "socs" / "xilinx-vc707-xc7vx485t"


def get_default_accelerators_root(start: Path | None = None) -> Path:
    return get_esp_root(start) / "accelerators" / "rtl"


def get_default_tech_acc_root(start: Path | None = None) -> Path:
    return get_esp_root(start) / "tech" / "virtex7" / "acc"


def get_default_benchmark_exe(accelerator_name: str, soc_root: Path | None = None) -> Path:
    root = soc_root or get_default_soc_root()
    return root / "soft-build" / "ariane" / "baremetal" / f"{accelerator_name}.exe"


def get_default_esp_config_path(soc_root: Path | None = None) -> Path:
    root = soc_root or get_default_soc_root()
    return root / "socgen" / "esp" / ".esp_config"


def get_default_transcript_path(soc_root: Path | None = None) -> Path:
    root = soc_root or get_default_soc_root()
    return root / "modelsim" / "transcript"


def get_default_utilization_report_paths(soc_root: Path | None = None) -> list[Path]:
    root = soc_root or get_default_soc_root()
    vivado_runs = root / "vivado" / f"esp-{root.name}.runs"
    return [
        vivado_runs / "impl_1" / "top_utilization_placed.rpt",
    ]


def get_default_runs_root(start: Path | None = None) -> Path:
    return (start or PROJECT_ROOT) / "runs"


def get_default_baselines_root(start: Path | None = None) -> Path:
    return (start or PROJECT_ROOT) / "baselines"


def get_default_bests_root(start: Path | None = None) -> Path:
    return (start or PROJECT_ROOT) / "bests"
