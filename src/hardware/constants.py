"""
Hardware abstraction constants.

Serial communication, capture card, and mode identifiers.
"""

# Hardware modes
MODE_SOFTWARE = "software"
MODE_ARDUINO = "arduino"
MODE_FULL_HARDWARE = "full_hardware"
MODE_CAPTURE_CARD = "capture_card"

# Arduino serial
ARDUINO_BAUD_RATE = 115200
ARDUINO_SERIAL_TIMEOUT = 0.1
ARDUINO_COMMAND_DELAY = 0.002
ARDUINO_CLICK_PRESS_DURATION = 0.008  # 8ms + 2ms cmd delay ≈ firmware delay(10)
ARDUINO_CLICK_INTERVAL = 0.05         # 50ms between clicks, = firmware delay(50)

# Capture card
CAPTURE_DEVICE_INDEX = 0
