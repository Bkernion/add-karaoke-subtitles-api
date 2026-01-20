r"""
Caption Parser for Word-Level Timing Extraction.

This module parses SRT and ASS subtitle files to extract individual words
with their precise timing information. Supports karaoke timing tags (\k)
in ASS files for precise word-level timing.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class WordTiming:
    """
    Timing information for a single word.

    Attributes:
        word: The text of the word.
        start_time: Start time in seconds.
        end_time: End time in seconds.
    """

    word: str
    start_time: float
    end_time: float


def _srt_time_to_seconds(srt_time: str) -> float:
    """
    Convert SRT time format (HH:MM:SS,mmm) to seconds.

    Args:
        srt_time: Time string in SRT format (e.g., "00:01:23,456").

    Returns:
        Time in seconds as a float.
    """
    # SRT format: HH:MM:SS,mmm (uses comma for milliseconds)
    # Also handle period separator as some SRT files use that
    srt_time = srt_time.replace(",", ".")
    parts = srt_time.split(":")

    hours = int(parts[0])
    minutes = int(parts[1])
    seconds_parts = parts[2].split(".")
    seconds = int(seconds_parts[0])
    milliseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0

    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000.0


def _ass_time_to_seconds(ass_time: str) -> float:
    """
    Convert ASS time format (H:MM:SS.CC) to seconds.

    Args:
        ass_time: Time string in ASS format (e.g., "0:01:23.45").

    Returns:
        Time in seconds as a float.
    """
    # ASS format: H:MM:SS.CC (centiseconds)
    parts = ass_time.strip().split(":")

    hours = int(parts[0])
    minutes = int(parts[1])
    seconds_parts = parts[2].split(".")
    seconds = int(seconds_parts[0])
    centiseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0

    return hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0


def _clean_word(word: str) -> str:
    """
    Clean a single word by removing stray characters.

    Args:
        word: The word to clean.

    Returns:
        Cleaned word.
    """
    # Remove leading/trailing slashes and backslashes (common ASS artifacts)
    word = word.strip("/\\")
    # Remove any remaining backslashes within the word
    word = word.replace("\\", "")
    return word.strip()


def _distribute_timing_to_words(
    text: str, start_time: float, end_time: float
) -> list[WordTiming]:
    """
    Distribute timing evenly across words in a text string.

    Timing is calculated based on original word positions to preserve
    the intended rhythm even when characters are cleaned from words.

    Args:
        text: The text containing words to time.
        start_time: Start time of the entire text block.
        end_time: End time of the entire text block.

    Returns:
        List of WordTiming objects with evenly distributed timing.
    """
    # Split into words (keep original positions for timing)
    raw_words = [w.strip() for w in text.split() if w.strip()]

    if not raw_words:
        return []

    duration = end_time - start_time
    word_duration = duration / len(raw_words)  # Based on ORIGINAL word count

    result: list[WordTiming] = []
    for i, word in enumerate(raw_words):
        cleaned_word = _clean_word(word)
        # Calculate timing based on original position
        word_start = start_time + (i * word_duration)
        word_end = word_start + word_duration
        # Only add if word has content after cleaning
        if cleaned_word:
            result.append(WordTiming(word=cleaned_word, start_time=word_start, end_time=word_end))

    return result


def _parse_karaoke_tags(text: str, start_time: float) -> list[WordTiming] | None:
    r"""
    Parse ASS karaoke timing tags (\k, \K, \kf, \ko) to extract word-level timing.

    Karaoke tags encode timing in centiseconds:
    - {\k50}word = word takes 0.5 seconds (50 centiseconds)
    - {\K100}word = word takes 1.0 second (100 centiseconds)

    Args:
        text: Text with potential karaoke tags.
        start_time: Base start time for the line.

    Returns:
        List of WordTiming if karaoke tags found, None otherwise.
    """
    # Match karaoke tags: {\kN}, {\KN}, {\kfN}, {\koN}
    karaoke_pattern = r"\{\\[kK](?:f|o)?(\d+)\}([^{]*)"
    matches = re.findall(karaoke_pattern, text)

    if not matches:
        return None

    result: list[WordTiming] = []
    current_time = start_time

    for duration_cs, word_text in matches:
        duration_seconds = int(duration_cs) / 100.0
        # Clean ASS special characters from word text
        word_text = re.sub(r"\\[Nnh]", " ", word_text)
        word_text = word_text.replace("\\", "")
        word_text = word_text.strip()

        if word_text:
            # Handle multiple words within a single karaoke tag
            words = word_text.split()
            if len(words) > 1:
                # Distribute timing across multiple words based on ORIGINAL count
                word_duration = duration_seconds / len(words)
                for word in words:
                    cleaned = _clean_word(word)
                    word_start = current_time
                    word_end = current_time + word_duration
                    # Always advance timing based on original position
                    current_time += word_duration
                    # Only add to result if word has content
                    if cleaned:
                        result.append(
                            WordTiming(
                                word=cleaned,
                                start_time=word_start,
                                end_time=word_end,
                            )
                        )
            else:
                cleaned = _clean_word(word_text)
                word_start = current_time
                word_end = current_time + duration_seconds
                # Always advance timing
                current_time += duration_seconds
                # Only add to result if word has content
                if cleaned:
                    result.append(
                        WordTiming(
                            word=cleaned,
                            start_time=word_start,
                            end_time=word_end,
                        )
                    )
        else:
            # Empty text, just advance time
            current_time += duration_seconds

    return result if result else None


def _clean_ass_text(text: str) -> str:
    """
    Remove ASS formatting tags from text.

    Args:
        text: Text with potential ASS tags.

    Returns:
        Cleaned text without ASS tags.
    """
    # Remove all ASS tags like {\k25}, {\r}, {\an8}, etc.
    clean_text = re.sub(r"\{[^}]*\}", "", text)
    # Remove ASS line break and special characters: \N, \n, \h
    clean_text = re.sub(r"\\[Nnh]", " ", clean_text)
    # Remove any stray backslashes that might remain
    clean_text = clean_text.replace("\\", "")
    # Clean up multiple spaces
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    return clean_text


def _read_file_with_encoding(file_path: Path) -> str:
    """
    Read a file trying multiple encodings.

    Args:
        file_path: Path to the file.

    Returns:
        File contents as string.

    Raises:
        ValueError: If file cannot be read with any encoding.
    """
    encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252", "iso-8859-1"]

    for encoding in encodings:
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read()
        except (UnicodeDecodeError, LookupError):
            continue

    # Last resort: read as binary and decode with error replacement
    with open(file_path, "rb") as f:
        raw_content = f.read()
    return raw_content.decode("utf-8", errors="replace")


def parse_srt(file_path: str | Path) -> list[dict[str, str | float]]:
    """
    Parse an SRT subtitle file and extract word-level timing.

    SRT format:
    1
    00:00:01,000 --> 00:00:04,000
    Hello world

    Args:
        file_path: Path to the SRT file.

    Returns:
        List of dicts with 'word', 'start_time', and 'end_time' keys.
        Times are in seconds as floats.
    """
    file_path = Path(file_path)
    content = _read_file_with_encoding(file_path)

    # Split into subtitle blocks (separated by blank lines)
    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\n+", content.strip())

    all_words: list[dict[str, str | float]] = []

    for block in blocks:
        lines = block.strip().split("\n")

        if len(lines) < 2:
            continue

        # Find the timing line (contains " --> ")
        timing_line = None
        text_start_idx = 0

        for i, line in enumerate(lines):
            if " --> " in line:
                timing_line = line
                text_start_idx = i + 1
                break

        if timing_line is None:
            continue

        # Parse timing
        timing_match = re.match(
            r"(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[,\.]\d{3})",
            timing_line.strip(),
        )

        if not timing_match:
            continue

        start_time = _srt_time_to_seconds(timing_match.group(1))
        end_time = _srt_time_to_seconds(timing_match.group(2))

        # Get text (may span multiple lines)
        text_lines = lines[text_start_idx:]
        text = " ".join(text_lines)

        # Remove HTML-like tags (e.g., <i>, </i>, <b>, etc.)
        text = re.sub(r"<[^>]+>", "", text)
        text = text.strip()

        if not text:
            continue

        # Distribute timing across words
        word_timings = _distribute_timing_to_words(text, start_time, end_time)

        for wt in word_timings:
            all_words.append(
                {"word": wt.word, "start_time": wt.start_time, "end_time": wt.end_time}
            )

    return all_words


def parse_ass(file_path: str | Path) -> list[dict[str, str | float]]:
    r"""
    Parse an ASS/SSA subtitle file and extract word-level timing.

    Supports karaoke timing tags (\k, \K, \kf, \ko) for precise word timing.
    Falls back to even distribution if no karaoke tags are present.

    ASS dialogue format:
    Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text

    Args:
        file_path: Path to the ASS file.

    Returns:
        List of dicts with 'word', 'start_time', and 'end_time' keys.
        Times are in seconds as floats.
    """
    file_path = Path(file_path)
    content = _read_file_with_encoding(file_path)

    # Normalize line endings
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = content.split("\n")

    all_words: list[dict[str, str | float]] = []

    for line in lines:
        if not line.startswith("Dialogue:"):
            continue

        # Parse ASS dialogue line
        # Format: Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
        # Split on comma, but only up to 9 commas (the Text field may contain commas)
        parts = line.split(",", 9)

        if len(parts) < 10:
            continue

        start_time = _ass_time_to_seconds(parts[1])
        end_time = _ass_time_to_seconds(parts[2])
        text = parts[9].strip()

        if not text:
            continue

        # Try to parse karaoke tags first for precise timing
        karaoke_words = _parse_karaoke_tags(text, start_time)

        if karaoke_words:
            # Use karaoke timing
            for wt in karaoke_words:
                all_words.append(
                    {
                        "word": wt.word,
                        "start_time": wt.start_time,
                        "end_time": wt.end_time,
                    }
                )
        else:
            # No karaoke tags - clean text and distribute evenly
            clean_text = _clean_ass_text(text)

            if not clean_text:
                continue

            word_timings = _distribute_timing_to_words(clean_text, start_time, end_time)

            for wt in word_timings:
                all_words.append(
                    {
                        "word": wt.word,
                        "start_time": wt.start_time,
                        "end_time": wt.end_time,
                    }
                )

    return all_words


def parse_caption_file(file_path: str | Path) -> list[dict[str, str | float]]:
    """
    Parse a caption file (SRT or ASS) and extract word-level timing.

    Automatically detects file format based on extension.

    Args:
        file_path: Path to the caption file (.srt or .ass).

    Returns:
        List of dicts with 'word', 'start_time', and 'end_time' keys.

    Raises:
        ValueError: If file format is not supported.
    """
    file_path = Path(file_path)
    extension = file_path.suffix.lower()

    if extension == ".srt":
        return parse_srt(file_path)
    elif extension in (".ass", ".ssa"):
        return parse_ass(file_path)
    else:
        raise ValueError(
            f"Unsupported caption format: {extension}. Supported: .srt, .ass, .ssa"
        )
