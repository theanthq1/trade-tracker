from __future__ import annotations


def win_rate(pnls: list[float]) -> float:
    if not pnls:
        return 0.0
    return sum(pnl > 0 for pnl in pnls) / len(pnls) * 100


def expectancy(pnls: list[float]) -> float:
    return sum(pnls) / len(pnls) if pnls else 0.0
