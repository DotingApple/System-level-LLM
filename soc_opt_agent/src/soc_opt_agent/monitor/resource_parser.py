from __future__ import annotations

import re
from pathlib import Path


_LUT_PATTERN = re.compile(r"^\|\s*Slice LUTs\*?\s*\|.*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*$", re.MULTILINE)
_FF_PATTERN = re.compile(r"^\|\s*Slice Registers\s*\|.*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*$", re.MULTILINE)
_BRAM_PATTERN = re.compile(r"^\|\s*Block RAM Tile\s*\|.*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*$", re.MULTILINE)
_DSP_PATTERN = re.compile(r"^\|\s*DSPs\s*\|.*\|\s*([0-9]+(?:\.[0-9]+)?)\s*\|\s*$", re.MULTILINE)


def _parse_required_percentage(pattern: re.Pattern[str], text: str, label: str) -> float:
    matches = pattern.findall(text)
    if not matches:
        raise ValueError(f"Unable to parse {label} utilization from Vivado report")
    return float(matches[0])


def parse_resource_report(text: str) -> dict[str, float]:
    lut_utilization = _parse_required_percentage(_LUT_PATTERN, text, "LUT")
    ff_utilization = _parse_required_percentage(_FF_PATTERN, text, "FF")
    bram_utilization = _parse_required_percentage(_BRAM_PATTERN, text, "BRAM")
    dsp_utilization = _parse_required_percentage(_DSP_PATTERN, text, "DSP")
    resource_score = (lut_utilization + ff_utilization + bram_utilization + dsp_utilization) / 4.0
    return {
        "lut_utilization": lut_utilization,
        "ff_utilization": ff_utilization,
        "bram_utilization": bram_utilization,
        "dsp_utilization": dsp_utilization,
        "resource_score": resource_score,
    }


def load_resource_report(report_path: Path) -> dict[str, float]:
    return parse_resource_report(report_path.read_text(encoding="utf-8"))
