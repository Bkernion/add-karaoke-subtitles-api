import os
import asyncio
from pathlib import Path
from typing import Union

import aiofiles
import requests
import ffmpeg

class VideoProcessor:
    def __init__(self):
        self.chunk_size = 8192

    async def download_video(self, url: str, output_path: Path) -> None:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        async with aiofiles.open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                if chunk:
                    await f.write(chunk)

    def extract_audio(self, video_path: Path, audio_path: Path) -> None:
        try:
            (
                ffmpeg
                .input(str(video_path))
                .output(str(audio_path), acodec='pcm_s16le', ac=1, ar='8000')
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
        except ffmpeg.Error as e:
            raise Exception(f"Error extracting audio: {e.stderr.decode()}")

    def burn_subtitles(self, video_path: Path, subtitle_path: Path, output_path: Path) -> None:
        try:
            input_video = ffmpeg.input(str(video_path))
            
            # High-quality settings optimized for compatibility
            output = ffmpeg.output(
                input_video,
                str(output_path),
                vf=f"ass={subtitle_path}",
                vcodec='libx264',          # H.264 codec
                acodec='aac',              # AAC audio codec
                crf=28,                    # Balanced quality (lower = better, 28 is good for speed)
                preset='veryfast',        # Very fast encoding (good speed/quality balance)
                profile='high',            # H.264 high profile
                pix_fmt='yuv420p',        # Standard pixel format for compatibility
                movflags='+faststart',    # Optimize for web streaming
                **{'b:a': '320k'},        # High-quality audio bitrate
                ar=48000,                 # High audio sample rate
                ac=2,                     # Stereo audio
            )
            
            print(f"🎬 Encoding with CPU-optimized settings (CRF=28, preset=veryfast, 320k audio)")
            ffmpeg.run(output, overwrite_output=True, capture_stdout=True, capture_stderr=True)
            
        except ffmpeg.Error as e:
            raise Exception(f"Error burning subtitles: {e.stderr.decode()}")

    def get_video_info(self, video_path: Path) -> dict:
        try:
            probe = ffmpeg.probe(str(video_path))
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if video_stream is None:
                raise Exception("No video stream found")
            
            return {
                'duration': float(probe['format']['duration']),
                'width': int(video_stream['width']),
                'height': int(video_stream['height']),
                'fps': eval(video_stream['r_frame_rate'])
            }
        except ffmpeg.Error as e:
            raise Exception(f"Error getting video info: {e.stderr.decode()}")