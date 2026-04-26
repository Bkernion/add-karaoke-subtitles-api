import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any

import gc
import aiofiles
import requests
import ffmpeg
from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel
from slugify import slugify
import base64

from subtitle_generator import KaraokeSubtitleGenerator
from video_processor import VideoProcessor
from caption_parser import parse_caption_file
from style_engine import StyleEngine
from frame_generator import FrameGenerator, FrameDimensions
from video_assembler import VideoAssembler, create_frames_with_timing, create_frames_with_timing_from_paths
from font_registry import get_default_registry, resolve_font_name

app = FastAPI(title="Karaoke Subtitle API", version="1.0.0")

PUBLIC_DIR = Path("public")
PUBLIC_DIR.mkdir(exist_ok=True)
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

class VideoRequest(BaseModel):
    video_url: str  # Keep exact presigned URL without normalization
    font_name: str = "Arial Rounded MT Bold"
    font_size: int = 24
    font_color: str = "#FFFFFF"  # White by default
    highlight_color: str = "#FFFF00"  # Yellow by default
    subtitle_position: float = None  # Optional: 0.0 = top, 1.0 = bottom, 0.75 = 3/4 down
    headers: Dict[str, str] | None = None  # Optional: extra request headers for fetching
    base64_urls: bool | None = None  # If true, the URLs are base64-encoded

class VideoRequestWithASS(BaseModel):
    video_url: str  # Keep exact presigned URL
    ass_url: str  # Keep exact ASS URL
    font_name: str = "Arial Rounded MT Bold"
    font_size: int = 24
    font_color: str = "#FFFFFF"  # White by default
    highlight_color: str = "#FFFF00"  # Yellow by default
    subtitle_position: float = None  # Optional: 0.0 = top, 1.0 = bottom, 0.75 = 3/4 down
    headers: Dict[str, str] | None = None  # Optional: extra request headers for fetching
    base64_urls: bool | None = None  # If true, the URLs are base64-encoded

class VideoResponse(BaseModel):
    status: str
    download_url: str
    message: str = ""


class ArtisticVideoRequest(BaseModel):
    """Request model for artistic word-by-word video generation.

    Accepts caption files (.ass/.srt) via URL and audio via URL.
    At least one of audio_url or video_url must be provided.
    If video_url is provided, audio will be extracted from it.
    """
    caption_url: str | None = None  # Optional URL to .ass or .srt caption file
    audio_url: str | None = None  # Optional URL to audio file (.mp3, .wav)
    video_url: str | None = None  # Optional URL to video (audio will be extracted)
    output_format: str = "9:16"  # Output format: "9:16" (portrait), "1:1" (square), "16:9" (landscape)
    headers: Dict[str, str] | None = None  # Optional headers for fetching URLs
    base64_urls: bool | None = None  # If true, URLs are base64-encoded

    def model_post_init(self, __context: Any) -> None:
        """Validate that at least one audio source is provided."""
        if not self.audio_url and not self.video_url:
            raise ValueError("At least one of audio_url or video_url must be provided")
        if self.output_format not in ("9:16", "1:1", "16:9"):
            raise ValueError("output_format must be one of: 9:16, 1:1, 16:9")


class ArtisticVideoResponse(BaseModel):
    """Response model for artistic video generation."""
    status: str
    download_url: str
    message: str = ""


class FontUploadResponse(BaseModel):
    """Response model for font upload."""
    status: str
    font_name: str
    message: str = ""


class FontListResponse(BaseModel):
    """Response model for listing available fonts."""
    fonts: list[str]
    count: int


# TTF magic bytes: The first 4 bytes of a valid TrueType font file
# Can be: 0x00010000 (TrueType), 0x4F54544F (OpenType 'OTTO'), or 0x74727565 ('true')
TTF_MAGIC_BYTES = [
    b'\x00\x01\x00\x00',  # TrueType
    b'\x4F\x54\x54\x4F',  # OpenType (OTTO)
    b'\x74\x72\x75\x65',  # 'true' (TrueType on Mac)
]


def is_valid_ttf(content: bytes) -> bool:
    """
    Validate that the file content appears to be a valid TTF/OTF font file.

    Args:
        content: The file content bytes.

    Returns:
        True if the file starts with valid TTF magic bytes, False otherwise.
    """
    if len(content) < 4:
        return False
    header = content[:4]
    return any(header == magic for magic in TTF_MAGIC_BYTES)


def sanitize_font_filename(filename: str) -> str:
    """
    Sanitize a font filename to prevent path traversal and invalid characters.

    Args:
        filename: The original filename.

    Returns:
        A sanitized filename safe for filesystem use.
    """
    # Extract base name (remove any path components)
    base_name = os.path.basename(filename)

    # Remove .ttf extension if present (we'll add it back)
    if base_name.lower().endswith('.ttf'):
        base_name = base_name[:-4]
    elif base_name.lower().endswith('.otf'):
        base_name = base_name[:-4]

    # Use slugify to create a safe filename, but preserve case
    # Remove special characters, keeping only alphanumeric and spaces
    safe_chars = []
    for char in base_name:
        if char.isalnum() or char in ' -_':
            safe_chars.append(char)
    safe_name = ''.join(safe_chars).strip()

    # Replace spaces with nothing to create CamelCase-like names
    parts = safe_name.split()
    if parts:
        # Capitalize first letter of each part for consistent naming
        safe_name = ''.join(part.capitalize() if part else '' for part in parts)

    # Fallback if empty after sanitization
    if not safe_name:
        safe_name = 'CustomFont'

    return safe_name + '.ttf'


@app.post("/generate-karaoke-subtitles", response_model=VideoResponse)
async def generate_karaoke_subtitles(video_request: VideoRequest, request: Request) -> VideoResponse:
    try:
        unique_id = str(uuid.uuid4())[:8]

        video_processor = VideoProcessor()
        subtitle_generator = KaraokeSubtitleGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            input_video_path = temp_path / f"{unique_id}_input.mp4"
            audio_path = temp_path / f"{unique_id}_audio.wav"
            subtitle_path = temp_path / f"{unique_id}_subtitles.ass"
            output_video_path = PUBLIC_DIR / f"{unique_id}_final.mp4"
            
            video_url = video_request.video_url
            if video_request.base64_urls:
                try:
                    video_url = base64.b64decode(video_url).decode("utf-8")
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid base64 video_url")
            await video_processor.download_video(str(video_url), input_video_path, extra_headers=video_request.headers)
            
            video_info = video_processor.get_video_info(input_video_path)
            
            raise HTTPException(
                status_code=400,
                detail="Whisper transcription has been removed to reduce memory usage. "
                       "Please use /generate-with-ass-file or /generate-artistic-video with a caption file instead."
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")

@app.get("/")
@app.head("/")
async def root():
    return {
        "service": "Karaoke Subtitle API", 
        "status": "running",
        "endpoints": {
            "health": "/health",
            "generate": "/generate-karaoke-subtitles",
            "generate-with-ass": "/generate-with-ass-file",
            "docs": "/docs"
        }
    }

@app.get("/health")
@app.head("/health")
async def health_check():
    return {"status": "healthy", "service": "Karaoke Subtitle API"}

@app.get("/test")
async def test_endpoint():
    return {"message": "Test endpoint working", "timestamp": "2025-01-24"}

@app.post("/generate-karaoke-subtitles-simple")
async def generate_karaoke_subtitles_simple(video_request: VideoRequest, request: Request):
    """Alternative endpoint that returns just the URL as plain text"""
    try:
        unique_id = str(uuid.uuid4())[:8]

        video_processor = VideoProcessor()
        subtitle_generator = KaraokeSubtitleGenerator()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            input_video_path = temp_path / f"{unique_id}_input.mp4"
            audio_path = temp_path / f"{unique_id}_audio.wav"
            subtitle_path = temp_path / f"{unique_id}_subtitles.ass"
            output_video_path = PUBLIC_DIR / f"{unique_id}_final.mp4"
            
            video_url = video_request.video_url
            if video_request.base64_urls:
                try:
                    video_url = base64.b64decode(video_url).decode("utf-8")
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid base64 video_url")
            raise HTTPException(
                status_code=400,
                detail="Whisper transcription has been removed to reduce memory usage. "
                       "Please use /generate-with-ass-file or /generate-artistic-video with a caption file instead."
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")

async def download_ass_file(ass_url: str, output_path: Path, extra_headers: Dict[str, str] | None = None) -> None:
    """Download ASS subtitle file from URL with resilient headers"""
    headers_primary = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }
    headers_secondary = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
            "Gecko/20100101 Firefox/125.0"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }

    # Provider heuristics
    if "heygen.ai" in str(ass_url).lower():
        headers_primary.update({
            "Referer": "https://app.heygen.com/",
            "Origin": "https://app.heygen.com",
        })
        headers_secondary.update({
            "Referer": "https://app.heygen.com/",
            "Origin": "https://app.heygen.com",
        })

    if extra_headers:
        headers_primary.update(extra_headers)
        headers_secondary.update(extra_headers)

    session = requests.Session()
    session.trust_env = False
    # Preserve exact URL without re-encoding
    req1 = requests.Request("GET", str(ass_url), headers=headers_primary)
    prepped1 = session.prepare_request(req1)
    prepped1.url = str(ass_url)
    response = session.send(prepped1, stream=True, allow_redirects=True, timeout=(10, 60))
    if response.status_code == 403:
        try:
            response.close()
        except Exception:
            pass
        req2 = requests.Request("GET", str(ass_url), headers=headers_secondary)
        prepped2 = session.prepare_request(req2)
        prepped2.url = str(ass_url)
        response = session.send(prepped2, stream=True, allow_redirects=True, timeout=(10, 60))
    response.raise_for_status()
    
    async with aiofiles.open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                await f.write(chunk)

@app.post("/generate-with-ass-file")
async def generate_with_ass_file(video_request: VideoRequestWithASS, request: Request):
    """Generate video with subtitles using provided ASS file from HeyGen"""
    try:
        unique_id = str(uuid.uuid4())[:8]

        video_processor = VideoProcessor()
        subtitle_generator = KaraokeSubtitleGenerator()  # No whisper model needed

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            input_video_path = temp_path / f"{unique_id}_input.mp4"
            heygen_ass_path = temp_path / f"{unique_id}_heygen.ass"
            custom_subtitle_path = temp_path / f"{unique_id}_subtitles.ass"
            output_video_path = PUBLIC_DIR / f"{unique_id}_final.mp4"

            # Prepare URLs (optional base64 decoding)
            video_url = video_request.video_url
            ass_url = video_request.ass_url
            if video_request.base64_urls:
                try:
                    video_url = base64.b64decode(video_url).decode("utf-8")
                    ass_url = base64.b64decode(ass_url).decode("utf-8")
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid base64 URLs")

            # Download video
            await video_processor.download_video(str(video_url), input_video_path, extra_headers=video_request.headers)

            # Download ASS file from HeyGen
            await download_ass_file(str(ass_url), heygen_ass_path, extra_headers=video_request.headers)
            print(f"📥 Downloaded HeyGen ASS file: {heygen_ass_path.stat().st_size} bytes")

            # Get video info for proper formatting
            video_info = video_processor.get_video_info(input_video_path)
            print(f"🎥 Video info: {video_info['width']}x{video_info['height']}")

            # Parse HeyGen ASS file to extract timing and words
            transcription = subtitle_generator.parse_ass_file(heygen_ass_path)
            print(f"📝 Parsed {len(transcription.get('segments', []))} segments from ASS file")
            print(f"📝 Total text: {transcription.get('text', '')[:100]}...")

            # Resolve font_name -> canonical TTF family name for libass.
            # Bundled fonts often have a family name with spaces ("Zen Dots")
            # that doesn't match the filename ("ZenDots"); without this fix
            # libass silently falls back to a default sans.
            requested_font = video_request.font_name
            resolved_font = resolve_font_name(requested_font)
            font_name_for_ass = resolved_font or requested_font
            if resolved_font and resolved_font != requested_font:
                print(f"🔤 Resolved font '{requested_font}' -> '{resolved_font}'")
            elif not resolved_font:
                print(f"🔤 Font '{requested_font}' not in bundled set; "
                      f"passing through to fontconfig")

            # Generate new ASS file with custom formatting using HeyGen's timing
            subtitle_generator.generate_ass_file(
                transcription,
                custom_subtitle_path,
                font_name=font_name_for_ass,
                font_size=video_request.font_size,
                font_color=video_request.font_color,
                highlight_color=video_request.highlight_color,
                video_width=video_info['width'],
                video_height=video_info['height'],
                subtitle_position=video_request.subtitle_position,
                enable_karaoke=True  # Enable karaoke timing for highlight effect
            )
            print(f"✍️ Generated custom ASS file: {custom_subtitle_path.stat().st_size} bytes")

            # Burn subtitles with custom formatting
            print(f"🔥 Burning subtitles into video...")
            video_processor.burn_subtitles(input_video_path, custom_subtitle_path, output_video_path)
            print(f"✅ Final video created: {output_video_path.stat().st_size} bytes")

            # Construct full URL - force HTTPS for production
            if "onrender.com" in str(request.url.netloc):
                base_url = f"https://{request.url.netloc}"
            else:
                base_url = f"{request.url.scheme}://{request.url.netloc}"

            download_url = f"{base_url}/public/{unique_id}_final.mp4"

            # Return just the URL as plain text (like simple endpoint)
            return Response(content=download_url, media_type="text/plain")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")
    finally:
        gc.collect()


async def download_file(url: str, output_path: Path, extra_headers: Dict[str, str] | None = None) -> None:
    """Download a file from URL with resilient headers (for caption or audio files)."""
    headers_primary = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }
    headers_secondary = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
            "Gecko/20100101 Firefox/125.0"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }

    if extra_headers:
        headers_primary.update(extra_headers)
        headers_secondary.update(extra_headers)

    session = requests.Session()
    session.trust_env = False
    req1 = requests.Request("GET", str(url), headers=headers_primary)
    prepped1 = session.prepare_request(req1)
    prepped1.url = str(url)
    response = session.send(prepped1, stream=True, allow_redirects=True, timeout=(10, 120))
    if response.status_code == 403:
        try:
            response.close()
        except Exception:
            pass
        req2 = requests.Request("GET", str(url), headers=headers_secondary)
        prepped2 = session.prepare_request(req2)
        prepped2.url = str(url)
        response = session.send(prepped2, stream=True, allow_redirects=True, timeout=(10, 120))
    response.raise_for_status()

    async with aiofiles.open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                await f.write(chunk)


@app.post("/generate-artistic-video", response_model=ArtisticVideoResponse)
async def generate_artistic_video(video_request: ArtisticVideoRequest, request: Request):
    """
    Generate an artistic word-by-word video with dynamic typography.

    Creates scroll-stopping social media videos where each word appears on its own
    artistic frame with varying fonts, colors, positions, backgrounds, and effects.

    Accepts caption files (.ass/.srt) via URL and audio via URL.
    If video_url is provided instead of audio_url, audio will be extracted from it.
    A caption_url (.ass or .srt) is required for word-level timing.
    """
    try:
        unique_id = str(uuid.uuid4())[:8]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Decode base64 URLs if needed
            caption_url = video_request.caption_url
            audio_url = video_request.audio_url
            video_url = video_request.video_url
            if video_request.base64_urls:
                try:
                    if caption_url:
                        caption_url = base64.b64decode(caption_url).decode("utf-8")
                    if audio_url:
                        audio_url = base64.b64decode(audio_url).decode("utf-8")
                    if video_url:
                        video_url = base64.b64decode(video_url).decode("utf-8")
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid base64 URLs")

            # Validate that we have an audio source
            if not audio_url and not video_url:
                raise HTTPException(
                    status_code=400,
                    detail="At least one of audio_url or video_url must be provided"
                )

            # Caption file is required (Whisper removed for memory savings)
            if not caption_url:
                raise HTTPException(
                    status_code=400,
                    detail="caption_url is required. Provide a .ass or .srt caption file URL for word-level timing."
                )

            # Set up paths
            audio_path = temp_path / f"{unique_id}_audio.wav"
            output_video_path = PUBLIC_DIR / f"{unique_id}_artistic.mp4"

            # If caption_url is provided, download and set up caption file
            caption_path: Path | None = None
            if caption_url:
                # Determine caption file extension from URL
                caption_ext = ".ass"
                caption_url_lower = caption_url.lower()
                if ".srt" in caption_url_lower:
                    caption_ext = ".srt"
                elif ".ass" in caption_url_lower or ".ssa" in caption_url_lower:
                    caption_ext = ".ass"

                caption_path = temp_path / f"{unique_id}_caption{caption_ext}"

                # Download caption file
                print(f"📥 Downloading caption file...")
                await download_file(str(caption_url), caption_path, extra_headers=video_request.headers)
                print(f"✅ Caption downloaded: {caption_path.stat().st_size} bytes")

            # Get audio - either download directly or extract from video
            video_processor = VideoProcessor()
            if audio_url:
                # Download audio file directly
                audio_download_path = temp_path / f"{unique_id}_audio_download.mp3"
                print(f"📥 Downloading audio file...")
                await download_file(str(audio_url), audio_download_path, extra_headers=video_request.headers)
                print(f"✅ Audio downloaded: {audio_download_path.stat().st_size} bytes")

                # Convert to WAV for consistent processing (or use directly if already compatible)
                # For simplicity, we'll convert to WAV
                try:
                    ffmpeg.input(str(audio_download_path)).output(
                        str(audio_path),
                        acodec='pcm_s16le',
                        ac=1,
                        ar='16000'
                    ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
                except ffmpeg.Error as e:
                    # If conversion fails, try using the original file directly
                    audio_path = audio_download_path
            else:
                # Extract audio from video
                input_video_path = temp_path / f"{unique_id}_input_video.mp4"
                print(f"📥 Downloading video for audio extraction...")
                await video_processor.download_video(str(video_url), input_video_path, extra_headers=video_request.headers)
                print(f"✅ Video downloaded: {input_video_path.stat().st_size} bytes")

                print(f"🎵 Extracting audio from video...")
                video_processor.extract_audio(input_video_path, audio_path)
                print(f"✅ Audio extracted: {audio_path.stat().st_size} bytes")

            # Get word-level timing from caption file
            print(f"📝 Parsing captions...")
            word_timings = parse_caption_file(caption_path)
            print(f"✅ Parsed {len(word_timings)} words from captions")

            if not word_timings:
                raise HTTPException(
                    status_code=400,
                    detail="No words found in caption file"
                )

            # Extract just the words for style generation (cast to str for type safety)
            words: list[str] = [str(wt["word"]) for wt in word_timings]

            # Generate styles for each word
            print(f"🎨 Generating styles for {len(words)} words...")
            style_engine = StyleEngine()
            styles = style_engine.generate_styles_for_words(words)
            print(f"✅ Styles generated")

            # Generate frames for each word (streamed to disk)
            print(f"🖼️ Generating frames...")
            dimensions = FrameDimensions.from_format_string(video_request.output_format)
            frame_generator = FrameGenerator(default_dimensions=dimensions)
            frame_paths = frame_generator.generate_frames_to_disk(words, styles, temp_path, dimensions)
            print(f"✅ Generated {len(frame_paths)} frames")

            # Create frames with timing for video assembly
            timings: list[dict[str, float]] = [
                {"start_time": float(wt["start_time"]), "end_time": float(wt["end_time"])}
                for wt in word_timings
            ]
            frames_with_timing = create_frames_with_timing_from_paths(frame_paths, timings)

            # Assemble video with audio
            print(f"🎬 Assembling video...")
            video_assembler = VideoAssembler()
            # Cast output_format to Literal type for type safety
            from typing import cast
            from video_assembler import OutputFormat
            output_format_literal = cast(OutputFormat, video_request.output_format)
            video_assembler.assemble(
                frames_with_timing,
                audio_path,
                output_video_path,
                output_format_literal
            )
            print(f"✅ Video assembled: {output_video_path.stat().st_size} bytes")

            # Construct download URL
            if "onrender.com" in str(request.url.netloc):
                base_url = f"https://{request.url.netloc}"
            else:
                base_url = f"{request.url.scheme}://{request.url.netloc}"

            download_url = f"{base_url}/public/{unique_id}_artistic.mp4"

            return ArtisticVideoResponse(
                status="success",
                download_url=download_url,
                message=f"Artistic video generated successfully with {len(words)} words"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating artistic video: {str(e)}")
    finally:
        gc.collect()


@app.post("/generate-artistic-video-upload", response_model=ArtisticVideoResponse)
async def generate_artistic_video_upload(
    request: Request,
    caption_file: UploadFile | None = File(None, description="Optional .ass or .srt caption file"),
    audio_file: UploadFile | None = File(None, description="Optional audio file (.mp3, .wav)"),
    video_file: UploadFile | None = File(None, description="Optional video file (audio will be extracted)"),
    output_format: str = Form("9:16", description="Output format: 9:16, 1:1, or 16:9"),
):
    """
    Generate an artistic word-by-word video with dynamic typography using file uploads.

    Creates scroll-stopping social media videos where each word appears on its own
    artistic frame with varying fonts, colors, positions, backgrounds, and effects.

    Accepts caption files (.ass/.srt) and audio via file upload.
    If video_file is provided instead of audio_file, audio will be extracted from it.
    A caption_file (.ass or .srt) is required for word-level timing.
    """
    try:
        # Validate output format
        if output_format not in ("9:16", "1:1", "16:9"):
            raise HTTPException(
                status_code=400,
                detail="output_format must be one of: 9:16, 1:1, 16:9"
            )

        # Validate that at least one audio source is provided
        if not audio_file and not video_file:
            raise HTTPException(
                status_code=400,
                detail="At least one of audio_file or video_file must be provided"
            )

        # Caption file is required (Whisper removed for memory savings)
        if not caption_file:
            raise HTTPException(
                status_code=400,
                detail="caption_file is required. Provide a .ass or .srt caption file for word-level timing."
            )

        unique_id = str(uuid.uuid4())[:8]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Set up paths
            audio_path = temp_path / f"{unique_id}_audio.wav"
            output_video_path = PUBLIC_DIR / f"{unique_id}_artistic.mp4"

            # If caption_file is provided, save it
            caption_path: Path | None = None
            if caption_file:
                # Determine caption file extension from filename
                caption_ext = ".ass"
                if caption_file.filename:
                    filename_lower = caption_file.filename.lower()
                    if filename_lower.endswith(".srt"):
                        caption_ext = ".srt"
                    elif filename_lower.endswith(".ass") or filename_lower.endswith(".ssa"):
                        caption_ext = ".ass"

                caption_path = temp_path / f"{unique_id}_caption{caption_ext}"

                # Save caption file
                print(f"📥 Saving caption file...")
                async with aiofiles.open(caption_path, 'wb') as f:
                    content = await caption_file.read()
                    await f.write(content)
                print(f"✅ Caption saved: {caption_path.stat().st_size} bytes")

            # Get audio - either from audio file or extract from video
            video_processor = VideoProcessor()
            if audio_file:
                # Save audio file and convert to WAV
                audio_download_path = temp_path / f"{unique_id}_audio_upload.mp3"
                print(f"📥 Saving audio file...")
                async with aiofiles.open(audio_download_path, 'wb') as f:
                    content = await audio_file.read()
                    await f.write(content)
                print(f"✅ Audio saved: {audio_download_path.stat().st_size} bytes")

                # Convert to WAV for consistent processing
                try:
                    ffmpeg.input(str(audio_download_path)).output(
                        str(audio_path),
                        acodec='pcm_s16le',
                        ac=1,
                        ar='16000'
                    ).overwrite_output().run(capture_stdout=True, capture_stderr=True)
                except ffmpeg.Error:
                    # If conversion fails, try using the original file directly
                    audio_path = audio_download_path
            else:
                # Extract audio from video file
                input_video_path = temp_path / f"{unique_id}_input_video.mp4"
                print(f"📥 Saving video file for audio extraction...")
                async with aiofiles.open(input_video_path, 'wb') as f:
                    content = await video_file.read()  # type: ignore[union-attr]
                    await f.write(content)
                print(f"✅ Video saved: {input_video_path.stat().st_size} bytes")

                print(f"🎵 Extracting audio from video...")
                video_processor.extract_audio(input_video_path, audio_path)
                print(f"✅ Audio extracted: {audio_path.stat().st_size} bytes")

            # Get word-level timing from caption file
            print(f"📝 Parsing captions...")
            word_timings = parse_caption_file(caption_path)
            print(f"✅ Parsed {len(word_timings)} words from captions")

            if not word_timings:
                raise HTTPException(
                    status_code=400,
                    detail="No words found in caption file"
                )

            # Extract just the words for style generation (cast to str for type safety)
            words: list[str] = [str(wt["word"]) for wt in word_timings]

            # Generate styles for each word
            print(f"🎨 Generating styles for {len(words)} words...")
            style_engine = StyleEngine()
            styles = style_engine.generate_styles_for_words(words)
            print(f"✅ Styles generated")

            # Generate frames for each word (streamed to disk)
            print(f"🖼️ Generating frames...")
            dimensions = FrameDimensions.from_format_string(output_format)
            frame_generator = FrameGenerator(default_dimensions=dimensions)
            frame_paths = frame_generator.generate_frames_to_disk(words, styles, temp_path, dimensions)
            print(f"✅ Generated {len(frame_paths)} frames")

            # Create frames with timing for video assembly
            timings: list[dict[str, float]] = [
                {"start_time": float(wt["start_time"]), "end_time": float(wt["end_time"])}
                for wt in word_timings
            ]
            frames_with_timing = create_frames_with_timing_from_paths(frame_paths, timings)

            # Assemble video with audio
            print(f"🎬 Assembling video...")
            video_assembler = VideoAssembler()
            from typing import cast
            from video_assembler import OutputFormat
            output_format_literal = cast(OutputFormat, output_format)
            video_assembler.assemble(
                frames_with_timing,
                audio_path,
                output_video_path,
                output_format_literal
            )
            print(f"✅ Video assembled: {output_video_path.stat().st_size} bytes")

            # Construct download URL
            if "onrender.com" in str(request.url.netloc):
                base_url = f"https://{request.url.netloc}"
            else:
                base_url = f"{request.url.scheme}://{request.url.netloc}"

            download_url = f"{base_url}/public/{unique_id}_artistic.mp4"

            return ArtisticVideoResponse(
                status="success",
                download_url=download_url,
                message=f"Artistic video generated successfully with {len(words)} words"
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating artistic video: {str(e)}")
    finally:
        gc.collect()


# Font directory path
FONTS_DIR = Path(__file__).parent / "fonts"


@app.post("/upload-font", response_model=FontUploadResponse)
async def upload_font(
    font_file: UploadFile = File(..., description="TTF font file to upload"),
):
    """
    Upload a custom TTF font for use in artistic video generation.

    Accepts a TTF font file, validates it, and saves it to the fonts directory
    with a sanitized filename. The font will be immediately available for use
    in subsequent video generation requests.

    Args:
        font_file: The TTF font file to upload.

    Returns:
        FontUploadResponse with the font name to use in future requests.
    """
    try:
        # Read file content
        content = await font_file.read()

        # Validate file size (limit to 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(content) > max_size:
            raise HTTPException(
                status_code=400,
                detail="Font file too large. Maximum size is 10MB."
            )

        # Validate TTF magic bytes
        if not is_valid_ttf(content):
            raise HTTPException(
                status_code=400,
                detail="Invalid font file. File must be a valid TTF or OTF font."
            )

        # Get original filename and sanitize it
        original_filename = font_file.filename or "CustomFont.ttf"
        safe_filename = sanitize_font_filename(original_filename)

        # Ensure fonts directory exists
        FONTS_DIR.mkdir(exist_ok=True)

        # Generate unique filename if font already exists
        font_path = FONTS_DIR / safe_filename
        if font_path.exists():
            # Add a unique suffix to avoid overwriting
            base_name = safe_filename[:-4]  # Remove .ttf
            counter = 1
            while font_path.exists():
                safe_filename = f"{base_name}_{counter}.ttf"
                font_path = FONTS_DIR / safe_filename
                counter += 1

        # Save the font file
        async with aiofiles.open(font_path, 'wb') as f:
            await f.write(content)

        # Refresh the font registry to pick up the new font
        font_registry = get_default_registry()
        font_registry.refresh()

        # Extract font name (without .ttf extension) for response
        font_name = safe_filename[:-4]

        print(f"📥 Font uploaded: {font_name} ({len(content)} bytes)")

        return FontUploadResponse(
            status="success",
            font_name=font_name,
            message=f"Font '{font_name}' uploaded successfully and is now available for use"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading font: {str(e)}")


@app.get("/fonts", response_model=FontListResponse)
async def list_fonts():
    """
    List all available fonts for artistic video generation.

    Returns a list of font names that can be used in video generation requests.
    This includes both bundled fonts and any custom fonts uploaded via /upload-font.

    Returns:
        FontListResponse with list of font names and count.
    """
    font_registry = get_default_registry()
    fonts = font_registry.get_available_fonts()

    return FontListResponse(
        fonts=fonts,
        count=len(fonts)
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))  # Changed default to 10000 for Render
    print(f"🚀 Starting Karaoke Subtitle API on port {port}")
    print(f"📋 Health check: http://0.0.0.0:{port}/health")
    print(f"📖 API docs: http://0.0.0.0:{port}/docs")
    print("✋ Press Ctrl+C to stop the server")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)