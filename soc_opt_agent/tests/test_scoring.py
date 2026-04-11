import pytest

from soc_opt_agent.scoring.compare import improvement_ratio, is_plateau


def test_plateau_requires_five_small_improvements():
    ratios = [0.01, 0.015, 0.0, 0.019, 0.005]
    assert is_plateau(ratios, min_improvement=0.02, window=5) is True
    assert improvement_ratio(best_cycles=100, candidate_cycles=95) == 0.05


def test_improvement_ratio_rejects_zero_best_cycles():
    with pytest.raises(ValueError, match="best_cycles must be greater than 0"):
        improvement_ratio(best_cycles=0, candidate_cycles=95)


@pytest.mark.parametrize(
    ("ratios", "window", "expected"),
    [
        ([], 0, False),
        ([0.01, 0.02], 3, False),
        ([0.02, 0.02, 0.02], 3, False),
    ],
)
def test_is_plateau_boundary_behavior(ratios, window, expected):
    assert is_plateau(ratios, min_improvement=0.02, window=window) is expected
