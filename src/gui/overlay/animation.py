"""Overlay pulse animation - pure function."""
import math

from .config import OPACITY_MIN, OPACITY_MAX, PULSE_PERIOD


def compute_pulse_opacity(elapsed_seconds: float) -> float:
    t = elapsed_seconds % PULSE_PERIOD
    return OPACITY_MIN + (OPACITY_MAX - OPACITY_MIN) * (math.sin(2 * math.pi * t / PULSE_PERIOD) + 1) / 2
