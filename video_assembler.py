"""
Video Assembler Module for Artistic Word-by-Word Video Generation.

This module assembles image frames into a video synced with audio using FFmpeg.
Each frame is displayed for the duration of its corresponding word timing.
"""

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import ffmpeg
from PIL import Image

from frame_generator import FrameDimensions


@dataclass
class FrameWithTiming:
    """
    A frame with its associated timing information.

    Attributes:
        image: PIL Image object for the frame.
        start_time: Start time in seconds when frame should appear.
        end_time: End time in seconds when frame should disappear.
    """

    image: Image.Image
    start_time: float
    end_time: float

    @property
    def duration(self) -> float:
        """Calculate the duration this frame should be displayed."""
        return self.end_time - self.start_time


# Output format type
OutputFormat = Literal["9:16", "1:1", "16:9"]


class VideoAssembler:
    """
    Assembles image frames into a video with audio.

    Uses FFmpeg to create H.264 MP4 videos optimized for web playback.
    """

    def __init__(self) -> None:
        """Initialize the VideoAssembler."""
        pass

    def _get_dimensions_for_format(self, output_format: OutputFormat) -> tuple[int, int]:
        """
        Get the pixel dimensions for an output format.

        Args:
            output_format: Output format string ("9:16", "1:1", or "16:9").

        Returns:
            Tuple of (width, height) in pixels.
        """
        dimensions = FrameDimensions.from_format_string(output_format)
        return (dimensions.width, dimensions.height)

    def _create_frame_files(
        self,
        frames_with_timing: list[FrameWithTiming],
        temp_dir: str,
    ) -> list[tuple[str, float]]:
        """
        Save frames as image files and return paths with durations.

        Args:
            frames_with_timing: List of FrameWithTiming objects.
            temp_dir: Temporary directory to save frames.

        Returns:
            List of tuples containing (file_path, duration_in_seconds).
        """
        frame_files: list[tuple[str, float]] = []

        for i, frame in enumerate(frames_with_timing):
            # Save frame as PNG for lossless quality
            frame_path = os.path.join(temp_dir, f"frame_{i:06d}.png")
            frame.image.save(frame_path, "PNG")
            frame_files.append((frame_path, frame.duration))

        return frame_files

    def _create_concat_file(
        self,
        frame_files: list[tuple[str, float]],
        concat_file_path: str,
    ) -> None:
        """
        Create a concat demuxer file for FFmpeg.

        Args:
            frame_files: List of (file_path, duration) tuples.
            concat_file_path: Path to write the concat file.
        """
        with open(concat_file_path, "w", encoding="utf-8") as f:
            for file_path, duration in frame_files:
                # FFmpeg concat demuxer format
                # Escape single quotes in file paths
                escaped_path = file_path.replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
                f.write(f"duration {duration:.6f}\n")

            # Add last frame again to ensure it displays for full duration
            if frame_files:
                last_path = frame_files[-1][0].replace("'", "'\\''")
                f.write(f"file '{last_path}'\n")

    def assemble(
        self,
        frames_with_timing: list[FrameWithTiming],
        audio_path: Path | str,
        output_path: Path | str,
        output_format: OutputFormat = "9:16",
    ) -> Path:
        """
        Assemble frames into a video with audio.

        Args:
            frames_with_timing: List of FrameWithTiming objects containing
                               PIL Images with start and end times.
            audio_path: Path to the audio file (mp3, wav, etc.).
            output_path: Path for the output video file.
            output_format: Video format - "9:16" (portrait), "1:1" (square),
                          or "16:9" (landscape). Default is "9:16".

        Returns:
            Path to the created video file.

        Raises:
            ValueError: If frames_with_timing is empty.
            Exception: If FFmpeg processing fails.
        """
        if not frames_with_timing:
            raise ValueError("frames_with_timing cannot be empty")

        # Convert to Path objects
        audio_path = Path(audio_path)
        output_path = Path(output_path)

        # Get target dimensions for the format
        target_width, target_height = self._get_dimensions_for_format(output_format)

        # Create temporary directory for frame files
        with tempfile.TemporaryDirectory() as temp_dir:
            # Save frames to temporary files
            frame_files = self._create_frame_files(frames_with_timing, temp_dir)

            # Create concat demuxer file
            concat_file_path = os.path.join(temp_dir, "concat.txt")
            self._create_concat_file(frame_files, concat_file_path)

            try:
                # Build FFmpeg command using concat demuxer
                video_input = ffmpeg.input(
                    concat_file_path,
                    f="concat",
                    safe=0,
                )

                audio_input = ffmpeg.input(str(audio_path))

                # Create output with H.264 encoding optimized for web
                output = ffmpeg.output(
                    video_input,
                    audio_input,
                    str(output_path),
                    vcodec="libx264",
                    acodec="aac",
                    pix_fmt="yuv420p",
                    crf=23,
                    preset="medium",
                    movflags="+faststart",
                    shortest=None,  # End when shortest stream ends
                    **{"b:a": "192k"},
                    ar=44100,
                    s=f"{target_width}x{target_height}",
                )

                # Run FFmpeg
                ffmpeg.run(
                    output,
                    overwrite_output=True,
                    capture_stdout=True,
                    capture_stderr=True,
                )

            except ffmpeg.Error as e:
                stderr = e.stderr.decode() if e.stderr else "Unknown error"
                raise Exception(f"Error assembling video: {stderr}")

        return output_path


# Module-level convenience instance
_default_assembler: VideoAssembler | None = None


def get_default_assembler() -> VideoAssembler:
    """
    Get the default VideoAssembler instance (singleton).

    Returns:
        The default VideoAssembler instance.
    """
    global _default_assembler
    if _default_assembler is None:
        _default_assembler = VideoAssembler()
    return _default_assembler


def assemble_video(
    frames_with_timing: list[FrameWithTiming],
    audio_path: Path | str,
    output_path: Path | str,
    output_format: OutputFormat = "9:16",
) -> Path:
    """
    Assemble frames into a video with audio using the default assembler.

    Args:
        frames_with_timing: List of FrameWithTiming objects containing
                           PIL Images with start and end times.
        audio_path: Path to the audio file (mp3, wav, etc.).
        output_path: Path for the output video file.
        output_format: Video format - "9:16" (portrait), "1:1" (square),
                      or "16:9" (landscape). Default is "9:16".

    Returns:
        Path to the created video file.
    """
    return get_default_assembler().assemble(
        frames_with_timing, audio_path, output_path, output_format
    )


def create_frames_with_timing(
    images: list[Image.Image],
    timings: list[dict[str, float]],
) -> list[FrameWithTiming]:
    """
    Create FrameWithTiming objects from separate lists of images and timings.

    This is a convenience function to convert the output of caption_parser
    and frame_generator into the format expected by assemble_video.

    Args:
        images: List of PIL Image objects.
        timings: List of dicts with 'start_time' and 'end_time' keys (in seconds).

    Returns:
        List of FrameWithTiming objects.

    Raises:
        ValueError: If images and timings lists have different lengths.
    """
    if len(images) != len(timings):
        raise ValueError(
            f"Number of images ({len(images)}) must match number of timings ({len(timings)})"
        )

    return [
        FrameWithTiming(
            image=image,
            start_time=timing["start_time"],
            end_time=timing["end_time"],
        )
        for image, timing in zip(images, timings)
    ]
