from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import shlex
import subprocess
from collections.abc import Callable


TOOLS_ENV_SCRIPT = "/opt/cad/scripts/tools_env.sh"
_ESP_CONFIG_SUCCESS_MARKERS = (
    "Created global constants definition into 'esp_global.vhd'",
    "Created configuration into 'socmap.vhd'",
    "Created configuration into 'mmi64_regs.h'",
)


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    cwd: str
    stdout: str
    stderr: str
    returncode: int


def _sanitized_env() -> dict[str, str]:
    env = dict(os.environ)
    virtual_env = env.pop("VIRTUAL_ENV", None)
    env.pop("PYTHONHOME", None)
    env.pop("PYTHONPATH", None)
    if virtual_env:
        venv_bin = str(Path(virtual_env) / "bin")
        path_entries = [entry for entry in env.get("PATH", "").split(os.pathsep) if entry and entry != venv_bin]
        env["PATH"] = os.pathsep.join(path_entries)
    return env


def _is_benign_esp_config_cleanup_failure(command: list[str], stdout: str, returncode: int) -> bool:
    if returncode == 0 or command != ["make", "esp-config"]:
        return False
    if "/usr/bin/xvfb-run: line 186: kill:" not in stdout:
        return False
    if "make: ***" not in stdout:
        return False
    return all(marker in stdout for marker in _ESP_CONFIG_SUCCESS_MARKERS)


def run_command(
    command: list[str],
    cwd: Path,
    on_output: Callable[[str], None] | None = None,
) -> CommandResult:
    shell_command = f"source {shlex.quote(TOOLS_ENV_SCRIPT)} && {shlex.join(command)}"
    process = subprocess.Popen(
        ["/bin/bash", "-lc", shell_command],
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        env=_sanitized_env(),
    )
    assert process.stdout is not None
    collected_output: list[str] = []
    for line in process.stdout:
        collected_output.append(line)
        if on_output is not None:
            on_output(line.rstrip("\n"))

    returncode = process.wait()
    stdout = "".join(collected_output)
    if returncode != 0 and not _is_benign_esp_config_cleanup_failure(command, stdout, returncode):
        raise subprocess.CalledProcessError(returncode, process.args, output=stdout, stderr="")
    return CommandResult(
        command=list(command),
        cwd=str(cwd),
        stdout=stdout,
        stderr="",
        returncode=returncode,
    )


__all__ = ["CommandResult", "run_command"]
