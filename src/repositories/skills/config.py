"""
Skills Config - Hash tables for reading digit values.

Based on PyTibia's approach:
- Load digit images (0-9)
- Generate hashes for all number combinations
- Use hash lookup for fast reading
"""
import pathlib
import cv2
import numpy as np

from ...utils.image_resolver import resolve_image

# Try to use farmhash for fast hashing (like PyTibia)
try:
    from farmhash import FarmHash64
    def hashit(arr: np.ndarray) -> int:
        return FarmHash64(np.ascontiguousarray(arr))
except ImportError:
    import hashlib
    def hashit(arr: np.ndarray) -> int:
        return int(hashlib.md5(np.ascontiguousarray(arr)).hexdigest()[:16], 16)


CURRENT_PATH = pathlib.Path(__file__).parent.resolve()
IMAGES_PATH = CURRENT_PATH / "images"
DIGITS_PATH = IMAGES_PATH / "digits"
ICONS_PATH = IMAGES_PATH / "icons"


def load_gray_image(path: str) -> np.ndarray:
    """Load image as grayscale."""
    img = cv2.imread(str(path))
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


# Load digit images
images = {
    'digits': {},
    'icons': {}
}

# Expected digit dimensions
DIGIT_WIDTH = 6
DIGIT_HEIGHT = 8

# Load digits 0-9 (resolve_image picks platform-specific via PLATFORM)
for i in range(10):
    digit_path = resolve_image(IMAGES_PATH, f"digits/{i}.png")
    if digit_path.exists():
        img = load_gray_image(str(digit_path))
        if img is not None and img.shape[1] < DIGIT_WIDTH:
            padded = np.zeros((DIGIT_HEIGHT, DIGIT_WIDTH), dtype=np.uint8)
            padded[:, :img.shape[1]] = img
            img = padded
        images['digits'][i] = img

# Load skills icon
skills_icon_path = resolve_image(IMAGES_PATH, "icons/skills.png")
if skills_icon_path.exists():
    images['icons']['skills'] = load_gray_image(str(skills_icon_path))

# Generate hash tables for number recognition
minutes_or_hours_hashes = {}
numbers_hashes = {}

# Generate hashes for numbers 0-999 (for HP, Mana, Capacity, etc.)
for number in range(1000):
    number_str = "{:03d}".format(number)
    digit = int(number_str[2])

    if digit not in images['digits'] or images['digits'][digit] is None:
        continue

    digit_image = images['digits'][digit]
    number_img = np.zeros((8, 22), dtype=np.uint8)
    number_img[:, 22 - 6:22] = digit_image

    # Decimal digit (tens place)
    if number >= 10:
        decimal_digit = int(number_str[1])
        if decimal_digit in images['digits'] and images['digits'][decimal_digit] is not None:
            decimal_digit_image = images['digits'][decimal_digit]
            number_img[:, 22 - 14:22 - 14 + 6] = decimal_digit_image

    # Hundred digit
    if number >= 100:
        hundred_digit = int(number_str[0])
        if hundred_digit in images['digits'] and images['digits'][hundred_digit] is not None:
            hundred_digit_image = images['digits'][hundred_digit]
            number_img[:, 0:6] = hundred_digit_image

    number_img = np.array(number_img, dtype=np.uint8)
    hash_key = hashit(number_img)
    numbers_hashes[hash_key] = number

# Generate hashes for minutes/hours 0-59 (for Food, Stamina)
for number in range(60):
    number_str = "{:02d}".format(number)
    first_digit = int(number_str[1])
    second_digit = int(number_str[0])

    if first_digit not in images['digits'] or images['digits'][first_digit] is None:
        continue
    if second_digit not in images['digits'] or images['digits'][second_digit] is None:
        continue

    first_digit_image = images['digits'][first_digit]
    second_digit_image = images['digits'][second_digit]

    date_img = np.zeros((8, 14), dtype=np.uint8)
    date_img[:, 14 - 6:14] = first_digit_image
    date_img[:, 0:6] = second_digit_image
    date_img = np.array(date_img, dtype=np.uint8)

    hash_key = hashit(date_img)
    minutes_or_hours_hashes[hash_key] = number

print(f"Skills config loaded: {len(numbers_hashes)} number hashes, {len(minutes_or_hours_hashes)} time hashes")
