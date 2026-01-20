"""
Artistic Frame Generator Module for Word-by-Word Video Generation.

This module provides frame generation capabilities using Pillow (PIL) to create
styled image frames with text on solid color backgrounds. It integrates with
the font registry and style engine for artistic video creation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal

from PIL import Image, ImageDraw, ImageFilter, ImageFont

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
        rotated_size: tuple[int, int] | None = None,
    ) -> tuple[int, int]:
        """
        Calculate the position to draw text based on style settings.

        Args:
            dimensions: Frame dimensions.
            text_bbox: Bounding box of text (left, top, right, bottom).
            style: Frame style with position information.
            rotated_size: If provided, the (width, height) of rotated text layer
                         to use for bounds calculation instead of text_bbox.

        Returns:
            Tuple of (x, y) pixel coordinates for text anchor point.
        """
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # For bounds checking, use rotated size if provided
        if rotated_size is not None:
            bounds_width, bounds_height = rotated_size
        else:
            bounds_width, bounds_height = text_width, text_height

        # Get position percentages from style
        pos_x_pct, pos_y_pct = style.text_position_xy

        # Calculate center point based on percentages
        center_x = int(dimensions.width * pos_x_pct)
        center_y = int(dimensions.height * pos_y_pct)

        # Adjust to top-left corner for PIL's text drawing
        x = center_x - bounds_width // 2
        y = center_y - bounds_height // 2

        # Ensure text stays within frame bounds with padding
        padding = 20
        x = max(padding, min(x, dimensions.width - bounds_width - padding))
        y = max(padding, min(y, dimensions.height - bounds_height - padding))

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

    def _create_rotated_highlight_layer(
        self,
        word: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        text_bbox: tuple[int, int, int, int],
        style: FrameStyle,
        rotated_size: tuple[int, int],
    ) -> Image.Image:
        """
        Create a rotated highlight layer for text.

        Args:
            word: The text to highlight.
            font: PIL font object.
            text_bbox: Bounding box of text (left, top, right, bottom) relative to (0,0).
            style: Frame style with highlight settings.
            rotated_size: Size of the rotated text layer.

        Returns:
            PIL Image with rotated highlight (RGBA with transparency).
        """
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        padding = style.highlight_padding

        # Create layer sized for the highlight box
        layer_width = text_width + padding * 2
        layer_height = text_height + padding * 2

        # Add extra space for rotation
        max_dim = int((layer_width**2 + layer_height**2) ** 0.5) + 20
        highlight_layer = Image.new("RGBA", (max_dim, max_dim), (0, 0, 0, 0))
        draw = ImageDraw.Draw(highlight_layer)

        # Calculate centered position for highlight
        center_x = max_dim // 2
        center_y = max_dim // 2
        box_left = center_x - text_width // 2 - padding
        box_top = center_y - text_height // 2 - padding
        box_right = center_x + text_width // 2 + padding
        box_bottom = center_y + text_height // 2 + padding

        rgb = hex_to_rgb(style.highlight_color) if style.highlight_color else (128, 128, 128)

        if style.highlight_style == HighlightStyle.BOX:
            draw.rectangle([box_left, box_top, box_right, box_bottom], fill=rgb)
        elif style.highlight_style == HighlightStyle.BRUSH:
            # Create parallelogram
            skew = int((box_bottom - box_top) * 0.25)
            points = [
                (box_left + skew, box_top),
                (box_right + skew, box_top),
                (box_right, box_bottom),
                (box_left, box_bottom),
            ]
            draw.polygon(points, fill=rgb)

        # Rotate the highlight layer
        if style.text_rotation != 0:
            highlight_layer = highlight_layer.rotate(
                style.text_rotation, resample=Image.Resampling.BICUBIC, expand=True
            )

        return highlight_layer

    def _create_shadow_layer(
        self,
        word: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        text_x: int,
        text_y: int,
        shadow_offset: tuple[int, int],
        shadow_blur: int,
        shadow_color: str,
        dimensions: "FrameDimensions",
    ) -> Image.Image:
        """
        Create a shadow layer for text.

        Args:
            word: The text to create shadow for.
            font: PIL font object.
            text_x: X position of the original text.
            text_y: Y position of the original text.
            shadow_offset: (x, y) offset for shadow in pixels.
            shadow_blur: Blur radius for shadow in pixels.
            shadow_color: Hex color for shadow.
            dimensions: Frame dimensions.

        Returns:
            PIL Image with shadow layer (RGBA with transparency).
        """
        # Create transparent layer for shadow
        shadow_layer = Image.new(
            "RGBA", (dimensions.width, dimensions.height), (0, 0, 0, 0)
        )
        shadow_draw = ImageDraw.Draw(shadow_layer)

        # Draw shadow text at offset position
        shadow_x = text_x + shadow_offset[0]
        shadow_y = text_y + shadow_offset[1]

        rgb = hex_to_rgb(shadow_color)
        # Use semi-transparent shadow for softer effect
        shadow_rgba = (*rgb, 180)

        shadow_draw.text((shadow_x, shadow_y), word, font=font, fill=shadow_rgba)

        # Apply blur if specified
        if shadow_blur > 0:
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(shadow_blur))

        return shadow_layer

    def _create_rotated_text_layer(
        self,
        word: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        text_color: tuple[int, int, int] | tuple[int, int, int, int],
        rotation: float,
    ) -> Image.Image:
        """
        Create a rotated text layer on transparent background.

        Args:
            word: The text to render.
            font: PIL font object.
            text_color: RGB or RGBA color tuple for text.
            rotation: Rotation angle in degrees (positive = counter-clockwise).

        Returns:
            PIL Image with rotated text (RGBA with transparency).
        """
        # Create a temporary image to measure text size
        temp_img = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
        temp_draw = ImageDraw.Draw(temp_img)
        text_bbox = temp_draw.textbbox((0, 0), word, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]

        # Add padding for rotation (text expands when rotated)
        # Use diagonal as maximum possible expansion
        max_dim = int((text_width**2 + text_height**2) ** 0.5) + 20
        layer_size = (max_dim, max_dim)

        # Create transparent layer for text
        text_layer = Image.new("RGBA", layer_size, (0, 0, 0, 0))
        text_draw = ImageDraw.Draw(text_layer)

        # Draw text centered in the layer
        text_x = (layer_size[0] - text_width) // 2 - text_bbox[0]
        text_y = (layer_size[1] - text_height) // 2 - text_bbox[1]
        text_draw.text((text_x, text_y), word, font=font, fill=text_color)

        # Rotate the layer
        if rotation != 0:
            text_layer = text_layer.rotate(
                rotation, resample=Image.Resampling.BICUBIC, expand=True
            )

        return text_layer

    def _create_glow_layer(
        self,
        word: str,
        font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
        text_x: int,
        text_y: int,
        glow_radius: int,
        glow_color: str,
        dimensions: "FrameDimensions",
    ) -> Image.Image:
        """
        Create a glow layer for text.

        Args:
            word: The text to create glow for.
            font: PIL font object.
            text_x: X position of the original text.
            text_y: Y position of the original text.
            glow_radius: Radius of the glow effect in pixels.
            glow_color: Hex color for glow.
            dimensions: Frame dimensions.

        Returns:
            PIL Image with glow layer (RGBA with transparency).
        """
        # Create transparent layer for glow
        glow_layer = Image.new(
            "RGBA", (dimensions.width, dimensions.height), (0, 0, 0, 0)
        )
        glow_draw = ImageDraw.Draw(glow_layer)

        rgb = hex_to_rgb(glow_color)
        # Use full opacity for initial glow drawing, blur will spread and fade
        glow_rgba = (*rgb, 255)

        # Draw the text multiple times with slight offsets to create thicker base
        # This creates a bolder glow effect
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                glow_draw.text(
                    (text_x + dx, text_y + dy), word, font=font, fill=glow_rgba
                )

        # Apply significant blur to create the glow halo
        if glow_radius > 0:
            # Use stronger blur for glow effect (multiply by 1.5 for more spread)
            blur_amount = glow_radius * 1.5
            glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(blur_amount))

        return glow_layer

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

        # Get font color
        font_color = hex_to_rgb(style.font_color)

        # Check if rotation is enabled (non-zero)
        rotation = style.text_rotation
        use_rotation = abs(rotation) > 0.1  # Small threshold to avoid unnecessary rotation

        if use_rotation:
            # Create rotated text layer to determine final size
            rotated_text = self._create_rotated_text_layer(
                word, font, (*font_color, 255), rotation
            )
            rotated_size = rotated_text.size

            # Calculate position based on rotated size for proper bounds checking
            x, y = self._calculate_text_position(
                dimensions, text_bbox, style, rotated_size
            )

            # Convert image to RGBA for compositing
            image = image.convert("RGBA")

            # Draw highlight behind text if enabled (also rotated)
            if style.highlight_style != HighlightStyle.NONE and style.highlight_color:
                highlight_layer = self._create_rotated_highlight_layer(
                    word, font, text_bbox, style, rotated_size
                )
                # Create full-size layer and paste the highlight
                full_highlight = Image.new(
                    "RGBA", (dimensions.width, dimensions.height), (0, 0, 0, 0)
                )
                paste_x = x + (rotated_size[0] - highlight_layer.width) // 2
                paste_y = y + (rotated_size[1] - highlight_layer.height) // 2
                full_highlight.paste(highlight_layer, (paste_x, paste_y), highlight_layer)
                image = Image.alpha_composite(image, full_highlight)

            # Apply drop shadow effect if enabled (rotated)
            if style.shadow_enabled:
                shadow_color = hex_to_rgb(style.shadow_color)
                shadow_layer = self._create_rotated_text_layer(
                    word, font, (*shadow_color, 180), rotation
                )
                if style.shadow_blur > 0:
                    shadow_layer = shadow_layer.filter(
                        ImageFilter.GaussianBlur(style.shadow_blur)
                    )
                # Create full-size layer and paste the shadow with offset
                full_shadow = Image.new(
                    "RGBA", (dimensions.width, dimensions.height), (0, 0, 0, 0)
                )
                shadow_x = x + style.shadow_offset[0]
                shadow_y = y + style.shadow_offset[1]
                full_shadow.paste(shadow_layer, (shadow_x, shadow_y), shadow_layer)
                image = Image.alpha_composite(image, full_shadow)

            # Apply glow effect if enabled (rotated)
            if style.glow_enabled:
                glow_color = hex_to_rgb(style.glow_color)
                # Create thicker glow base by drawing multiple offset copies
                glow_base = self._create_rotated_text_layer(
                    word, font, (*glow_color, 255), rotation
                )
                # Expand glow with additional offset renders
                expanded_size = (
                    glow_base.width + 8,
                    glow_base.height + 8,
                )
                glow_layer = Image.new("RGBA", expanded_size, (0, 0, 0, 0))
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        glow_layer.paste(
                            glow_base, (4 + dx, 4 + dy), glow_base
                        )
                if style.glow_radius > 0:
                    blur_amount = style.glow_radius * 1.5
                    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(blur_amount))
                # Create full-size layer and paste the glow
                full_glow = Image.new(
                    "RGBA", (dimensions.width, dimensions.height), (0, 0, 0, 0)
                )
                glow_x = x - 4
                glow_y = y - 4
                full_glow.paste(glow_layer, (glow_x, glow_y), glow_layer)
                image = Image.alpha_composite(image, full_glow)

            # Paste the rotated text on top
            full_text = Image.new(
                "RGBA", (dimensions.width, dimensions.height), (0, 0, 0, 0)
            )
            full_text.paste(rotated_text, (x, y), rotated_text)
            image = Image.alpha_composite(image, full_text)

        else:
            # No rotation - use original direct drawing approach
            # Calculate position
            x, y = self._calculate_text_position(dimensions, text_bbox, style)

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

            # Apply drop shadow effect if enabled
            if style.shadow_enabled:
                shadow_layer = self._create_shadow_layer(
                    word=word,
                    font=font,
                    text_x=x,
                    text_y=y,
                    shadow_offset=style.shadow_offset,
                    shadow_blur=style.shadow_blur,
                    shadow_color=style.shadow_color,
                    dimensions=dimensions,
                )
                # Composite shadow onto background (convert to RGBA for compositing)
                image = image.convert("RGBA")
                image = Image.alpha_composite(image, shadow_layer)

            # Apply glow effect if enabled
            if style.glow_enabled:
                glow_layer = self._create_glow_layer(
                    word=word,
                    font=font,
                    text_x=x,
                    text_y=y,
                    glow_radius=style.glow_radius,
                    glow_color=style.glow_color,
                    dimensions=dimensions,
                )
                # Composite glow onto image
                if image.mode != "RGBA":
                    image = image.convert("RGBA")
                image = Image.alpha_composite(image, glow_layer)

            # Draw the main text on top
            # Need to recreate draw context if image was converted
            draw = ImageDraw.Draw(image)
            draw.text((x, y), word, font=font, fill=font_color)

        # Convert back to RGB for final output
        if image.mode == "RGBA":
            image = image.convert("RGB")

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
