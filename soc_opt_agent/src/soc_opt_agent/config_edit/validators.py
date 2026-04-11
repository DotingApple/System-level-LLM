from __future__ import annotations

from collections.abc import Collection, Mapping

from soc_opt_agent.config_edit.parser import ConfigEntry


def validate_allowed_keys(changes: Mapping[str, object], allowed_keys: Collection[str]) -> None:
    allowed = set(allowed_keys)
    disallowed = sorted(key for key in changes if key not in allowed)
    if disallowed:
        joined = ", ".join(disallowed)
        raise ValueError(f"disallowed config keys: {joined}")


def validate_no_duplicate_active_keys(entries: Collection[ConfigEntry]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()

    for entry in entries:
        if entry.disabled:
            continue
        if entry.key in seen:
            duplicates.add(entry.key)
        else:
            seen.add(entry.key)

    if duplicates:
        joined = ", ".join(sorted(duplicates))
        raise ValueError(f"duplicate active config keys: {joined}")


def validate_no_duplicate_disabled_keys_for_targets(
    entries: Collection[ConfigEntry],
    target_keys: Collection[str],
) -> None:
    targets = set(target_keys)
    seen: set[str] = set()
    duplicates: set[str] = set()

    for entry in entries:
        if not entry.disabled or entry.key not in targets:
            continue
        if entry.key in seen:
            duplicates.add(entry.key)
        else:
            seen.add(entry.key)

    if duplicates:
        joined = ", ".join(sorted(duplicates))
        raise ValueError(f"duplicate disabled config keys for edited keys: {joined}")


def validate_no_mixed_key_states(entries: Collection[ConfigEntry]) -> None:
    states: dict[str, set[bool]] = {}

    for entry in entries:
        key_states = states.setdefault(entry.key, set())
        key_states.add(entry.disabled)
        if len(key_states) > 1:
            raise ValueError(f"mixed config key states: {entry.key}")
