import re
from pathlib import Path
from typing import List, Dict, Any
import math

class KaraokeSubtitleGenerator:
    def __init__(self):
        self.syllable_patterns = self._create_syllable_patterns()
    
    def _create_syllable_patterns(self) -> List[str]:
        return [
            r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]*[aeiouAEIOU]+[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]*',
            r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]+',
            r'[aeiouAEIOU]+'
        ]
    
    # Matches an SRT timestamp line: "00:00:01,840 --> 00:00:03,520"
    # Tolerant: 1-2 digit hours, comma OR period millisecond separator, 1-3 digit ms.
    _SRT_TIMESTAMP_RE = re.compile(
        r'(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*'
        r'(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})'
    )

    def parse_ass_file(self, ass_path: Path) -> Dict[str, Any]:
        """Parse a subtitle file (ASS or SRT) into Whisper transcription format.

        Despite the name, this dispatches on the file's actual content — so a
        .srt payload masquerading as an .ass file (which HeyGen sometimes
        serves via the same caption_url) is parsed correctly.
        """
        # Sniff for binary/video files masquerading as captions
        with open(ass_path, 'rb') as f:
            first_bytes = f.read(20)

        print(f"🔍 File magic bytes (first 20): {first_bytes[:20]}")
        print(f"🔍 File magic hex: {first_bytes[:20].hex()}")

        if b'ftyp' in first_bytes[:20] or b'moov' in first_bytes[:20]:
            raise Exception(
                "❌ ERROR: The caption_url is pointing to a VIDEO FILE (MP4/MOV), not a subtitle file! "
                "In your n8n workflow, make sure 'caption_url' uses the SUBTITLE URL from HeyGen, not the video URL. "
                "HeyGen provides separate URLs for video and captions - you need the caption/subtitle URL."
            )

        if first_bytes.startswith(b'RIFF'):
            raise Exception(
                "❌ ERROR: The caption_url is pointing to a VIDEO FILE (AVI), not a subtitle file! "
                "Make sure 'caption_url' uses the subtitle URL, not the video URL."
            )

        # Decode with a fallback chain — caption files come from many sources
        encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        content = None
        used_encoding = None
        for encoding in encodings:
            try:
                with open(ass_path, 'r', encoding=encoding) as f:
                    content = f.read()
                used_encoding = encoding
                break
            except (UnicodeDecodeError, LookupError):
                continue
        if content is None:
            with open(ass_path, 'rb') as f:
                raw_content = f.read()
            content = raw_content.decode('utf-8', errors='replace')
            used_encoding = 'utf-8 (with error replacement)'

        # Strip BOM if it survived decoding
        if content.startswith('\ufeff'):
            content = content[1:]

        print(f"🔤 Successfully read subtitle file using {used_encoding} encoding")
        print(f"📄 Subtitle file has {len(content)} characters, {len(content.split(chr(10)))} lines")

        # Debug: Show first 20 lines of the file
        lines = content.split('\n')
        print(f"🔍 First 20 lines of subtitle file:")
        for i, line in enumerate(lines[:20]):
            print(f"   Line {i+1}: {line[:100]}")

        fmt = self._detect_subtitle_format(content)
        print(f"🔎 Detected subtitle format: {fmt.upper()}")

        if fmt == 'ass':
            result = self._parse_ass_content(content)
        elif fmt == 'srt':
            result = self._parse_srt_content(content)
        else:
            raise Exception(
                "❌ ERROR: Subtitle file is neither ASS nor SRT — could not find any "
                "'Dialogue:' lines (ASS) or 'HH:MM:SS,mmm --> ...' timestamps (SRT). "
                f"First 200 chars: {content[:200]!r}"
            )

        if not result['segments']:
            raise Exception(
                f"❌ ERROR: Subtitle file recognized as {fmt.upper()} but parsed 0 segments. "
                f"File length: {len(content)} chars. First 200 chars: {content[:200]!r}"
            )

        print(f"✅ Parsed {len(result['segments'])} segments with {len(result['words'])} total words")
        print(f"   First segment: {result['segments'][0].get('text', '')[:50]}...")
        print(f"   First segment has {len(result['segments'][0].get('words', []))} words")

        return result

    def _detect_subtitle_format(self, content: str) -> str:
        """Return 'ass', 'srt', or 'unknown' based on content sniffing."""
        if 'Dialogue:' in content or '[Script Info]' in content or '[V4+ Styles]' in content:
            return 'ass'
        if self._SRT_TIMESTAMP_RE.search(content):
            return 'srt'
        return 'unknown'

    def _count_syllables(self, word: str) -> int:
        """Approximate English syllable count via the vowel-group heuristic.

        Used to weight per-word duration inside a cue so long words
        ("entire", "underground") get more time than short ones ("the", "a"),
        which keeps the karaoke highlight from sliding behind speech on long
        cues. Heuristic is ~80% accurate for English — good enough for
        timing weights, and infinitely better than equal slices.
        """
        cleaned = re.sub(r'[^a-zA-Z]', '', word).lower()
        if not cleaned:
            # Numbers, punctuation: estimate by digit count (e.g. "1997" → 4 syllables read aloud)
            digits = sum(c.isdigit() for c in word)
            return max(digits, 1)
        groups = re.findall(r'[aeiouy]+', cleaned)
        count = len(groups)
        # Silent trailing 'e' ("rescue" → 2, not 3) — but never drop below 1
        if cleaned.endswith('e') and count > 1:
            count -= 1
        return max(count, 1)

    def _segment_from_text(self, start_time: float, end_time: float, clean_text: str,
                           word_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build one Whisper-style segment with syllable-weighted word timings.

        Distributes the cue's duration across words proportional to their
        syllable count, so the highlight tracks actual speech pace within a
        cue. The first word still begins at start_time and the last word
        still ends at end_time, so cue boundaries are preserved exactly.

        Appends each word to the shared word_list so the caller can return a
        flat list alongside the per-segment ones.
        """
        words = clean_text.split()
        duration = max(end_time - start_time, 1e-3)

        weights = [self._count_syllables(w) for w in words]
        total_weight = sum(weights) or len(words)  # safety: never divide by zero

        segment_words = []
        elapsed = 0.0
        for i, (word, weight) in enumerate(zip(words, weights)):
            if i == len(words) - 1:
                # Anchor last word's end exactly to cue end so float drift
                # doesn't push the final highlight past the cue boundary.
                word_end = duration
            else:
                word_end = elapsed + duration * (weight / total_weight)
            word_start_offset = elapsed
            elapsed = word_end

            entry = {
                'word': word,
                'start': start_time + word_start_offset,
                'end': start_time + word_end,
                'probability': 1.0,  # external transcription is treated as ground truth
            }
            segment_words.append(entry)
            word_list.append(entry)

        return {
            'start': start_time,
            'end': end_time,
            'text': clean_text,
            'words': segment_words,
        }

    def _parse_ass_content(self, content: str) -> Dict[str, Any]:
        segments: List[Dict[str, Any]] = []
        word_list: List[Dict[str, Any]] = []

        dialogue_lines = [ln for ln in content.split('\n') if ln.startswith('Dialogue:')]
        print(f"💬 Found {len(dialogue_lines)} dialogue lines in ASS file")

        for line in dialogue_lines:
            # Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
            parts = line.split(',', 9)
            if len(parts) < 10:
                continue

            start_time = self._ass_time_to_seconds(parts[1])
            end_time = self._ass_time_to_seconds(parts[2])
            text = parts[9].strip()

            # Strip ASS override tags ({\k25}, {/k9}, {\r}, partials, stragglers)
            clean_text = re.sub(r'\{[^}]*\}', '', text)
            clean_text = re.sub(r'\{[^}]*', '', clean_text)
            clean_text = re.sub(r'[^{]*\}', '', clean_text)
            clean_text = re.sub(r'[{}]', '', clean_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            if not clean_text:
                continue

            segments.append(self._segment_from_text(start_time, end_time, clean_text, word_list))

        return {
            'segments': segments,
            'text': ' '.join(s['text'] for s in segments),
            'words': word_list,
        }

    def _parse_srt_content(self, content: str) -> Dict[str, Any]:
        segments: List[Dict[str, Any]] = []
        word_list: List[Dict[str, Any]] = []

        # Normalize line endings, then split into cue blocks on blank lines
        normalized = content.replace('\r\n', '\n').replace('\r', '\n').strip()
        blocks = re.split(r'\n\s*\n', normalized)
        print(f"💬 Found {len(blocks)} SRT blocks")

        for block in blocks:
            block_lines = [ln for ln in block.split('\n') if ln.strip()]
            if not block_lines:
                continue

            # Locate the timestamp line — usually line 0 or 1 (after the cue index)
            ts_match = None
            ts_idx = None
            for i, ln in enumerate(block_lines):
                m = self._SRT_TIMESTAMP_RE.search(ln)
                if m:
                    ts_match = m
                    ts_idx = i
                    break
            if ts_match is None:
                continue

            start_time = self._srt_time_to_seconds(*ts_match.group(1, 2, 3, 4))
            end_time = self._srt_time_to_seconds(*ts_match.group(5, 6, 7, 8))

            # Text = everything after the timestamp line, joined into one string
            raw_text = ' '.join(block_lines[ts_idx + 1:])
            # Strip simple HTML/SRT inline tags (<i>, <b>, <font color="...">)
            clean_text = re.sub(r'<[^>]+>', '', raw_text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            if not clean_text:
                continue

            segments.append(self._segment_from_text(start_time, end_time, clean_text, word_list))

        return {
            'segments': segments,
            'text': ' '.join(s['text'] for s in segments),
            'words': word_list,
        }

    def _ass_time_to_seconds(self, ass_time: str) -> float:
        """Convert ASS time format (H:MM:SS.CC) to seconds (e.g. '0:00:01.84')."""
        parts = ass_time.split(':')
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_parts = parts[2].split('.')
        seconds = int(seconds_parts[0])
        centiseconds = int(seconds_parts[1]) if len(seconds_parts) > 1 else 0

        return hours * 3600 + minutes * 60 + seconds + centiseconds / 100.0

    def _srt_time_to_seconds(self, h: str, m: str, s: str, ms: str) -> float:
        """Convert SRT timestamp components to seconds. ms is 1-3 digits, scaled to ms."""
        # Right-pad ms so "5" → 500ms, "84" → 840ms, "840" → 840ms
        ms_int = int(ms.ljust(3, '0')[:3])
        return int(h) * 3600 + int(m) * 60 + int(s) + ms_int / 1000.0
    
    def _split_into_syllables(self, word: str) -> List[str]:
        if len(word) <= 2:
            return [word]
        
        syllables = []
        remaining = word.lower()
        
        vowels = "aeiou"
        consonants = "bcdfghjklmnpqrstvwxyz"
        
        i = 0
        while i < len(remaining):
            syllable = ""
            
            while i < len(remaining) and remaining[i] in consonants:
                syllable += remaining[i]
                i += 1
            
            if i < len(remaining) and remaining[i] in vowels:
                syllable += remaining[i]
                i += 1
                
                if i < len(remaining) and remaining[i] in consonants:
                    if i + 1 < len(remaining) and remaining[i + 1] in vowels:
                        pass
                    else:
                        syllable += remaining[i]
                        i += 1
            
            if syllable:
                syllables.append(syllable)
            elif i < len(remaining):
                syllables.append(remaining[i])
                i += 1
        
        if not syllables:
            return [word]
        
        result = []
        word_chars = list(word)
        char_idx = 0
        
        for syl in syllables:
            actual_syllable = ""
            for _ in range(len(syl)):
                if char_idx < len(word_chars):
                    actual_syllable += word_chars[char_idx]
                    char_idx += 1
            if actual_syllable:
                result.append(actual_syllable)
        
        while char_idx < len(word_chars):
            if result:
                result[-1] += word_chars[char_idx]
            else:
                result.append(word_chars[char_idx])
            char_idx += 1
        
        return result if result else [word]
    
    def _format_timestamp(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours}:{minutes:02d}:{secs:05.2f}"
    
    def _hex_to_ass_color(self, hex_color: str) -> str:
        """Convert hex color (#RRGGBB) to ASS color format (&H00BBGGRR)"""
        if hex_color.startswith('#'):
            hex_color = hex_color[1:]
        
        # Ensure valid 6-character hex
        if len(hex_color) != 6 or not all(c in '0123456789ABCDEFabcdef' for c in hex_color):
            hex_color = "FFFFFF"  # Default to white
        
        # ASS uses BGR format, so reverse RGB
        r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
        
        # Convert to integers and back to ensure proper format
        r_int = int(r, 16)
        g_int = int(g, 16)  
        b_int = int(b, 16)
        
        return f"&H00{b_int:02X}{g_int:02X}{r_int:02X}"
    
    def _wrap_text_for_video(self, words_with_timing: List[Dict], max_chars_per_line: int, max_words_per_line: int) -> List[Dict]:
        """Smart text wrapping based on video orientation"""
        wrapped_segments = []
        current_line_words = []
        current_line_chars = 0
        
        for word_info in words_with_timing:
            word = word_info["word"].strip()
            word_length = len(word) + 1  # +1 for space
            
            # Check if adding this word would exceed limits
            if (current_line_chars + word_length > max_chars_per_line or 
                len(current_line_words) >= max_words_per_line) and current_line_words:
                
                # Finalize current line
                wrapped_segments.append({
                    "words": current_line_words.copy(),
                    "start": current_line_words[0]["start"],
                    "end": current_line_words[-1]["end"]
                })
                
                # Start new line
                current_line_words = [word_info]
                current_line_chars = word_length
            else:
                # Add to current line
                current_line_words.append(word_info)
                current_line_chars += word_length
        
        # Add final line if it has words
        if current_line_words:
            wrapped_segments.append({
                "words": current_line_words,
                "start": current_line_words[0]["start"],
                "end": current_line_words[-1]["end"]
            })
        
        return wrapped_segments
    
    def _create_ass_styles(self, font_name: str = "Arial Rounded MT Bold",
                          font_size: int = 24,
                          font_color: str = "#FFFFFF", 
                          highlight_color: str = "#FFFF00") -> str:
        primary_color = self._hex_to_ass_color(font_color)
        secondary_color = self._hex_to_ass_color(highlight_color)
        
        return f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},{secondary_color},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1"""
    
    def _create_ass_styles_with_position(self, font_name: str = "Arial Rounded MT Bold",
                          font_size: int = 24,
                          font_color: str = "#FFFFFF", 
                          highlight_color: str = "#FFFF00",
                          video_height: int = 1080,
                          subtitle_position: float = 0.75) -> str:
        
        primary_color = self._hex_to_ass_color(font_color)
        secondary_color = self._hex_to_ass_color(highlight_color)
        
        # Adjust margin calculation to position subtitles higher (closer to 3/4 down)
        margin_v = 10 + int((1.0 - (subtitle_position / 2)) * 100)
        
        print(f"📍 subtitle_position={subtitle_position} → marginV={margin_v}px from bottom (video_height={video_height})")
        
        return f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},{secondary_color},&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,{margin_v},1"""
    
    def generate_ass_file(self, transcription: Dict[str, Any], output_path: Path, 
                         font_name: str = "Arial Rounded MT Bold",
                         font_size: int = 24,
                         font_color: str = "#FFFFFF",
                         highlight_color: str = "#FFFF00",
                         video_width: int = 1920,
                         video_height: int = 1080,
                         subtitle_position: float = None,
                         enable_karaoke: bool = True) -> None:
        
        # Debug transcription input
        print(f"🔍 generate_ass_file received transcription with {len(transcription.get('segments', []))} segments")
        
        # Coerce subtitle_position to float and add debugging
        if subtitle_position is not None:
            try:
                subtitle_position = float(subtitle_position)
            except Exception:
                print("⚠️ could not parse subtitle_position:", subtitle_position)
                subtitle_position = None
        print("DEBUG:", subtitle_position, type(subtitle_position), video_height)
        
        # Only apply custom positioning if explicitly provided
        if subtitle_position is not None:
            styles = self._create_ass_styles_with_position(font_name, font_size, font_color, highlight_color, video_height, subtitle_position)
        else:
            styles = self._create_ass_styles(font_name, font_size, font_color, highlight_color)
        
        # Determine video orientation and wrapping strategy
        is_vertical = video_width <= 1080  # Vertical/square videos
        is_horizontal = video_width >= 1920  # Horizontal videos
        
        if is_vertical:
            max_chars_per_line = 15  # Shorter lines for vertical videos
            max_words_per_line = 3
        elif is_horizontal:
            max_chars_per_line = 40  # Longer lines for horizontal videos  
            max_words_per_line = 8
        else:
            max_chars_per_line = 25  # Medium lines for in-between sizes
            max_words_per_line = 5
        
        # Debug: Print style and layout info
        print(f"🎨 Generating subtitles with:")
        print(f"   Video: {video_width}x{video_height} ({'Vertical' if is_vertical else 'Horizontal' if is_horizontal else 'Medium'})")
        print(f"   Font: {font_name}, Size: {font_size}")
        print(f"   Text Color: {font_color} -> {self._hex_to_ass_color(font_color)}")
        print(f"   Highlight Color: {highlight_color} -> {self._hex_to_ass_color(highlight_color)}")
        print(f"   Max chars per line: {max_chars_per_line}, Max words per line: {max_words_per_line}")
        
        ass_content = f"""[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+

{styles}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        dialogue_count = 0
        segments_processed = 0
        segments_skipped = 0
        
        for segment in transcription["segments"]:
            segments_processed += 1
            
            if "words" not in segment:
                segments_skipped += 1
                print(f"⚠️ Segment {segments_processed} has no 'words' key: {segment.keys()}")
                continue
            
            if not segment["words"]:
                segments_skipped += 1
                print(f"⚠️ Segment {segments_processed} has empty 'words' array")
                continue
            
            # Apply adaptive text wrapping based on video orientation
            wrapped_lines = self._wrap_text_for_video(segment["words"], max_chars_per_line, max_words_per_line)
            
            for line_info in wrapped_lines:
                if enable_karaoke:
                    # Word-by-word highlighting: create separate dialogue lines for each word
                    all_words_text = " ".join([w["word"].strip() for w in line_info["words"] if w["word"].strip()])
                    
                    for word_idx, word_info in enumerate(line_info["words"]):
                        word = word_info["word"].strip()
                        if not word:
                            continue
                            
                        word_start = word_info["start"]
                        word_end = word_info["end"]
                        
                        # Create text with current word highlighted
                        highlighted_text = ""
                        highlight_ass_color = self._hex_to_ass_color(highlight_color)
                        for i, w in enumerate(line_info["words"]):
                            w_text = w["word"].strip()
                            if not w_text:
                                continue
                            if i == word_idx:
                                # Highlight current word with user-specified color
                                highlighted_text += f"{{\\c{highlight_ass_color}}}{w_text}{{\\c}}"
                            else:
                                highlighted_text += w_text
                            highlighted_text += " "
                        
                        highlighted_text = highlighted_text.strip()
                        
                        start_time = self._format_timestamp(word_start)
                        end_time = self._format_timestamp(word_end)
                        
                        ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{highlighted_text}\n"
                        dialogue_count += 1
                else:
                    # Simple text without any highlighting
                    simple_text = " ".join([w["word"].strip() for w in line_info["words"] if w["word"].strip()])
                    
                    start_time = self._format_timestamp(line_info["start"])
                    end_time = self._format_timestamp(line_info["end"])
                    
                    ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{simple_text}\n"
                    dialogue_count += 1
        
        print(f"📊 Processed {segments_processed} segments, skipped {segments_skipped}, generated {dialogue_count} dialogue lines")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)