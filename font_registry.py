"""
Font Registry Module for Artistic Video Generation.

This module provides utilities to list available fonts, validate font names,
and retrieve font paths for use in video frame generation.
"""

import os
import random
from pathlib import Path


class FontRegistry:
    """
    Registry for managing and accessing bundled fonts.

    Provides methods to list available fonts, get font paths, and validate
    font names for use in artistic video generation.
    """

    # Common Linux system font directories
    SYSTEM_FONT_DIRS = [
        "/usr/share/fonts",
        "/usr/local/share/fonts",
    ]

    def __init__(self, fonts_dir: str | Path | None = None) -> None:
        """
        Initialize the FontRegistry.

        Args:
            fonts_dir: Path to the fonts directory. If None, uses the default
                      fonts/ directory relative to this module.
        """
        if fonts_dir is None:
            # Default to fonts/ directory relative to this module
            module_dir = Path(__file__).parent
            self.fonts_dir = module_dir / "fonts"
        else:
            self.fonts_dir = Path(fonts_dir)

        # Cache for available fonts (font_name -> font_path)
        self._font_cache: dict[str, Path] | None = None

    def _scan_fonts(self) -> dict[str, Path]:
        """
        Scan the bundled fonts directory and system font directories for TTF files.

        Bundled fonts (in fonts/) take priority over system fonts with the same name.

        Returns:
            Dictionary mapping font names to their file paths.
        """
        if self._font_cache is not None:
            return self._font_cache

        self._font_cache = {}

        # Scan system font directories first (so bundled fonts override them)
        for sys_dir in self.SYSTEM_FONT_DIRS:
            sys_path = Path(sys_dir)
            if sys_path.exists():
                for file_path in sys_path.rglob("*.ttf"):
                    font_name = file_path.stem
                    self._font_cache[font_name] = file_path
                for file_path in sys_path.rglob("*.otf"):
                    font_name = file_path.stem
                    self._font_cache[font_name] = file_path

        # Scan bundled fonts directory (overrides system fonts with same name)
        if self.fonts_dir.exists():
            for file_path in self.fonts_dir.iterdir():
                if file_path.suffix.lower() in (".ttf", ".otf"):
                    font_name = file_path.stem
                    self._font_cache[font_name] = file_path

        return self._font_cache

    def get_available_fonts(self) -> list[str]:
        """
        Get a list of all available font names.

        Returns:
            List of font names (without file extension) available in the fonts directory.
        """
        fonts = self._scan_fonts()
        return sorted(fonts.keys())

    def get_font_path(self, font_name: str) -> str | None:
        """
        Get the absolute path to a font file.

        Args:
            font_name: The name of the font (without .ttf extension).

        Returns:
            Absolute path to the TTF file as a string, or None if font not found.
        """
        fonts = self._scan_fonts()
        font_path = fonts.get(font_name)

        if font_path is not None:
            return str(font_path.absolute())

        return None

    def is_valid_font(self, font_name: str) -> bool:
        """
        Check if a font name is valid (exists in the registry).

        Args:
            font_name: The name of the font to validate.

        Returns:
            True if the font exists, False otherwise.
        """
        fonts = self._scan_fonts()
        return font_name in fonts

    def get_random_font(self) -> str | None:
        """
        Get a random font name from available fonts.

        Returns:
            A randomly selected font name, or None if no fonts are available.
        """
        fonts = self.get_available_fonts()

        if not fonts:
            return None

        return random.choice(fonts)

    def refresh(self) -> None:
        """
        Clear the font cache and rescan the fonts directory.

        Call this method after adding new fonts to pick up changes.
        """
        self._font_cache = None


# Module-level singleton for convenience
_default_registry: FontRegistry | None = None


def get_default_registry() -> FontRegistry:
    """
    Get the default FontRegistry instance (singleton).

    Returns:
        The default FontRegistry instance.
    """
    global _default_registry
    if _default_registry is None:
        _default_registry = FontRegistry()
    return _default_registry


def get_available_fonts() -> list[str]:
    """
    Get a list of all available font names using the default registry.

    Returns:
        List of font names available in the fonts directory.
    """
    return get_default_registry().get_available_fonts()


def get_font_path(font_name: str) -> str | None:
    """
    Get the absolute path to a font file using the default registry.

    Args:
        font_name: The name of the font (without .ttf extension).

    Returns:
        Absolute path to the TTF file, or None if font not found.
    """
    return get_default_registry().get_font_path(font_name)


def is_valid_font(font_name: str) -> bool:
    """
    Check if a font name is valid using the default registry.

    Args:
        font_name: The name of the font to validate.

    Returns:
        True if the font exists, False otherwise.
    """
    return get_default_registry().is_valid_font(font_name)


def get_random_font() -> str | None:
    """
    Get a random font name using the default registry.

    Returns:
        A randomly selected font name, or None if no fonts are available.
    """
    return get_default_registry().get_random_font()
