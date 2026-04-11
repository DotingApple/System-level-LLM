from __future__ import annotations

import os
from pathlib import Path

from soc_opt_agent.esp_flow.executor import run_command


def test_run_command_sources_tools_env(monkeypatch):
    captured = {}
    seen_output: list[str] = []

    class FakeProcess:
        def __init__(self):
            self.args = []
            self.stdout = iter(["line one\n", "line two\n"])

        def wait(self):
            return 0

    def fake_popen(command, cwd, stdout, stderr, text, bufsize, env):
        captured["command"] = command
        captured["cwd"] = cwd
        captured["stdout"] = stdout
        captured["stderr"] = stderr
        captured["text"] = text
        captured["bufsize"] = bufsize
        captured["env"] = env
        process = FakeProcess()
        process.args = command
        return process

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    result = run_command(["make", "esp-config"], Path("/soc"), on_output=seen_output.append)

    assert captured["command"][0:2] == ["/bin/bash", "-lc"]
    assert "source /opt/cad/scripts/tools_env.sh && make esp-config" == captured["command"][2]
    assert captured["bufsize"] == 1
    assert result.command == ["make", "esp-config"]
    assert result.cwd == "/soc"
    assert result.stdout == "line one\nline two\n"
    assert seen_output == ["line one", "line two"]


def test_run_command_strips_virtualenv_from_child_environment(monkeypatch):
    captured = {}

    class FakeProcess:
        def __init__(self):
            self.args = []
            self.stdout = iter([])

        def wait(self):
            return 0

    def fake_popen(command, cwd, stdout, stderr, text, bufsize, env):
        captured["env"] = env
        process = FakeProcess()
        process.args = command
        return process

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setenv("VIRTUAL_ENV", "/tmp/demo-venv")
    monkeypatch.setenv("PYTHONHOME", "/tmp/pythonhome")
    monkeypatch.setenv("PYTHONPATH", "/tmp/pythonpath")
    monkeypatch.setenv("PATH", os.pathsep.join(["/tmp/demo-venv/bin", "/usr/bin", "/bin"]))

    run_command(["make", "esp-config"], Path("/soc"))

    assert "VIRTUAL_ENV" not in captured["env"]
    assert "PYTHONHOME" not in captured["env"]
    assert "PYTHONPATH" not in captured["env"]
    assert captured["env"]["PATH"] == os.pathsep.join(["/usr/bin", "/bin"])


def test_run_command_tolerates_benign_esp_config_cleanup_failure(monkeypatch):
    class FakeProcess:
        def __init__(self):
            self.args = []
            self.stdout = iter(
                [
                    "Generating ESP configuration...\n",
                    "Created global constants definition into 'esp_global.vhd'\n",
                    "Created configuration into 'socmap.vhd'\n",
                    "Created configuration into 'mmi64_regs.h'\n",
                    "/usr/bin/xvfb-run: line 186: kill: (659) - No such process\n",
                    "make: *** [/home/cz2931/esp/utils/make/esp.mk:28: socgen/esp/socmap.vhd] Error 1\n",
                ]
            )

        def wait(self):
            return 2

    def fake_popen(command, cwd, stdout, stderr, text, bufsize, env):
        process = FakeProcess()
        process.args = command
        return process

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    result = run_command(["make", "esp-config"], Path("/soc"))

    assert result.returncode == 2
    assert "Created configuration into 'socmap.vhd'" in result.stdout
