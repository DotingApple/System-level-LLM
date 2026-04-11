def improvement_ratio(best_cycles: int, candidate_cycles: int) -> float:
    if best_cycles == 0:
        raise ValueError("best_cycles must be greater than 0")
    return (best_cycles - candidate_cycles) / best_cycles


def is_plateau(ratios: list[float], min_improvement: float, window: int) -> bool:
    if window <= 0 or len(ratios) < window:
        return False

    return all(value < min_improvement for value in ratios[-window:])
