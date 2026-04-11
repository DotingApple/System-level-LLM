import pytest

from soc_opt_agent.config_edit import validate_no_duplicate_disabled_keys_for_targets
from soc_opt_agent.config_edit.editor import apply_changes
from soc_opt_agent.config_edit.parser import parse_esp_config
from soc_opt_agent.config_edit.validators import validate_allowed_keys


def test_parse_esp_config_extracts_assignments_and_ignores_comments():
    text = (
        "CPU_ARCH = ariane\n"
        "#CONFIG_MULTICAST_NOC_EN is not set\n"
        "CONFIG_CPU_CACHES = 512 4 1024 16\n"
        "\n"
        "CONFIG_ETH_EN = y\n"
    )

    parsed = parse_esp_config(text)

    assert parsed == {
        "CPU_ARCH": "ariane",
        "CONFIG_CPU_CACHES": "512 4 1024 16",
        "CONFIG_ETH_EN": "y",
    }


def test_parse_esp_config_ignores_non_kconfig_comment_ending_in_is_not_set():
    text = (
        "# this is not set\n"
        "CONFIG_QUEUE_SIZE = 4\n"
    )

    parsed = parse_esp_config(text)

    assert parsed == {"CONFIG_QUEUE_SIZE": "4"}


def test_validate_allowed_keys_rejects_disallowed_keys():
    with pytest.raises(ValueError, match="CPU_ARCH"):
        validate_allowed_keys(
            {"CPU_ARCH": "ibex", "CONFIG_QUEUE_SIZE": 8},
            allowed_keys={"CONFIG_QUEUE_SIZE"},
        )


def test_apply_changes_updates_existing_lines_and_appends_missing_allowed_keys():
    text = "CPU_ARCH = ariane\nCONFIG_QUEUE_SIZE = 4\n"

    updated = apply_changes(
        text,
        {"CONFIG_QUEUE_SIZE": 8, "CONFIG_DMA_NOC_WIDTH": 128},
        allowed_keys={"CONFIG_QUEUE_SIZE", "CONFIG_DMA_NOC_WIDTH"},
    )

    assert "CPU_ARCH = ariane" in updated
    assert "CONFIG_QUEUE_SIZE = 8" in updated
    assert "CONFIG_DMA_NOC_WIDTH = 128" in updated
    assert updated.endswith("\n")


def test_apply_changes_updates_disabled_kconfig_line_in_place():
    text = "#CONFIG_QUEUE_SIZE is not set\n"

    updated = apply_changes(
        text,
        {"CONFIG_QUEUE_SIZE": 8},
        allowed_keys={"CONFIG_QUEUE_SIZE"},
    )

    assert updated == "CONFIG_QUEUE_SIZE = 8\n"


def test_apply_changes_rejects_newline_injection_values():
    text = "CONFIG_QUEUE_SIZE = 4\n"

    with pytest.raises(ValueError, match="newline"):
        apply_changes(
            text,
            {"CONFIG_QUEUE_SIZE": "8\nCONFIG_DMA_NOC_WIDTH = 128"},
            allowed_keys={"CONFIG_QUEUE_SIZE"},
        )


def test_apply_changes_rejects_duplicate_active_keys():
    text = "CONFIG_QUEUE_SIZE = 4\nCONFIG_QUEUE_SIZE = 6\n"

    with pytest.raises(ValueError, match="duplicate"):
        apply_changes(
            text,
            {"CONFIG_QUEUE_SIZE": 8},
            allowed_keys={"CONFIG_QUEUE_SIZE"},
        )


def test_apply_changes_rejects_mixed_disabled_and_active_key():
    text = "#CONFIG_QUEUE_SIZE is not set\nCONFIG_QUEUE_SIZE = 4\n"

    with pytest.raises(ValueError, match="mixed"):
        apply_changes(
            text,
            {"CONFIG_QUEUE_SIZE": 8},
            allowed_keys={"CONFIG_QUEUE_SIZE"},
        )


def test_parse_esp_config_rejects_mixed_disabled_and_active_key():
    text = "#CONFIG_QUEUE_SIZE is not set\nCONFIG_QUEUE_SIZE = 4\n"

    with pytest.raises(ValueError, match="mixed"):
        parse_esp_config(text)


def test_parse_esp_config_rejects_duplicate_active_keys():
    text = "CONFIG_QUEUE_SIZE = 4\nCONFIG_QUEUE_SIZE = 6\n"

    with pytest.raises(ValueError, match="duplicate active"):
        parse_esp_config(text)


def test_apply_changes_rejects_duplicate_disabled_target_keys():
    text = "#CONFIG_QUEUE_SIZE is not set\n# CONFIG_QUEUE_SIZE is not set\n"

    with pytest.raises(ValueError, match="duplicate disabled"):
        apply_changes(
            text,
            {"CONFIG_QUEUE_SIZE": 8},
            allowed_keys={"CONFIG_QUEUE_SIZE"},
        )


def test_config_edit_package_reexports_duplicate_disabled_validator():
    assert callable(validate_no_duplicate_disabled_keys_for_targets)
