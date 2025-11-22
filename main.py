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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))  # Changed default to 10000 for Render
    print(f"🚀 Starting Karaoke Subtitle API on port {port}")
    print(f"📋 Health check: http://0.0.0.0:{port}/health")
    print(f"📖 API docs: http://0.0.0.0:{port}/docs")
    print("✋ Press Ctrl+C to stop the server")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)