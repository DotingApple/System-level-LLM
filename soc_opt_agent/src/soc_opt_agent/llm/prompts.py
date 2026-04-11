from __future__ import annotations

from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"
PROMPTS_DIR_RESOLVED = PROMPTS_DIR.resolve()


def get_prompt_path(name: str) -> Path:
    path = (PROMPTS_DIR / name).resolve()
    try:
        path.relative_to(PROMPTS_DIR_RESOLVED)
    except ValueError as exc:
        raise ValueError(f"Prompt name {name!r} escapes PROMPTS_DIR") from exc
    return path


def load_prompt(name: str) -> str:
    return get_prompt_path(name).read_text(encoding="utf-8")


def load_system_prompt() -> str:
    return load_prompt("system.txt")


def load_suggest_config_prompt() -> str:
    return load_prompt("suggest_config.txt")


def load_reflect_on_result_prompt() -> str:
    return load_prompt("reflect_on_result.txt")


__all__ = [
    "PROMPTS_DIR",
    "get_prompt_path",
    "load_prompt",
    "load_system_prompt",
    "load_suggest_config_prompt",
    "load_reflect_on_result_prompt",
]
