"""Doc 07 §10 adaptive updating: New Baseline = alpha*Current + (1-alpha)*Previous."""
from __future__ import annotations

import math


class EmaStat:
    """Exponential moving average with an EMA-of-squared-deviation variance
    estimate, so both mean and spread adapt gradually per Doc 07 §10."""

    def __init__(self, alpha: float):
        self.alpha = alpha
        self.mean: float | None = None
        self.var: float = 0.0
        self.n: int = 0

    def seed(self, mean: float, std: float) -> None:
        """Doc 07 §17: prime from a population reference before any real
        observation exists."""
        self.mean = mean
        self.var = std ** 2

    def update(self, x: float) -> None:
        self.n += 1
        if self.mean is None:
            self.mean = x
            self.var = 0.0
            return
        delta = x - self.mean
        self.mean = self.alpha * x + (1 - self.alpha) * self.mean
        self.var = (1 - self.alpha) * (self.var + self.alpha * delta * delta)

    @property
    def std(self) -> float:
        return math.sqrt(self.var) if self.var > 0 else 0.0

    @property
    def has_data(self) -> bool:
        return self.mean is not None
