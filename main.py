import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any

import aiofiles
import requests
import whisper
import ffmpeg
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, HttpUrl
from slugify import slugify

from subtitle_generator import KaraokeSubtitleGenerator
from video_processor import VideoProcessor

app = FastAPI(title="Karaoke Subtitle API", version="1.0.0")

PUBLIC_DIR = Path("public")
PUBLIC_DIR.mkdir(exist_ok=True)
app.mount("/public", StaticFiles(directory=PUBLIC_DIR), name="public")

class VideoRequest(BaseModel):
    video_url: HttpUrl
    font_name: str = "Arial Rounded MT Bold"
    font_color: str = "#FFFFFF"  # White by default
    highlight_color: str = "#FFFF00"  # Yellow by default

class VideoResponse(BaseModel):
    status: str
    download_url: str
    message: str = ""

@app.post("/generate-karaoke-subtitles", response_model=VideoResponse)
async def generate_karaoke_subtitles(request: VideoRequest) -> VideoResponse:
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
            
            await video_processor.download_video(str(request.video_url), input_video_path)
            
            video_processor.extract_audio(input_video_path, audio_path)
            
            transcription = subtitle_generator.transcribe_with_timing(audio_path)
            
            subtitle_generator.generate_ass_file(
                transcription, 
                subtitle_path,
                font_name=request.font_name,
                font_color=request.font_color,
                highlight_color=request.highlight_color
            )
            
            video_processor.burn_subtitles(input_video_path, subtitle_path, output_video_path)
            
            download_url = f"/public/{unique_id}_final.mp4"
            
            return VideoResponse(
                status="success",
                download_url=download_url,
                message="Karaoke subtitles generated successfully"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing video: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Karaoke Subtitle API"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    print(f"🚀 Starting Karaoke Subtitle API on port {port}")
    print(f"📋 Health check: http://localhost:{port}/health")
    print(f"📖 API docs: http://localhost:{port}/docs")
    print("✋ Press Ctrl+C to stop the server")
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=False)