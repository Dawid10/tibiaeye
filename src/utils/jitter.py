"""Jitter - adds human-like timing variation to delays."""
import random

from ..core.constants import JITTER_SIGMA


def jitter(base_delay: float, sigma_fraction: float = JITTER_SIGMA) -> float:
    """Add gaussian noise to a delay. Human timing follows normal distribution."""
    if base_delay <= 0:
        return 0
    result = random.gauss(base_delay, base_delay * sigma_fraction)
    return max(base_delay * 0.5, result)
