from __future__ import annotations

from collections.abc import Mapping

from soc_opt_agent.config_edit.parser import parse_esp_config_entries
from soc_opt_agent.config_edit.validators import (
    validate_allowed_keys,
    validate_no_duplicate_disabled_keys_for_targets,
    validate_no_mixed_key_states,
    validate_no_duplicate_active_keys,
)


def _stringify_config_value(value: object) -> str:
    if isinstance(value, list):
        return " ".join(_stringify_config_value(item) for item in value)
    return str(value)


def _assert_safe_config_value(value: object) -> None:
    if isinstance(value, list):
        for item in value:
            _assert_safe_config_value(item)
        return

    text = str(value)
    if "\n" in text or "\r" in text:
        raise ValueError("config values must not contain newline characters")


def apply_changes(text: str, changes: Mapping[str, object], allowed_keys: set[str]) -> str:
    validate_allowed_keys(changes, allowed_keys)

    entries = parse_esp_config_entries(text)
    validate_no_mixed_key_states(entries)
    validate_no_duplicate_active_keys(entries)
    validate_no_duplicate_disabled_keys_for_targets(entries, changes)

    for value in changes.values():
        _assert_safe_config_value(value)

    entries_by_line = {entry.line_number: entry for entry in entries}
    lines = text.splitlines(keepends=True)
    updated_lines: list[str] = []
    remaining_changes = dict(changes)

    for line_number, line in enumerate(lines, start=1):
        entry = entries_by_line.get(line_number)
        if entry is None:
            updated_lines.append(line)
            continue

        if entry.key not in remaining_changes:
            updated_lines.append(line)
            continue

        newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        updated_lines.append(
            f"{entry.key} = {_stringify_config_value(remaining_changes.pop(entry.key))}{newline}"
        )

    if remaining_changes:
        if updated_lines and not updated_lines[-1].endswith(("\n", "\r")):
            updated_lines[-1] = f"{updated_lines[-1]}\n"

        for key, value in remaining_changes.items():
            updated_lines.append(f"{key} = {_stringify_config_value(value)}\n")

    return "".join(updated_lines)
