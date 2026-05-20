"""
Platform-aware image resolution.

Resolves template images with platform-specific overrides.
On win32, looks for images in `images/win32/` first, then falls back to `images/`.
On darwin/linux, uses default `images/` paths directly.
"""
import sys
import pathlib

PLATFORM = sys.platform  # 'darwin', 'win32', 'linux'


def resolve_image(images_path, relative):
    """Resolve image path with platform-specific override.

    Checks `images_path/PLATFORM/relative` first.
    Falls back to `images_path/relative`.
    """
    platform_path = images_path / PLATFORM / relative
    if platform_path.exists():
        return platform_path
    return images_path / relative


def resolve_directory(images_path, subdir):
    """Resolve directory with platform override."""
    platform_dir = images_path / PLATFORM / subdir
    if platform_dir.exists():
        return platform_dir
    return images_path / subdir


def glob_images(images_path, subdir, pattern="*.png"):
    """Glob images from platform dir if exists, else default dir."""
    platform_dir = images_path / PLATFORM / subdir
    if platform_dir.exists() and any(platform_dir.glob(pattern)):
        return list(platform_dir.glob(pattern))
    default_dir = images_path / subdir
    if default_dir.exists():
        return list(default_dir.glob(pattern))
    return []
