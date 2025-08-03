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
from pydantic import BaseModel, HttpUrl
from slugify import slugify

from subtitle_generator import KaraokeSubtitleGenerator
from video_processor import VideoProcessor

app = FastAPI(title="Karaoke Subtitle API", version="1.0.0")

# Load Whisper model once at startup
whisper_model = whisper.load_model("base")

PUBLIC_DIR = Path("public")
PUBLIC_DIR.mkdir(exist_ok=True)
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

class VideoRequest(BaseModel):
    video_url: HttpUrl
    font_name: str = "Arial Rounded MT Bold"
    font_size: int = 24
    font_color: str = "#FFFFFF"  # White by default
    highlight_color: str = "#FFFF00"  # Yellow by default
    subtitle_position: float = None  # Optional: 0.0 = top, 1.0 = bottom, 0.75 = 3/4 down

class VideoRequestWithASS(BaseModel):
    video_url: HttpUrl
    ass_url: HttpUrl  # URL to the .ass subtitle file from HeyGen

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
            
            await video_processor.download_video(str(video_request.video_url), input_video_path)
            
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
            
            await video_processor.download_video(str(video_request.video_url), input_video_path)
            
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

async def download_ass_file(ass_url: str, output_path: Path) -> None:
    """Download ASS subtitle file from URL"""
    response = requests.get(str(ass_url), stream=True)
    response.raise_for_status()
    
    async with aiofiles.open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            await f.write(chunk)

@app.post("/generate-with-ass-file", response_model=VideoResponse)
async def generate_with_ass_file(video_request: VideoRequestWithASS, request: Request) -> VideoResponse:
    """Generate video with subtitles using provided ASS file from HeyGen"""
    try:
        unique_id = str(uuid.uuid4())[:8]
        
        video_processor = VideoProcessor()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            input_video_path = temp_path / f"{unique_id}_input.mp4"
            subtitle_path = temp_path / f"{unique_id}_subtitles.ass"
            output_video_path = PUBLIC_DIR / f"{unique_id}_final.mp4"
            
            # Download video
            await video_processor.download_video(str(video_request.video_url), input_video_path)
            
            # Download ASS file from HeyGen
            await download_ass_file(str(video_request.ass_url), subtitle_path)
            
            # Burn subtitles (skip transcription entirely)
            video_processor.burn_subtitles(input_video_path, subtitle_path, output_video_path)
            
            # Construct full URL - force HTTPS for production
            if "onrender.com" in str(request.url.netloc):
                base_url = f"https://{request.url.netloc}"
            else:
                base_url = f"{request.url.scheme}://{request.url.netloc}"
            
            download_url = f"{base_url}/public/{unique_id}_final.mp4"
            
            response_data = {
                "status": "success",
                "download_url": download_url,
                "message": "Video processed with HeyGen ASS subtitles successfully"
            }
            
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))  # Changed default to 10000 for Render
    print(f"🚀 Starting Karaoke Subtitle API on port {port}")
    print(f"📋 Health check: http://0.0.0.0:{port}/health")
    print(f"📖 API docs: http://0.0.0.0:{port}/docs")
    print("✋ Press Ctrl+C to stop the server")
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)