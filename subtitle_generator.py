import re
import whisper
from pathlib import Path
from typing import List, Dict, Any
import math

class KaraokeSubtitleGenerator:
    def __init__(self, model_name: str = "base"):
        self.model = whisper.load_model(model_name)
        self.syllable_patterns = self._create_syllable_patterns()
    
    def _create_syllable_patterns(self) -> List[str]:
        return [
            r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]*[aeiouAEIOU]+[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]*',
            r'[bcdfghjklmnpqrstvwxyzBCDFGHJKLMNPQRSTVWXYZ]+',
            r'[aeiouAEIOU]+'
        ]
    
    def transcribe_with_timing(self, audio_path: Path) -> Dict[str, Any]:
        result = self.model.transcribe(
            str(audio_path),
            word_timestamps=True,
            verbose=False
        )
        return result
    
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
    
    def _create_ass_styles(self) -> str:
        return """[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Rounded MT Bold,24,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1
Style: Karaoke,Arial Rounded MT Bold,24,&H00FFFFFF,&H0000FFFF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1"""
    
    def generate_ass_file(self, transcription: Dict[str, Any], output_path: Path) -> None:
        ass_content = """[Script Info]
Title: Karaoke Subtitles
ScriptType: v4.00+

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Rounded MT Bold,24,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        
        for segment in transcription["segments"]:
            if "words" not in segment:
                continue
                
            segment_start = segment["start"]
            segment_end = segment["end"]
            
            karaoke_text = ""
            current_time = segment_start
            
            for word_info in segment["words"]:
                word = word_info["word"].strip()
                word_start = word_info["start"]
                word_end = word_info["end"]
                
                if not word:
                    continue
                
                syllables = self._split_into_syllables(word)
                
                if len(syllables) == 1:
                    duration_cs = int((word_end - word_start) * 100)
                    karaoke_text += f"{{\\k{duration_cs}}}{word}"
                else:
                    syllable_duration = (word_end - word_start) / len(syllables)
                    for syllable in syllables:
                        duration_cs = int(syllable_duration * 100)
                        karaoke_text += f"{{\\k{duration_cs}}}{syllable}"
                
                karaoke_text += " "
            
            karaoke_text = karaoke_text.strip()
            
            start_time = self._format_timestamp(segment_start)
            end_time = self._format_timestamp(segment_end)
            
            ass_content += f"Dialogue: 0,{start_time},{end_time},Default,,0,0,0,,{karaoke_text}\n"
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(ass_content)