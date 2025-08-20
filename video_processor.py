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

    async def download_video(self, url: str, output_path: Path, extra_headers: dict | None = None) -> None:
        # Use browser-like headers to avoid upstream WAF blocks (e.g., CloudFront/HeyGen)
        headers_primary = self._default_headers()
        headers_secondary = self._alt_headers()

        # Heuristics for specific providers
        if "heygen.ai" in url.lower():
            headers_primary.update({
                "Referer": "https://app.heygen.com/",
                "Origin": "https://app.heygen.com",
            })
            headers_secondary.update({
                "Referer": "https://app.heygen.com/",
                "Origin": "https://app.heygen.com",
            })

        # Allow caller overrides
        if extra_headers:
            headers_primary.update(extra_headers)
            headers_secondary.update(extra_headers)

        response = requests.get(
            url,
            headers=headers_primary,
            stream=True,
            allow_redirects=True,
            # Avoid proxy/env rewriting
            trust_env=False,
            timeout=(10, 180)
        )

        # Retry with alternate headers if forbidden
        if response.status_code == 403:
            try:
                response.close()
            except Exception:
                pass
            response = requests.get(
                url,
                headers=headers_secondary,
                stream=True,
                allow_redirects=True,
                trust_env=False,
                timeout=(10, 180)
            )

        try:
            response.raise_for_status()
        except requests.HTTPError as http_err:
            # Capture upstream error body for diagnostics (non-streaming fetch)
            try:
                diag = requests.get(url, headers=headers_secondary, timeout=(10, 30), trust_env=False)
                body_snippet = diag.text[:500]
            except Exception:
                body_snippet = "(no upstream body)"
            raise Exception(
                f"Failed to download video ({response.status_code}). If this is a signed URL (e.g., HeyGen), it may be blocked by their WAF for server-side requests. "
                f"Try again with a fresh link or provide a direct file upload. Upstream response snippet: {body_snippet}"
            ) from http_err

        async with aiofiles.open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=self.chunk_size):
                if chunk:
                    await f.write(chunk)

    def extract_audio(self, video_path: Path, audio_path: Path) -> None:
        try:
            (
                ffmpeg
                .input(str(video_path))
                .output(str(audio_path), acodec='pcm_s16le', ac=1, ar='16000')
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

    def _default_headers(self) -> dict:
        # Standard modern browser UA and typical headers to look like a regular client
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }

    def _alt_headers(self) -> dict:
        # Alternate headers if a WAF blocks the default UA or encoding
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
                "Gecko/20100101 Firefox/125.0"
            ),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            # Avoid compression to reduce edge-case issues when proxies mangle content
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
        }