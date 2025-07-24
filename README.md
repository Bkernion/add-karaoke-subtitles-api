# Karaoke Subtitle API 🎤

A FastAPI backend that generates karaoke-style subtitles for videos using OpenAI's Whisper and FFmpeg.

## Features

- 🎵 Karaoke-style subtitles with syllable-by-syllable timing
- 🎬 Advanced SubStation Alpha (.ass) subtitle format
- 🔥 Burned-in subtitles using FFmpeg
- 🌐 RESTful API with FastAPI
- 🚀 Ready for Render deployment
- 📱 Static file serving for processed videos

## API Usage

### Generate Karaoke Subtitles

**POST** `/generate-karaoke-subtitles`

```json
{
  "video_url": "https://example.com/input.mp4",
  "font_name": "Arial Rounded MT Bold",
  "font_size": 24,
  "font_color": "#FFFFFF",
  "highlight_color": "#FFFF00"
}
```

**Parameters:**
- `video_url` (required): URL of the video to process
- `font_name` (optional): Font family name (default: "Arial Rounded MT Bold")
- `font_size` (optional): Font size in points (default: 24)
- `font_color` (optional): Hex color for subtitle text (default: "#FFFFFF" - white)
- `highlight_color` (optional): Hex color for karaoke highlights (default: "#FFFF00" - yellow)

**Response:**
```json
{
  "status": "success",
  "download_url": "/public/abc123_final.mp4",
  "message": "Karaoke subtitles generated successfully"
}
```

### Health Check

**GET** `/health`

```json
{
  "status": "healthy",
  "service": "Karaoke Subtitle API"
}
```

## Local Development

### Prerequisites

- Python 3.11+
- FFmpeg installed on your system
- pip or pip3

### Installation

1. Clone the repository:
```bash
git clone <your-repo-url>
cd karaoke-subtitle-api
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the server:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

## Deployment

### Render

1. Connect your GitHub repository to Render
2. The `render.yaml` file will automatically configure the deployment
3. Your API will be available at your Render URL

### Docker

```bash
docker build -t karaoke-subtitle-api .
docker run -p 8000:8000 karaoke-subtitle-api
```

## Subtitle Features

- **Karaoke Timing**: Uses `\k` tags for syllable-by-syllable highlighting
- **Styling**: Bold white text with colored highlights during active syllables
- **Font**: Customizable font family, size, and colors
- **Background**: Semi-transparent black box for readability
- **Smart Text Wrapping**: Automatically adapts to video orientation:
  - **Vertical videos (≤1080px width)**: Short lines (3 words, 15 chars max)
  - **Horizontal videos (≥1920px width)**: Long lines (8 words, 40 chars max)  
  - **Medium videos**: Balanced lines (5 words, 25 chars max)
- **Format**: Advanced SubStation Alpha (.ass) for maximum compatibility

## API Examples

### Using curl (basic):

```bash
curl -X POST "http://localhost:8000/generate-karaoke-subtitles" \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://example.com/video.mp4"}'
```

### Using curl (with custom font and colors):

```bash
curl -X POST "http://localhost:8000/generate-karaoke-subtitles" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "font_name": "Impact",
    "font_size": 32,
    "font_color": "#FF0000",
    "highlight_color": "#00FF00"
  }'
```

### Using Python requests:

```python
import requests

response = requests.post(
    "http://localhost:8000/generate-karaoke-subtitles",
    json={
        "video_url": "https://example.com/video.mp4",
        "font_name": "Helvetica",
        "font_color": "#FFFFFF",
        "highlight_color": "#FF6B35"
    }
)

result = response.json()
print(f"Download URL: {result['download_url']}")
```

## Processing Flow

1. 📥 Download video from provided URL
2. 🎵 Extract audio using FFmpeg
3. 🗣️ Transcribe with Whisper (word-level timing)
4. ✂️ Split words into syllables
5. 📝 Generate .ass file with karaoke timing
6. 🔥 Burn subtitles into video
7. 📤 Return download URL

## Error Handling

The API includes comprehensive error handling for:
- Invalid video URLs
- Unsupported video formats
- Transcription failures
- FFmpeg processing errors
- File system issues

## Performance Notes

- Uses Whisper "base" model by default (good balance of speed/accuracy)
- Processes videos in temporary directories (auto-cleanup)
- Generates unique IDs for concurrent requests
- Optimized FFmpeg settings for quality and speed

## Troubleshooting

### Common Issues

1. **FFmpeg not found**: Install FFmpeg on your system
2. **Memory issues**: Use smaller Whisper model or increase system resources
3. **Long processing times**: Consider using "tiny" or "small" Whisper models
4. **Video format errors**: Ensure input videos are in common formats (MP4, AVI, MOV)

## License

MIT License - feel free to use and modify as needed!