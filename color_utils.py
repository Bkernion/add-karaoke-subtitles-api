"""
Color Utilities Module for Artistic Video Generation.

This module provides color palette generation with readable, complementary color
combinations for artistic text overlays. All palettes ensure WCAG AA compliance
with a minimum contrast ratio of 4.5:1.
"""

import random
from dataclasses import dataclass


# Type aliases for color representations
RGBColor = tuple[int, int, int]
HexColor = str


@dataclass
class ColorPalette:
    """
    A color palette for artistic video frames.

    Attributes:
        background_color: Primary background color (hex string).
        background_color_2: Secondary background color for gradients (hex string, optional).
        font_color: Text/font color (hex string).
        highlight_color: Optional highlight/accent color (hex string, optional).
        is_gradient: Whether background uses a gradient.
    """

    background_color: HexColor
    background_color_2: HexColor | None
    font_color: HexColor
    highlight_color: HexColor | None
    is_gradient: bool


# Curated base palettes: (bg1, bg2 or None, font, highlight or None)
# All combinations verified for WCAG AA contrast ratio >= 4.5:1
# For gradients, both bg1 and bg2 must have sufficient contrast with font
CURATED_PALETTES: list[tuple[HexColor, HexColor | None, HexColor, HexColor | None]] = [
    # Coral with dark text (contrast 5.5:1)
    ("#FF6B6B", None, "#1A1A1A", "#20B2AA"),
    # Deep blue gradient with white text (both endpoints pass)
    ("#1A237E", "#0D47A1", "#FFFFFF", "#FFD700"),
    # Peach with black text (contrast 9.0:1)
    ("#FFAB91", None, "#1A1A1A", "#4CAF50"),
    # Deep purple with gold (contrast 8.5:1)
    ("#4A148C", None, "#FFD700", "#E040FB"),
    # Dark gradient with white text (both pass)
    ("#1A237E", "#311B92", "#FFFFFF", "#FFD700"),
    # Ocean blue with white (contrast 8.6:1)
    ("#0D47A1", None, "#FFFFFF", "#FFEB3B"),
    # Mint green with dark text (contrast 8.8:1)
    ("#98FB98", None, "#1B4332", "#FF6B6B"),
    # Hot pink with black text (contrast 5.4:1)
    ("#FF1493", None, "#000000", "#FFD700"),
    # Deep teal gradient with cream (both pass)
    ("#004D40", "#00695C", "#FFF8E1", "#FFAB00"),
    # Lavender with dark purple (contrast 7.5:1)
    ("#E1BEE7", None, "#311B92", "#FF4081"),
    # Electric blue with yellow (contrast 4.6:1)
    ("#2962FF", None, "#FFFF00", "#00E676"),
    # Dark maroon gradient with white (both pass)
    ("#4A0000", "#7B1A1A", "#FFFFFF", "#FFD700"),
    # Forest green with cream (contrast 7.7:1)
    ("#1B5E20", None, "#FFFDE7", "#FFAB00"),
    # Navy with coral (contrast 6.3:1)
    ("#0D1B2A", None, "#FF6B6B", "#00E5FF"),
    # Rose gold gradient with dark text (both pass)
    ("#B76E79", "#D4A5A5", "#1A1A1A", "#4A148C"),
]


def hex_to_rgb(hex_color: HexColor) -> RGBColor:
    """
    Convert a hex color string to RGB tuple.

    Args:
        hex_color: Color in hex format (e.g., "#FF5722" or "FF5722").

    Returns:
        Tuple of (red, green, blue) values (0-255).
    """
    hex_color = hex_color.lstrip("#")
    return (
        int(hex_color[0:2], 16),
        int(hex_color[2:4], 16),
        int(hex_color[4:6], 16),
    )


def rgb_to_hex(rgb: RGBColor) -> HexColor:
    """
    Convert an RGB tuple to hex color string.

    Args:
        rgb: Tuple of (red, green, blue) values (0-255).

    Returns:
        Color in hex format (e.g., "#FF5722").
    """
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def get_relative_luminance(rgb: RGBColor) -> float:
    """
    Calculate the relative luminance of a color per WCAG 2.1.

    Args:
        rgb: Tuple of (red, green, blue) values (0-255).

    Returns:
        Relative luminance value between 0 and 1.
    """

    def linearize(value: int) -> float:
        """Convert sRGB component to linear RGB."""
        v = value / 255.0
        if v <= 0.03928:
            return v / 12.92
        return ((v + 0.055) / 1.055) ** 2.4

    r_lin = linearize(rgb[0])
    g_lin = linearize(rgb[1])
    b_lin = linearize(rgb[2])

    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(color1: HexColor, color2: HexColor) -> float:
    """
    Calculate the contrast ratio between two colors per WCAG 2.1.

    Args:
        color1: First color in hex format.
        color2: Second color in hex format.

    Returns:
        Contrast ratio (1:1 to 21:1 range, returned as single float).
    """
    lum1 = get_relative_luminance(hex_to_rgb(color1))
    lum2 = get_relative_luminance(hex_to_rgb(color2))

    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)

    return (lighter + 0.05) / (darker + 0.05)


def is_contrast_sufficient(
    background: HexColor, foreground: HexColor, min_ratio: float = 4.5
) -> bool:
    """
    Check if two colors meet the minimum contrast ratio requirement.

    Args:
        background: Background color in hex format.
        foreground: Foreground (text) color in hex format.
        min_ratio: Minimum contrast ratio (default 4.5 for WCAG AA).

    Returns:
        True if contrast ratio meets or exceeds minimum.
    """
    return calculate_contrast_ratio(background, foreground) >= min_ratio


def generate_complementary_palette(
    prefer_gradient: bool | None = None,
) -> ColorPalette:
    """
    Generate a random complementary color palette from curated options.

    All returned palettes ensure a minimum contrast ratio of 4.5:1 between
    background and font colors for WCAG AA readability compliance.

    Args:
        prefer_gradient: If True, prefer gradient backgrounds.
                        If False, prefer solid backgrounds.
                        If None, randomly choose.

    Returns:
        A ColorPalette with background, font, and optional highlight colors.
    """
    # Filter palettes based on gradient preference
    if prefer_gradient is True:
        filtered = [p for p in CURATED_PALETTES if p[1] is not None]
    elif prefer_gradient is False:
        filtered = [p for p in CURATED_PALETTES if p[1] is None]
    else:
        filtered = CURATED_PALETTES

    # Fall back to all palettes if filter returns empty
    if not filtered:
        filtered = CURATED_PALETTES

    # Select a random palette
    bg1, bg2, font, highlight = random.choice(filtered)

    return ColorPalette(
        background_color=bg1,
        background_color_2=bg2,
        font_color=font,
        highlight_color=highlight,
        is_gradient=bg2 is not None,
    )


def get_all_palettes() -> list[ColorPalette]:
    """
    Get all curated color palettes.

    Returns:
        List of all available ColorPalette objects.
    """
    return [
        ColorPalette(
            background_color=bg1,
            background_color_2=bg2,
            font_color=font,
            highlight_color=highlight,
            is_gradient=bg2 is not None,
        )
        for bg1, bg2, font, highlight in CURATED_PALETTES
    ]


def get_solid_palettes() -> list[ColorPalette]:
    """
    Get all curated palettes with solid backgrounds.

    Returns:
        List of ColorPalette objects with solid backgrounds.
    """
    return [p for p in get_all_palettes() if not p.is_gradient]


def get_gradient_palettes() -> list[ColorPalette]:
    """
    Get all curated palettes with gradient backgrounds.

    Returns:
        List of ColorPalette objects with gradient backgrounds.
    """
    return [p for p in get_all_palettes() if p.is_gradient]
