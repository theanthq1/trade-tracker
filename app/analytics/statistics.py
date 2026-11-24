from __future__ import annotations

from .metrics import expectancy, win_rate


def summarize_pnls(pnls: list[float]) -> dict[str, float]:
    return {"win_rate": win_rate(pnls), "expectancy": expectancy(pnls), "count": float(len(pnls))}
