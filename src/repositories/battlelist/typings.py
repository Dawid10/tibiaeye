"""Type aliases for battlelist module."""
from typing import Tuple

import numpy as np

GrayImage = np.ndarray
BBox = Tuple[int, int, int, int]  # (x, y, width, height)
