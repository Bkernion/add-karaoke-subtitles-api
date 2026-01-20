import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any

import aiofiles
import requests
import whisper
import ffmpeg
from fastapi import FastAPI, HTTPException, Request
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
from video_assembler import VideoAssembler, create_frames_with_timing

app = FastAPI(title="Karaoke Subtitle API", version="1.0.0")

# Load Whisper model once at startup
whisper_model = whisper.load_model("base")

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

@app.post("/generate-karaoke-subtitles", response_model=VideoResponse)
async def generate_karaoke_subtitles(video_request: VideoRequest, request: Request) -> VideoResponse:
    try:
        unique_id = str(uuid.uuid4())[:8]
        
        video_processor = VideoProcessor()
        subtitle_generator = KaraokeSubtitleGenerator(whisper_model)
        
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
            
            video_processor.extract_audio(input_video_path, audio_path)
            
            transcription = subtitle_generator.transcribe_with_timing(audio_path)
            
            subtitle_generator.generate_ass_file(
                transcription, 
                subtitle_path,
                font_name=video_request.font_name,
                font_size=video_request.font_size,
                font_color=video_request.font_color,
                highlight_color=video_request.highlight_color,
                video_width=video_info['width'],
                video_height=video_info['height'],
                subtitle_position=video_request.subtitle_position
            )
            
            video_processor.burn_subtitles(input_video_path, subtitle_path, output_video_path)
            
            # Construct full URL - force HTTPS for production
            if "onrender.com" in str(request.url.netloc):
                base_url = f"https://{request.url.netloc}"
            else:
                base_url = f"{request.url.scheme}://{request.url.netloc}"
            
            download_url = f"{base_url}/public/{unique_id}_final.mp4"
            
            # Debug logging
            print(f"🔗 Generated download URL: {download_url}")
            
            response_data = {
                "status": "success",
                "download_url": download_url,
                "message": "Karaoke subtitles generated successfully"
            }
            
            # Debug the response
            print(f"📋 Response data: {response_data}")
            
            # Use standard Response to ensure cleanest JSON
            import json
            json_string = json.dumps(response_data, ensure_ascii=False, separators=(',', ':'))
            
            return Response(
                content=json_string,
                media_type="application/json",
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Cache-Control": "no-cache",
                    "Access-Control-Allow-Origin": "*"
                }
            )
            
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
        subtitle_generator = KaraokeSubtitleGenerator(whisper_model)
        
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
            
            video_processor.extract_audio(input_video_path, audio_path)
            
            transcription = subtitle_generator.transcribe_with_timing(audio_path)
            
            subtitle_generator.generate_ass_file(
                transcription, 
                subtitle_path,
                font_name=video_request.font_name,
                font_size=video_request.font_size,
                font_color=video_request.font_color,
                highlight_color=video_request.highlight_color,
                video_width=video_info['width'],
                video_height=video_info['height'],
                subtitle_position=video_request.subtitle_position
            )
            
            video_processor.burn_subtitles(input_video_path, subtitle_path, output_video_path)
            
            # Return just the URL as plain text
            if "onrender.com" in str(request.url.netloc):
                base_url = f"https://{request.url.netloc}"
            else:
                base_url = f"{request.url.scheme}://{request.url.netloc}"
            
            download_url = f"{base_url}/public/{unique_id}_final.mp4"
            
            return Response(content=download_url, media_type="text/plain")
            
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

            # Generate new ASS file with custom formatting using HeyGen's timing
            subtitle_generator.generate_ass_file(
                transcription,
                custom_subtitle_path,
                font_name=video_request.font_name,
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

            # Validate that we have a caption source
            if not caption_url:
                raise HTTPException(
                    status_code=400,
                    detail="caption_url is required for this endpoint"
                )

            # Determine caption file extension from URL
            caption_ext = ".ass"
            if caption_url:
                caption_url_lower = caption_url.lower()
                if ".srt" in caption_url_lower:
                    caption_ext = ".srt"
                elif ".ass" in caption_url_lower or ".ssa" in caption_url_lower:
                    caption_ext = ".ass"

            caption_path = temp_path / f"{unique_id}_caption{caption_ext}"
            audio_path = temp_path / f"{unique_id}_audio.wav"
            output_video_path = PUBLIC_DIR / f"{unique_id}_artistic.mp4"

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

            # Parse captions to get word-level timing
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

            # Generate frames for each word
            print(f"🖼️ Generating frames...")
            dimensions = FrameDimensions.from_format_string(video_request.output_format)
            frame_generator = FrameGenerator(default_dimensions=dimensions)
            images = frame_generator.generate_frames_for_words(words, styles, dimensions)
            print(f"✅ Generated {len(images)} frames")

            # Create frames with timing for video assembly
            # Convert to the expected timing format
            timings: list[dict[str, float]] = [
                {"start_time": float(wt["start_time"]), "end_time": float(wt["end_time"])}
                for wt in word_timings
            ]
            frames_with_timing = create_frames_with_timing(images, timings)

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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))  # Changed default to 10000 for Render
    print(f"🚀 Starting Karaoke Subtitle API on port {port}")
    print(f"📋 Health check: http://0.0.0.0:{port}/health")
    print(f"📖 API docs: http://0.0.0.0:{port}/docs")
    print("✋ Press Ctrl+C to stop the server")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)