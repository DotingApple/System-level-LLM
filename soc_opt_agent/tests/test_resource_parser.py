from pathlib import Path

import pytest

from soc_opt_agent.monitor.resource_parser import parse_resource_report


FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def test_parse_resource_report_extracts_main_utilizations():
    text = (
        "1. Slice Logic\n"
        "+----------------------------+--------+-------+------------+-----------+-------+\n"
        "|          Site Type         |  Used  | Fixed | Prohibited | Available | Util% |\n"
        "+----------------------------+--------+-------+------------+-----------+-------+\n"
        "| Slice LUTs                 | 133512 |     0 |          0 |    303600 | 43.98 |\n"
        "| Slice Registers            | 114701 |     0 |          0 |    607200 | 18.89 |\n"
        "+----------------------------+--------+-------+------------+-----------+-------+\n"
        "3. Memory\n"
        "+-------------------+-------+-------+------------+-----------+-------+\n"
        "|     Site Type     |  Used | Fixed | Prohibited | Available | Util% |\n"
        "+-------------------+-------+-------+------------+-----------+-------+\n"
        "| Block RAM Tile    | 187.5 |     0 |          0 |      1030 | 18.20 |\n"
        "+-------------------+-------+-------+------------+-----------+-------+\n"
        "4. DSP\n"
        "+----------------+------+-------+------------+-----------+-------+\n"
        "|    Site Type   | Used | Fixed | Prohibited | Available | Util% |\n"
        "+----------------+------+-------+------------+-----------+-------+\n"
        "| DSPs           |   27 |     0 |          0 |      2800 |  0.96 |\n"
        "+----------------+------+-------+------------+-----------+-------+\n"
    )

    parsed = parse_resource_report(text)

    assert parsed == {
        "lut_utilization": 43.98,
        "ff_utilization": 18.89,
        "bram_utilization": 18.20,
        "dsp_utilization": 0.96,
        "resource_score": pytest.approx((43.98 + 18.89 + 18.20 + 0.96) / 4.0),
    }


def test_parse_resource_report_accepts_slice_luts_with_warning_marker():
    text = (
        "1. Slice Logic\n"
        "+----------------------------+--------+-------+------------+-----------+-------+\n"
        "|          Site Type         |  Used  | Fixed | Prohibited | Available | Util% |\n"
        "+----------------------------+--------+-------+------------+-----------+-------+\n"
        "| Slice LUTs*                | 482595 |     0 |          0 |    303600 | 158.96 |\n"
        "| Slice Registers            | 111517 |     0 |          0 |    607200 |  18.37 |\n"
        "+----------------------------+--------+-------+------------+-----------+-------+\n"
        "2. Memory\n"
        "+-------------------+-------+-------+------------+-----------+-------+\n"
        "|     Site Type     |  Used | Fixed | Prohibited | Available | Util% |\n"
        "+-------------------+-------+-------+------------+-----------+-------+\n"
        "| Block RAM Tile    | 187.5 |     0 |          0 |      1030 | 18.20 |\n"
        "+-------------------+-------+-------+------------+-----------+-------+\n"
        "3. DSP\n"
        "+----------------+------+-------+------------+-----------+-------+\n"
        "|    Site Type   | Used | Fixed | Prohibited | Available | Util% |\n"
        "+----------------+------+-------+------------+-----------+-------+\n"
        "| DSPs           |   27 |     0 |          0 |      2800 |  0.96 |\n"
        "+----------------+------+-------+------------+-----------+-------+\n"
    )

    parsed = parse_resource_report(text)

    assert parsed["lut_utilization"] == 158.96


def test_parse_resource_report_rejects_missing_required_resource():
    text = "| Slice LUTs | 1 | 0 | 0 | 10 | 10.00 |\n| Slice Registers | 1 | 0 | 0 | 10 | 10.00 |\n"

    with pytest.raises(ValueError, match="BRAM"):
        parse_resource_report(text)
