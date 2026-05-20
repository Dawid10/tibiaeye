#!/usr/bin/env python3
"""Get current coordinate - quick script."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core import get_screen_capture
from src.repositories.radar import get_coordinate
import cv2

screen = get_screen_capture()
img = screen.capture()
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
coord = get_coordinate(gray, None)

if coord:
    print(f"[{coord[0]}, {coord[1]}, {coord[2]}]")
else:
    print("Coordenada não detectada")
