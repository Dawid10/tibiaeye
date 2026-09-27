"""
Screen capture system with caching and performance optimizations.

Uses MSS for fast screen capture with optional caching to avoid
redundant image processing when the screen hasn't changed.
"""
import hashlib
import threading
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Optional, Tuple, Dict, Any

import cv2
import numpy as np

try:
    import mss
    MSS_AVAILABLE = True
except ImportError:
    MSS_AVAILABLE = False

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False


@dataclass
class Region:
    """Screen region definition."""
    x: int
    y: int
    width: int
    height: int

    @property
    def center(self) -> Tuple[int, int]:
        """Get center point of region."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def as_tuple(self) -> Tuple[int, int, int, int]:
        """Return as (x, y, width, height) tuple."""
        return (self.x, self.y, self.width, self.height)

    @property
    def as_mss_monitor(self) -> Dict[str, int]:
        """Return as MSS monitor dict."""
        return {
            "left": self.x,
            "top": self.y,
            "width": self.width,
            "height": self.height
        }

    @classmethod
    def from_dict(cls, data: Dict[str, int]) -> 'Region':
        """Create Region from dictionary."""
        return cls(
            x=data.get("x", 0),
            y=data.get("y", 0),
            width=data.get("width", 0),
            height=data.get("height", 0)
        )

    def to_dict(self) -> Dict[str, int]:
        """Convert to dictionary."""
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height
        }


class ScreenCapture:
    """
    High-performance screen capture with caching.

    Uses MSS for fast capture (~3ms vs ~30ms with pyautogui).
    Supports grayscale conversion and region-based capture.
    """

    _instance: Optional['ScreenCapture'] = None

    def __new__(cls) -> 'ScreenCapture':
        """Singleton pattern for screen capture."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # mss handles and image buffers are per thread: the bot loop, the GUI status panel and the
        # recorder capture concurrently. A shared mss deadlocked, and a shared buffer let one thread
        # overwrite the screenshot another was still reading.
        self._local = threading.local()
        self._last_frame: Optional[np.ndarray] = None
        self._last_frame_time: float = 0
        self._frame_cache_ttl: float = 0.016  # ~60fps max
        self._capture_region: Optional[Region] = None
        self._window_id: Optional[int] = None
        self._capture_backend_name: Optional[str] = None
        self._capture_backend_func: Optional[Callable] = None
        self._initialized = True

    @property
    def _sct(self):
        sct = getattr(self._local, 'sct', None)
        if sct is None and MSS_AVAILABLE:
            sct = mss.mss()
            self._local.sct = sct
        return sct

    @property
    def _buf_bgr(self) -> Optional[np.ndarray]:
        return getattr(self._local, 'buf_bgr', None)

    @_buf_bgr.setter
    def _buf_bgr(self, value: Optional[np.ndarray]) -> None:
        self._local.buf_bgr = value

    @property
    def _buf_gray(self) -> Optional[np.ndarray]:
        return getattr(self._local, 'buf_gray', None)

    @_buf_gray.setter
    def _buf_gray(self, value: Optional[np.ndarray]) -> None:
        self._local.buf_gray = value

    def set_capture_region(self, region: Optional['Region']) -> None:
        """Set fixed capture region (e.g. Tibia window). None for full screen."""
        self._capture_region = region

    def set_capture_window(self, window_id: int, region: 'Region') -> None:
        """Track a window by ID so the region auto-updates when it moves."""
        self._window_id = window_id
        self._capture_region = region

    def clear_capture_window(self) -> None:
        """Stop tracking a window, revert to full screen."""
        self._window_id = None
        self._capture_region = None

    def refresh_capture_region(self) -> None:
        """Re-query the tracked window position. No-op if no window tracked."""
        if self._window_id is None:
            return
        try:
            from ..utils.window import get_window_region
            region = get_window_region(self._window_id)
            if region is not None:
                self._capture_region = region
        except Exception as e:
            print(f"[Screen] Failed to refresh capture region: {e}")

    def get_capture_region(self) -> Optional['Region']:
        """Return current capture region, or None if full screen."""
        return self._capture_region

    def set_capture_backend(self, name: Optional[str], func: Optional[Callable]) -> None:
        """Set an alternative capture backend (e.g. capture card).

        Args:
            name: Backend identifier or None to clear.
            func: Callable(grayscale=False) -> np.ndarray, or None.
        """
        self._capture_backend_name = name
        self._capture_backend_func = func

    def capture(self, region: Optional[Region] = None, grayscale: bool = False) -> np.ndarray:
        """
        Capture screen region.

        Args:
            region: Screen region to capture. None uses stored capture region, or full screen.
            grayscale: Convert to grayscale for faster processing.

        Returns:
            numpy array in BGR format (or grayscale if specified).
        """
        # Use hardware capture backend if set
        if self._capture_backend_func is not None:
            return self._capture_via_backend(region, grayscale)

        effective_region = region or self._capture_region
        if self._sct and MSS_AVAILABLE:
            return self._capture_mss(effective_region, grayscale)
        elif PYAUTOGUI_AVAILABLE:
            return self._capture_pyautogui(effective_region, grayscale)
        else:
            raise RuntimeError("No screen capture backend available")

    def _capture_via_backend(self, region: Optional[Region], grayscale: bool) -> np.ndarray:
        """Capture using the hardware backend (e.g. capture card)."""
        frame = self._capture_backend_func(grayscale=grayscale)
        if frame is None:
            raise RuntimeError(f"Capture backend '{self._capture_backend_name}' returned None")

        effective_region = region or self._capture_region
        if effective_region is not None:
            x, y = effective_region.x, effective_region.y
            w, h = effective_region.width, effective_region.height
            frame = frame[y:y + h, x:x + w]

        if grayscale:
            self._ensure_buffers(frame.shape[0], frame.shape[1])
            cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY, dst=self._buf_gray)
            return self._buf_gray

        return frame

    def _ensure_buffers(self, height: int, width: int) -> None:
        """Lazily allocate or reallocate BGR/gray buffers when dimensions change."""
        if self._buf_bgr is not None and self._buf_bgr.shape[:2] == (height, width):
            return
        self._buf_bgr = np.empty((height, width, 3), dtype=np.uint8)
        self._buf_gray = np.empty((height, width), dtype=np.uint8)

    def _capture_mss(self, region: Optional[Region], grayscale: bool) -> np.ndarray:
        """Capture using MSS (fast)."""
        if region:
            monitor = region.as_mss_monitor
        else:
            monitor = self._sct.monitors[1]

        sct_img = self._sct.grab(monitor)
        bgra = np.array(sct_img)

        h, w = bgra.shape[:2]
        self._ensure_buffers(h, w)

        # MSS returns BGRA - convert like PyTibia does
        if grayscale:
            cv2.cvtColor(bgra, cv2.COLOR_BGRA2GRAY, dst=self._buf_gray)
            return self._buf_gray
        cv2.cvtColor(bgra, cv2.COLOR_BGRA2BGR, dst=self._buf_bgr)
        return self._buf_bgr

    def _capture_pyautogui(self, region: Optional[Region], grayscale: bool) -> np.ndarray:
        """Capture using pyautogui (slower fallback)."""
        if region:
            screenshot = pyautogui.screenshot(region=region.as_tuple)
        else:
            screenshot = pyautogui.screenshot()

        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)

        if grayscale:
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        return img

    def capture_cached(self, region: Optional[Region] = None,
                       grayscale: bool = False,
                       ttl: Optional[float] = None) -> np.ndarray:
        """
        Capture with frame caching.

        Returns cached frame if within TTL to reduce CPU usage.
        """
        current_time = time.time()
        cache_ttl = ttl if ttl is not None else self._frame_cache_ttl

        if (self._last_frame is not None and
            current_time - self._last_frame_time < cache_ttl):
            return self._last_frame

        frame = self.capture(region, grayscale)
        self._last_frame = frame
        self._last_frame_time = current_time

        return frame


def compute_image_hash(img: np.ndarray) -> str:
    """
    Compute fast hash of image for cache comparison.

    Uses downsampled image + md5 for speed vs accuracy balance.
    """
    # Downsample for faster hashing
    small = cv2.resize(img, (16, 16), interpolation=cv2.INTER_AREA)
    return hashlib.md5(small.tobytes()).hexdigest()


@dataclass
class CacheEntry:
    """Cache entry with value, hash, and timestamp."""
    value: Any
    image_hash: str
    timestamp: float


class PositionCache:
    """
    Cache for detected positions.

    Avoids re-running expensive detection if image hasn't changed.
    """

    def __init__(self, ttl: float = 0.5, max_size: int = 100):
        """
        Initialize position cache.

        Args:
            ttl: Time-to-live for cache entries in seconds.
            max_size: Maximum cache entries before cleanup.
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._ttl = ttl
        self._max_size = max_size

    def get(self, key: str, img: np.ndarray) -> Optional[Any]:
        """
        Get cached value if image hasn't changed.

        Args:
            key: Cache key (e.g., function name + args).
            img: Current image to compare hash.

        Returns:
            Cached value or None if cache miss.
        """
        if key not in self._cache:
            return None

        entry = self._cache[key]
        current_time = time.time()

        # Check TTL
        if current_time - entry.timestamp > self._ttl:
            del self._cache[key]
            return None

        # Check image hash
        current_hash = compute_image_hash(img)
        if current_hash != entry.image_hash:
            return None

        return entry.value

    def set(self, key: str, value: Any, img: np.ndarray) -> None:
        """
        Store value in cache with image hash.

        Args:
            key: Cache key.
            value: Value to cache.
            img: Image used to compute hash.
        """
        # Cleanup if needed
        if len(self._cache) >= self._max_size:
            self._cleanup()

        self._cache[key] = CacheEntry(
            value=value,
            image_hash=compute_image_hash(img),
            timestamp=time.time()
        )

    def _cleanup(self) -> None:
        """Remove expired entries."""
        current_time = time.time()
        expired = [
            key for key, entry in self._cache.items()
            if current_time - entry.timestamp > self._ttl
        ]
        for key in expired:
            del self._cache[key]

        # If still too large, remove oldest
        if len(self._cache) >= self._max_size:
            sorted_entries = sorted(
                self._cache.items(),
                key=lambda x: x[1].timestamp
            )
            for key, _ in sorted_entries[:len(sorted_entries) // 2]:
                del self._cache[key]

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()


# Global cache instance
_position_cache = PositionCache()


def cache_position(ttl: float = 0.5):
    """
    Decorator to cache detection results based on image hash.

    Usage:
        @cache_position(ttl=0.5)
        def detect_something(img: np.ndarray) -> Optional[Tuple[int, int]]:
            # expensive detection
            return result

    Args:
        ttl: Cache time-to-live in seconds.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(img: np.ndarray, *args, **kwargs) -> Any:
            # Generate cache key from function name and args
            cache_key = f"{func.__name__}:{args}:{kwargs}"

            # Check cache
            cached = _position_cache.get(cache_key, img)
            if cached is not None:
                return cached

            # Compute and cache
            result = func(img, *args, **kwargs)
            _position_cache.set(cache_key, result, img)

            return result

        return wrapper
    return decorator


def clear_position_cache() -> None:
    """Clear the global position cache."""
    _position_cache.clear()


# Convenience function for getting singleton
def get_screen_capture() -> ScreenCapture:
    """Get the singleton ScreenCapture instance."""
    return ScreenCapture()
