from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ConfigEntry:
    key: str
    value: str
    line_number: int
    raw_line: str
    disabled: bool = False


def _parse_assignment_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None

    key, value = stripped.split("=", 1)
    key = key.strip()
    value = value.strip()
    if not key:
        return None

    return key, value


def _parse_disabled_line(line: str) -> str | None:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return None

    match = re.fullmatch(r"#\s*(CONFIG_[A-Z0-9_]+)\s+is not set", stripped)
    if match is None:
        return None

    return match.group(1)


def parse_esp_config_entries(text: str) -> list[ConfigEntry]:
    entries: list[ConfigEntry] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        parsed = _parse_assignment_line(raw_line)
        if parsed is None:
            disabled_key = _parse_disabled_line(raw_line)
            if disabled_key is None:
                continue

            entries.append(
                ConfigEntry(
                    key=disabled_key,
                    value="n",
                    line_number=line_number,
                    raw_line=raw_line,
                    disabled=True,
                )
            )
            continue

        key, value = parsed
        entries.append(
            ConfigEntry(
                key=key,
                value=value,
                line_number=line_number,
                raw_line=raw_line,
                disabled=False,
            )
        )

    return entries


def parse_esp_config(text: str) -> dict[str, str]:
    entries = parse_esp_config_entries(text)

    from soc_opt_agent.config_edit.validators import (
        validate_no_duplicate_active_keys,
        validate_no_mixed_key_states,
    )

    validate_no_duplicate_active_keys(entries)
    validate_no_mixed_key_states(entries)

    parsed: dict[str, str] = {}
    for entry in entries:
        if entry.disabled:
            continue
        parsed[entry.key] = entry.value
    return parsed
