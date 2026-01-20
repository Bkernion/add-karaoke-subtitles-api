"""
Style Randomization Engine for Artistic Video Generation.

This module provides an engine that generates random but cohesive style choices
for each frame in an artistic word-by-word video. It integrates with the font
registry and color utilities to produce visually appealing combinations.
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from color_utils import ColorPalette, generate_complementary_palette
from font_registry import get_available_fonts, get_random_font


class TextPosition(Enum):
    """Predefined text position options for frame layout."""

    CENTER = "center"
    TOP_THIRD = "top_third"
    BOTTOM_THIRD = "bottom_third"
    LEFT_OFFSET = "left_offset"
    RIGHT_OFFSET = "right_offset"


class HighlightStyle(Enum):
    """Highlight styles for text emphasis."""

    NONE = "none"
    BOX = "box"
    BRUSH = "brush"


class GradientDirection(Enum):
    """Gradient direction options for backgrounds."""

    VERTICAL = "vertical"
    HORIZONTAL = "horizontal"
    DIAGONAL = "diagonal"


BackgroundType = Literal["solid", "gradient"]


@dataclass
class FrameStyle:
    """
    Complete style specification for a single video frame.

    Attributes:
        font_name: Name of the font to use (from font registry).
        font_size: Size of the font in pixels.
        font_color: Hex color string for the text.
        background_type: Either 'solid' or 'gradient'.
        background_colors: List of 1 (solid) or 2 (gradient) hex colors.
        gradient_direction: Direction for gradient (if applicable).
        text_position: Position preset for text placement.
        text_position_xy: Exact (x, y) coordinates as percentages (0.0-1.0).
        text_rotation: Rotation angle in degrees.
        highlight_style: Style of text highlight/emphasis.
        highlight_color: Hex color for highlight (if applicable).
        highlight_padding: Padding around text for highlight in pixels.
        shadow_enabled: Whether drop shadow is enabled.
        shadow_offset: Shadow offset (x, y) in pixels.
        shadow_blur: Shadow blur radius in pixels.
        shadow_color: Hex color for shadow.
        glow_enabled: Whether glow effect is enabled.
        glow_radius: Glow effect radius in pixels.
        glow_color: Hex color for glow effect.
    """

    font_name: str
    font_size: int
    font_color: str
    background_type: BackgroundType
    background_colors: list[str]
    gradient_direction: GradientDirection | None
    text_position: TextPosition
    text_position_xy: tuple[float, float]
    text_rotation: float
    highlight_style: HighlightStyle
    highlight_color: str | None
    highlight_padding: int
    shadow_enabled: bool
    shadow_offset: tuple[int, int]
    shadow_blur: int
    shadow_color: str
    glow_enabled: bool
    glow_radius: int
    glow_color: str


# Position presets as (x%, y%) percentages
POSITION_PRESETS: dict[TextPosition, tuple[float, float]] = {
    TextPosition.CENTER: (0.5, 0.5),
    TextPosition.TOP_THIRD: (0.5, 0.33),
    TextPosition.BOTTOM_THIRD: (0.5, 0.67),
    TextPosition.LEFT_OFFSET: (0.35, 0.5),
    TextPosition.RIGHT_OFFSET: (0.65, 0.5),
}


# Font size ranges
MIN_FONT_SIZE = 80
MAX_FONT_SIZE = 200
# Characters per frame width at max font size (for scaling)
CHARS_AT_MAX_SIZE = 6


class StyleEngine:
    """
    Engine for generating randomized but cohesive frame styles.

    Integrates with FontRegistry and ColorPalette to generate visually
    appealing style combinations for artistic word videos.
    """

    def __init__(
        self,
        base_font_size_range: tuple[int, int] = (MIN_FONT_SIZE, MAX_FONT_SIZE),
        rotation_range: tuple[float, float] = (-15.0, 15.0),
        shadow_probability: float = 0.4,
        glow_probability: float = 0.3,
        highlight_probability: float = 0.35,
        gradient_probability: float = 0.4,
    ) -> None:
        """
        Initialize the StyleEngine with customizable parameters.

        Args:
            base_font_size_range: Min and max font size in pixels.
            rotation_range: Min and max rotation angle in degrees.
            shadow_probability: Probability of enabling shadow (0.0-1.0).
            glow_probability: Probability of enabling glow (0.0-1.0).
            highlight_probability: Probability of adding highlight (0.0-1.0).
            gradient_probability: Probability of gradient vs solid bg (0.0-1.0).
        """
        self.base_font_size_range = base_font_size_range
        self.rotation_range = rotation_range
        self.shadow_probability = shadow_probability
        self.glow_probability = glow_probability
        self.highlight_probability = highlight_probability
        self.gradient_probability = gradient_probability

    def _calculate_font_size(self, word: str) -> int:
        """
        Calculate appropriate font size based on word length.

        Longer words get smaller fonts to ensure they fit within frame bounds.

        Args:
            word: The word to be displayed.

        Returns:
            Font size in pixels, scaled for word length.
        """
        min_size, max_size = self.base_font_size_range
        word_length = len(word)

        if word_length <= CHARS_AT_MAX_SIZE:
            # Short words can use full size range
            return random.randint(min_size, max_size)

        # Scale down for longer words
        # Reduce max size proportionally to word length
        scale_factor = CHARS_AT_MAX_SIZE / word_length
        adjusted_max = max(min_size, int(max_size * scale_factor))

        return random.randint(min_size, adjusted_max)

    def _generate_position(self) -> tuple[TextPosition, tuple[float, float]]:
        """
        Generate a random text position.

        Returns:
            Tuple of (TextPosition preset, (x, y) percentages).
        """
        position = random.choice(list(TextPosition))
        base_x, base_y = POSITION_PRESETS[position]

        # Add slight random variation (±5%)
        x = base_x + random.uniform(-0.05, 0.05)
        y = base_y + random.uniform(-0.05, 0.05)

        # Clamp to valid range
        x = max(0.1, min(0.9, x))
        y = max(0.1, min(0.9, y))

        return position, (x, y)

    def _generate_rotation(self) -> float:
        """
        Generate a random rotation angle.

        Returns:
            Rotation angle in degrees.
        """
        min_rot, max_rot = self.rotation_range
        return round(random.uniform(min_rot, max_rot), 1)

    def _generate_shadow_style(
        self, palette: ColorPalette
    ) -> tuple[bool, tuple[int, int], int, str]:
        """
        Generate shadow settings.

        Args:
            palette: Color palette for color coordination.

        Returns:
            Tuple of (enabled, offset, blur, color).
        """
        enabled = random.random() < self.shadow_probability

        if not enabled:
            return False, (0, 0), 0, "#000000"

        # Random shadow offset (2-8 pixels)
        offset_x = random.randint(2, 8)
        offset_y = random.randint(2, 8)

        # Random blur (0-6 pixels)
        blur = random.randint(0, 6)

        # Shadow color - typically darker version or black with transparency
        shadow_color = "#000000"

        return True, (offset_x, offset_y), blur, shadow_color

    def _generate_glow_style(
        self, palette: ColorPalette
    ) -> tuple[bool, int, str]:
        """
        Generate glow effect settings.

        Args:
            palette: Color palette for color coordination.

        Returns:
            Tuple of (enabled, radius, color).
        """
        enabled = random.random() < self.glow_probability

        if not enabled:
            return False, 0, "#FFFFFF"

        # Random glow radius (3-12 pixels)
        radius = random.randint(3, 12)

        # Glow color - use highlight color or font color
        glow_color = palette.highlight_color or palette.font_color

        return True, radius, glow_color

    def _generate_highlight_style(
        self, palette: ColorPalette
    ) -> tuple[HighlightStyle, str | None, int]:
        """
        Generate highlight/emphasis settings.

        Args:
            palette: Color palette for color coordination.

        Returns:
            Tuple of (style, color, padding).
        """
        if random.random() >= self.highlight_probability:
            return HighlightStyle.NONE, None, 0

        # Choose between box and brush styles
        style = random.choice([HighlightStyle.BOX, HighlightStyle.BRUSH])

        # Use highlight color from palette, or generate complementary
        highlight_color = palette.highlight_color

        # Random padding (10-30 pixels)
        padding = random.randint(10, 30)

        return style, highlight_color, padding

    def generate_frame_style(self, word: str | None = None) -> FrameStyle:
        """
        Generate a complete random style for a video frame.

        Args:
            word: The word to be displayed (used for font size calculation).
                  If None, uses default sizing.

        Returns:
            FrameStyle dataclass with all style parameters.
        """
        # Get a random font
        font_name = get_random_font()
        if font_name is None:
            # Fallback if no fonts available
            font_name = "Arial"

        # Calculate font size based on word length
        if word:
            font_size = self._calculate_font_size(word)
        else:
            font_size = random.randint(*self.base_font_size_range)

        # Decide on gradient vs solid background
        use_gradient = random.random() < self.gradient_probability

        # Get color palette
        palette = generate_complementary_palette(prefer_gradient=use_gradient)

        # Build background colors list
        if palette.is_gradient and palette.background_color_2:
            background_type: BackgroundType = "gradient"
            background_colors = [palette.background_color, palette.background_color_2]
            gradient_direction = random.choice(list(GradientDirection))
        else:
            background_type = "solid"
            background_colors = [palette.background_color]
            gradient_direction = None

        # Generate position
        text_position, text_position_xy = self._generate_position()

        # Generate rotation
        text_rotation = self._generate_rotation()

        # Generate effects
        shadow_enabled, shadow_offset, shadow_blur, shadow_color = (
            self._generate_shadow_style(palette)
        )
        glow_enabled, glow_radius, glow_color = self._generate_glow_style(palette)
        highlight_style, highlight_color, highlight_padding = (
            self._generate_highlight_style(palette)
        )

        return FrameStyle(
            font_name=font_name,
            font_size=font_size,
            font_color=palette.font_color,
            background_type=background_type,
            background_colors=background_colors,
            gradient_direction=gradient_direction,
            text_position=text_position,
            text_position_xy=text_position_xy,
            text_rotation=text_rotation,
            highlight_style=highlight_style,
            highlight_color=highlight_color,
            highlight_padding=highlight_padding,
            shadow_enabled=shadow_enabled,
            shadow_offset=shadow_offset,
            shadow_blur=shadow_blur,
            shadow_color=shadow_color,
            glow_enabled=glow_enabled,
            glow_radius=glow_radius,
            glow_color=glow_color,
        )

    def generate_styles_for_words(
        self, words: list[str], coherent: bool = False
    ) -> list[FrameStyle]:
        """
        Generate styles for a list of words.

        Args:
            words: List of words to generate styles for.
            coherent: If True, uses same palette for all frames (varies position/effects).

        Returns:
            List of FrameStyle objects, one per word.
        """
        if not words:
            return []

        if not coherent:
            # Fully random styles for each word
            return [self.generate_frame_style(word) for word in words]

        # Coherent mode: same palette, different positions and effects
        palette = generate_complementary_palette()
        styles = []

        for word in words:
            # Generate individual style but override colors from shared palette
            style = self.generate_frame_style(word)

            # Override colors to use shared palette
            if palette.is_gradient and palette.background_color_2:
                background_colors = [palette.background_color, palette.background_color_2]
                background_type: BackgroundType = "gradient"
            else:
                background_colors = [palette.background_color]
                background_type = "solid"

            # Create new style with shared colors
            coherent_style = FrameStyle(
                font_name=style.font_name,
                font_size=style.font_size,
                font_color=palette.font_color,
                background_type=background_type,
                background_colors=background_colors,
                gradient_direction=style.gradient_direction,
                text_position=style.text_position,
                text_position_xy=style.text_position_xy,
                text_rotation=style.text_rotation,
                highlight_style=style.highlight_style,
                highlight_color=palette.highlight_color,
                highlight_padding=style.highlight_padding,
                shadow_enabled=style.shadow_enabled,
                shadow_offset=style.shadow_offset,
                shadow_blur=style.shadow_blur,
                shadow_color=style.shadow_color,
                glow_enabled=style.glow_enabled,
                glow_radius=style.glow_radius,
                glow_color=palette.highlight_color or palette.font_color,
            )
            styles.append(coherent_style)

        return styles


# Module-level convenience instance
_default_engine: StyleEngine | None = None


def get_default_engine() -> StyleEngine:
    """
    Get the default StyleEngine instance (singleton).

    Returns:
        The default StyleEngine instance.
    """
    global _default_engine
    if _default_engine is None:
        _default_engine = StyleEngine()
    return _default_engine


def generate_frame_style(word: str | None = None) -> FrameStyle:
    """
    Generate a frame style using the default engine.

    Args:
        word: The word to be displayed (for font size calculation).

    Returns:
        FrameStyle with all styling parameters.
    """
    return get_default_engine().generate_frame_style(word)


def generate_styles_for_words(
    words: list[str], coherent: bool = False
) -> list[FrameStyle]:
    """
    Generate styles for a list of words using the default engine.

    Args:
        words: List of words to generate styles for.
        coherent: If True, uses same color palette for all frames.

    Returns:
        List of FrameStyle objects, one per word.
    """
    return get_default_engine().generate_styles_for_words(words, coherent)
