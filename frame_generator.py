"""
Artistic Frame Generator Module for Word-by-Word Video Generation.

This module provides frame generation capabilities using Pillow (PIL) to create
styled image frames with text on solid color backgrounds. It integrates with
the font registry and style engine for artistic video creation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from PIL import Image, ImageDraw, ImageFont

from color_utils import hex_to_rgb
from font_registry import get_font_path
from style_engine import FrameStyle, GradientDirection, HighlightStyle, TextPosition


class AspectRatio(Enum):
    """Supported video aspect ratios with their dimensions."""

    PORTRAIT = "9:16"  # 1080x1920 - Instagram Reels, TikTok
    SQUARE = "1:1"  # 1080x1080 - Instagram Posts
    LANDSCAPE = "16:9"  # 1920x1080 - YouTube, Desktop


# Dimension presets for each aspect ratio
DIMENSIONS: dict[AspectRatio, tuple[int, int]] = {
    AspectRatio.PORTRAIT: (1080, 1920),
    AspectRatio.SQUARE: (1080, 1080),
    AspectRatio.LANDSCAPE: (1920, 1080),
}

# String format to AspectRatio mapping
FORMAT_TO_RATIO: dict[str, AspectRatio] = {
    "9:16": AspectRatio.PORTRAIT,
    "1:1": AspectRatio.SQUARE,
    "16:9": AspectRatio.LANDSCAPE,
}


@dataclass
class FrameDimensions:
    """
    Dimensions for a video frame.

    Attributes:
        width: Frame width in pixels.
        height: Frame height in pixels.
    """

    width: int
    height: int

    @classmethod
    def from_aspect_ratio(cls, ratio: AspectRatio) -> "FrameDimensions":
        """
        Create FrameDimensions from an AspectRatio.

        Args:
            ratio: The aspect ratio to use.

        Returns:
            FrameDimensions with appropriate width and height.
        """
        width, height = DIMENSIONS[ratio]
        return cls(width=width, height=height)

    @classmethod
    def from_format_string(cls, format_str: str) -> "FrameDimensions":
        """
        Create FrameDimensions from a format string.

        Args:
            format_str: Format string like "9:16", "1:1", or "16:9".

        Returns:
            FrameDimensions with appropriate width and height.

        Raises:
            ValueError: If format string is not recognized.
        """
        ratio = FORMAT_TO_RATIO.get(format_str)
        if ratio is None:
            valid_formats = ", ".join(FORMAT_TO_RATIO.keys())
            raise ValueError(
                f"Unknown format '{format_str}'. Valid formats: {valid_formats}"
            )
        return cls.from_aspect_ratio(ratio)


class FrameGenerator:
    """
    Generator for artistic video frames with styled text.

    Uses Pillow (PIL) to create image frames with text on solid color
    backgrounds. Supports custom fonts, positioning, and various text styles.
    """

    def __init__(self, default_dimensions: FrameDimensions | None = None) -> None:
        """
        Initialize the FrameGenerator.

        Args:
            default_dimensions: Default frame dimensions to use if not specified
                               in generate_frame(). Defaults to 9:16 portrait.
        """
        if default_dimensions is None:
            default_dimensions = FrameDimensions.from_aspect_ratio(AspectRatio.PORTRAIT)
        self.default_dimensions = default_dimensions

        # Cache for loaded fonts
        self._font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}

    def _get_font(
        self, font_name: str, font_size: int
    ) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
        """
        Get a PIL font object, with caching.

        Args:
            font_name: Name of the font from font registry.
            font_size: Size of the font in pixels.

        Returns:
            PIL ImageFont object.
        """
        cache_key = (font_name, font_size)

        if cache_key in self._font_cache:
            return self._font_cache[cache_key]

        # Try to get font from registry
        font_path = get_font_path(font_name)

        if font_path is not None:
            try:
                font = ImageFont.truetype(font_path, font_size)
                self._font_cache[cache_key] = font
                return font
            except OSError:
                # Font file exists but couldn't be loaded
                pass

        # Fallback to default font
        try:
            # Try common system fonts
            for fallback in ["Arial.ttf", "DejaVuSans.ttf", "FreeSans.ttf"]:
                try:
                    font = ImageFont.truetype(fallback, font_size)
                    self._font_cache[cache_key] = font
                    return font
                except OSError:
                    continue
        except Exception:
            pass

        # Ultimate fallback to PIL default font (scaled won't work, use load_default)
        font = ImageFont.load_default()
        # Note: load_default() returns a font that can't be resized
        # For production, fonts should be available from font_registry
        return font

    def _create_solid_background(
        self, dimensions: FrameDimensions, color: str
    ) -> Image.Image:
        """
        Create a solid color background image.

        Args:
            dimensions: Frame dimensions.
            color: Hex color string for background.

        Returns:
            PIL Image with solid color background.
        """
        rgb = hex_to_rgb(color)
        return Image.new("RGB", (dimensions.width, dimensions.height), rgb)

    def _create_gradient_background(
        self,
        dimensions: FrameDimensions,
        color1: str,
        color2: str,
        direction: GradientDirection | None = None,
    ) -> Image.Image:
        """
        Create a gradient background image.

        Args:
            dimensions: Frame dimensions.
            color1: First color in hex format (start of gradient).
            color2: Second color in hex format (end of gradient).
            direction: Gradient direction. Defaults to vertical if None.

        Returns:
            PIL Image with gradient background.
        """
        if direction is None:
            direction = GradientDirection.VERTICAL

        rgb1 = hex_to_rgb(color1)
        rgb2 = hex_to_rgb(color2)

        # Create base image
        image = Image.new("RGB", (dimensions.width, dimensions.height))

        if direction == GradientDirection.VERTICAL:
            # Gradient from top to bottom
            for y in range(dimensions.height):
                ratio = y / (dimensions.height - 1) if dimensions.height > 1 else 0
                r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * ratio)
                g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * ratio)
                b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * ratio)
                for x in range(dimensions.width):
                    image.putpixel((x, y), (r, g, b))

        elif direction == GradientDirection.HORIZONTAL:
            # Gradient from left to right
            for x in range(dimensions.width):
                ratio = x / (dimensions.width - 1) if dimensions.width > 1 else 0
                r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * ratio)
                g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * ratio)
                b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * ratio)
                for y in range(dimensions.height):
                    image.putpixel((x, y), (r, g, b))

        elif direction == GradientDirection.DIAGONAL:
            # Diagonal gradient (top-left to bottom-right)
            max_distance = dimensions.width + dimensions.height - 2
            for y in range(dimensions.height):
                for x in range(dimensions.width):
                    # Distance from top-left corner
                    distance = x + y
                    ratio = distance / max_distance if max_distance > 0 else 0
                    r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * ratio)
                    g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * ratio)
                    b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * ratio)
                    image.putpixel((x, y), (r, g, b))

        return image

    def _calculate_text_position(
        self,
        dimensions: FrameDimensions,
        text_bbox: tuple[int, int, int, int],
        style: FrameStyle,
    ) -> tuple[int, int]:
        """
        Calculate the position to draw text based on style settings.

        Args:
            dimensions: Frame dimensions.
            text_bbox: Bounding box of text (left, top, right, bottom).
            style: Frame style with position information.

        Returns:
            Tuple of (x, y) pixel coordinates for text anchor point.
        """
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Get position percentages from style
        pos_x_pct, pos_y_pct = style.text_position_xy

        # Calculate center point based on percentages
        center_x = int(dimensions.width * pos_x_pct)
        center_y = int(dimensions.height * pos_y_pct)

        # Adjust to top-left corner for PIL's text drawing
        x = center_x - text_width // 2
        y = center_y - text_height // 2

        # Ensure text stays within frame bounds with padding
        padding = 20
        x = max(padding, min(x, dimensions.width - text_width - padding))
        y = max(padding, min(y, dimensions.height - text_height - padding))

        return x, y

    def _draw_highlight_box(
        self,
        draw: ImageDraw.ImageDraw,
        text_x: int,
        text_y: int,
        text_bbox: tuple[int, int, int, int],
        color: str,
        padding: int,
    ) -> None:
        """
        Draw a rectangular highlight box behind text.

        Args:
            draw: PIL ImageDraw object.
            text_x: X position of text.
            text_y: Y position of text.
            text_bbox: Bounding box of text (left, top, right, bottom) relative to (0,0).
            color: Hex color string for highlight.
            padding: Padding around text in pixels.
        """
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Calculate highlight box coordinates with padding
        box_left = text_x - padding
        box_top = text_y - padding
        box_right = text_x + text_width + padding
        box_bottom = text_y + text_height + padding

        rgb = hex_to_rgb(color)
        draw.rectangle([box_left, box_top, box_right, box_bottom], fill=rgb)

    def _draw_highlight_brush(
        self,
        draw: ImageDraw.ImageDraw,
        text_x: int,
        text_y: int,
        text_bbox: tuple[int, int, int, int],
        color: str,
        padding: int,
    ) -> None:
        """
        Draw an angled parallelogram highlight (brush stroke style) behind text.

        Args:
            draw: PIL ImageDraw object.
            text_x: X position of text.
            text_y: Y position of text.
            text_bbox: Bounding box of text (left, top, right, bottom) relative to (0,0).
            color: Hex color string for highlight.
            padding: Padding around text in pixels.
        """
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Calculate base rectangle coordinates with padding
        left = text_x - padding
        top = text_y - padding
        right = text_x + text_width + padding
        bottom = text_y + text_height + padding

        # Skew amount for parallelogram (based on height for consistent angle)
        skew = int((bottom - top) * 0.25)

        # Create parallelogram points (skewed to the right at the top)
        # Points are: top-left, top-right, bottom-right, bottom-left
        points = [
            (left + skew, top),      # top-left (shifted right)
            (right + skew, top),     # top-right (shifted right)
            (right, bottom),         # bottom-right
            (left, bottom),          # bottom-left
        ]

        rgb = hex_to_rgb(color)
        draw.polygon(points, fill=rgb)

    def generate_frame(
        self,
        word: str,
        style: FrameStyle,
        dimensions: FrameDimensions | None = None,
    ) -> Image.Image:
        """
        Generate a single frame with styled text.

        Args:
            word: The word to display on the frame.
            style: FrameStyle containing all styling parameters.
            dimensions: Optional frame dimensions. Uses default if not specified.

        Returns:
            PIL Image object with the rendered frame.
        """
        if dimensions is None:
            dimensions = self.default_dimensions

        # Create background (solid or gradient based on style)
        if (
            style.background_type == "gradient"
            and len(style.background_colors) >= 2
        ):
            image = self._create_gradient_background(
                dimensions,
                style.background_colors[0],
                style.background_colors[1],
                style.gradient_direction,
            )
        else:
            background_color = style.background_colors[0]
            image = self._create_solid_background(dimensions, background_color)

        # Create drawing context
        draw = ImageDraw.Draw(image)

        # Get font
        font = self._get_font(style.font_name, style.font_size)

        # Get text bounding box for positioning
        text_bbox_raw = draw.textbbox((0, 0), word, font=font)
        # Convert to int tuple for type safety
        text_bbox = (
            int(text_bbox_raw[0]),
            int(text_bbox_raw[1]),
            int(text_bbox_raw[2]),
            int(text_bbox_raw[3]),
        )

        # Calculate position
        x, y = self._calculate_text_position(dimensions, text_bbox, style)

        # Get font color
        font_color = hex_to_rgb(style.font_color)

        # Draw highlight behind text if enabled
        if style.highlight_style != HighlightStyle.NONE and style.highlight_color:
            if style.highlight_style == HighlightStyle.BOX:
                self._draw_highlight_box(
                    draw, x, y, text_bbox, style.highlight_color, style.highlight_padding
                )
            elif style.highlight_style == HighlightStyle.BRUSH:
                self._draw_highlight_brush(
                    draw, x, y, text_bbox, style.highlight_color, style.highlight_padding
                )

        # Draw the text
        # Note: Rotation, shadows, and glow are handled in later user stories
        draw.text((x, y), word, font=font, fill=font_color)

        return image

    def generate_frames_for_words(
        self,
        words: list[str],
        styles: list[FrameStyle],
        dimensions: FrameDimensions | None = None,
    ) -> list[Image.Image]:
        """
        Generate frames for a list of words with corresponding styles.

        Args:
            words: List of words to display.
            styles: List of FrameStyle objects (must match length of words).
            dimensions: Optional frame dimensions for all frames.

        Returns:
            List of PIL Image objects.

        Raises:
            ValueError: If words and styles lists have different lengths.
        """
        if len(words) != len(styles):
            raise ValueError(
                f"Number of words ({len(words)}) must match number of styles ({len(styles)})"
            )

        return [
            self.generate_frame(word, style, dimensions)
            for word, style in zip(words, styles)
        ]


# Module-level convenience instance
_default_generator: FrameGenerator | None = None


def get_default_generator() -> FrameGenerator:
    """
    Get the default FrameGenerator instance (singleton).

    Returns:
        The default FrameGenerator instance.
    """
    global _default_generator
    if _default_generator is None:
        _default_generator = FrameGenerator()
    return _default_generator


def generate_frame(
    word: str,
    style: FrameStyle,
    dimensions: FrameDimensions | None = None,
) -> Image.Image:
    """
    Generate a frame using the default generator.

    Args:
        word: The word to display on the frame.
        style: FrameStyle containing all styling parameters.
        dimensions: Optional frame dimensions.

    Returns:
        PIL Image object with the rendered frame.
    """
    return get_default_generator().generate_frame(word, style, dimensions)


def generate_frames_for_words(
    words: list[str],
    styles: list[FrameStyle],
    dimensions: FrameDimensions | None = None,
) -> list[Image.Image]:
    """
    Generate frames for a list of words using the default generator.

    Args:
        words: List of words to display.
        styles: List of FrameStyle objects.
        dimensions: Optional frame dimensions for all frames.

    Returns:
        List of PIL Image objects.
    """
    return get_default_generator().generate_frames_for_words(words, styles, dimensions)
