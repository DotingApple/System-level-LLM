from __future__ import annotations


def build_esp_config_command() -> list[str]:
    return ["make", "esp-config"]


def build_baremetal_command(accelerator_name: str) -> list[str]:
    return ["make", f"{accelerator_name}-baremetal"]


def build_sim_command(test_program: str) -> list[str]:
    return ["make", "sim", f"TEST_PROGRAM={test_program}"]
