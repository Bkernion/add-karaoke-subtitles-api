# Karaoke Subtitle API - Complete Documentation 📚

## Table of Contents
- [Overview](#overview)
- [Base URL](#base-url)
- [Endpoints](#endpoints)
- [Request Parameters](#request-parameters)
- [Subtitle Position Guide](#subtitle-position-guide)
- [Response Format](#response-format)
- [Error Handling](#error-handling)
- [Code Examples](#code-examples)

## Overview

The Karaoke Subtitle API generates karaoke-style subtitles for videos using OpenAI's Whisper for transcription and FFmpeg for video processing. The API creates syllable-by-syllable timing and burns subtitles directly into the video.

## Base URL

- **Production**: `https://your-render-domain.onrender.com`
- **Local Development**: `http://localhost:10000`

## Endpoints

### 1. Generate Karaoke Subtitles (JSON Response)

**Endpoint**: `POST /generate-karaoke-subtitles`

Main endpoint that returns a JSON response with the download URL and processing status.

### 2. Generate Karaoke Subtitles (Simple Response)

**Endpoint**: `POST /generate-karaoke-subtitles-simple`

Alternative endpoint that returns only the download URL as plain text.

### 3. Health Check

**Endpoint**: `GET /health`

Returns API health status.

### 4. Root Information

**Endpoint**: `GET /`

Returns basic API information and available endpoints.

### 5. Test Endpoint

**Endpoint**: `GET /test`

Simple test endpoint to verify API connectivity.

## Request Parameters

### VideoRequest Model

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `video_url` | string (URL) | ✅ Required | - | URL of the video to process |
| `font_name` | string | ❌ Optional | `"Arial Rounded MT Bold"` | Font family name for subtitles |
| `font_size` | integer | ❌ Optional | `24` | Font size in points |
| `font_color` | string | ❌ Optional | `"#FFFFFF"` | Hex color for subtitle text (white) |
| `highlight_color` | string | ❌ Optional | `"#FFFF00"` | Hex color for karaoke highlights (yellow) |
| `subtitle_position` | float | ❌ Optional | `null` | Vertical position of subtitles (see guide below) |

## Subtitle Position Guide

The `subtitle_position` parameter controls where subtitles appear vertically on the video. When `null`, subtitles use default bottom positioning.

### Position Value Table

| `subtitle_position` Value | Visual Position | Margin from Bottom | Description |
|---------------------------|-----------------|-------------------|-------------|
| `null` (default) | Bottom | 10px | Standard bottom positioning |
| `0.0` | Very High | ~110px | Near the top of the video |
| `0.2` | High | ~90px | Upper portion |
| `0.4` | Medium-High | ~70px | Above center |
| `0.5` | Center | ~60px | Middle of video |
| `0.6` | Medium-Low | ~50px | Below center |
| `0.75` | 3/4 Down | ~35px | **Recommended for most videos** |
| `0.8` | Low | ~30px | Lower portion |
| `1.0` | Bottom | ~10px | Same as default |

### Position Calculation

The positioning uses this formula:
```
margin_from_bottom = 10 + ((1.0 - (subtitle_position / 2)) * 100)
```

**Examples:**
- `subtitle_position: 0.75` → `35px` from bottom (3/4 down the screen)
- `subtitle_position: 0.5` → `60px` from bottom (center)
- `subtitle_position: 0.0` → `110px` from bottom (very high)

### Recommended Values

| Video Type | Recommended Position | Reasoning |
|------------|---------------------|-----------|
| **Vertical Videos** (TikTok, Instagram) | `0.75` | Places text in lower third, avoids UI elements |
| **Horizontal Videos** (YouTube) | `0.8` or `null` | Traditional bottom placement |
| **Square Videos** | `0.75` | Balanced positioning |
| **Music Videos** | `0.6` - `0.8` | Avoids lyrics or artist info |

## Response Format

### Successful Response (JSON Endpoint)

```json
{
  "status": "success",
  "download_url": "https://your-domain.com/public/abc12345_final.mp4",
  "message": "Karaoke subtitles generated successfully"
}
```

### Successful Response (Simple Endpoint)

```
https://your-domain.com/public/abc12345_final.mp4
```

### Error Response

```json
{
  "detail": "Error processing video: [specific error message]"
}
```

**HTTP Status Codes:**
- `200` - Success
- `422` - Validation Error (invalid parameters)
- `500` - Internal Server Error (processing failed)

## Error Handling

Common error scenarios:

### Invalid Video URL
```json
{
  "detail": "Error processing video: Unable to download video from URL"
}
```

### Unsupported Video Format
```json
{
  "detail": "Error processing video: Unsupported video format"
}
```

### Processing Timeout
```json
{
  "detail": "Error processing video: Processing timeout exceeded"
}
```

## Code Examples

### cURL Examples

#### Basic Request
```bash
curl -X POST "https://your-api-domain.com/generate-karaoke-subtitles" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4"
  }'
```

#### With Custom Positioning
```bash
curl -X POST "https://your-api-domain.com/generate-karaoke-subtitles" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "subtitle_position": 0.75,
    "font_size": 28,
    "highlight_color": "#FF6B35"
  }'
```

#### Simple Endpoint (Plain Text Response)
```bash
curl -X POST "https://your-api-domain.com/generate-karaoke-subtitles-simple" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "subtitle_position": 0.75
  }'
```

### Python Examples

#### Using requests library
```python
import requests

# Basic request
response = requests.post(
    "https://your-api-domain.com/generate-karaoke-subtitles",
    json={
        "video_url": "https://example.com/video.mp4"
    }
)

result = response.json()
print(f"Status: {result['status']}")
print(f"Download URL: {result['download_url']}")
```

#### With custom positioning and styling
```python
import requests

response = requests.post(
    "https://your-api-domain.com/generate-karaoke-subtitles",
    json={
        "video_url": "https://example.com/video.mp4",
        "subtitle_position": 0.75,  # 3/4 down the screen
        "font_name": "Liberation Sans Bold",
        "font_size": 32,
        "font_color": "#FFFFFF",
        "highlight_color": "#FF6B35"
    }
)

if response.status_code == 200:
    result = response.json()
    print(f"✅ Success! Download: {result['download_url']}")
else:
    print(f"❌ Error: {response.json()['detail']}")
```

#### Simple endpoint usage
```python
import requests

response = requests.post(
    "https://your-api-domain.com/generate-karaoke-subtitles-simple",
    json={
        "video_url": "https://example.com/video.mp4",
        "subtitle_position": 0.75
    }
)

if response.status_code == 200:
    download_url = response.text
    print(f"Download URL: {download_url}")
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

async function generateKaraokeSubtitles(videoUrl, subtitlePosition = 0.75) {
  try {
    const response = await axios.post(
      'https://your-api-domain.com/generate-karaoke-subtitles',
      {
        video_url: videoUrl,
        subtitle_position: subtitlePosition,
        font_size: 28,
        highlight_color: '#FF6B35'
      },
      {
        headers: {
          'Content-Type': 'application/json'
        }
      }
    );

    console.log('✅ Success:', response.data.download_url);
    return response.data.download_url;
    
  } catch (error) {
    console.error('❌ Error:', error.response?.data?.detail || error.message);
    throw error;
  }
}

// Usage
generateKaraokeSubtitles('https://example.com/video.mp4', 0.75);
```

## Processing Pipeline

1. **Video Download** - Downloads video from provided URL
2. **Audio Extraction** - Extracts audio using FFmpeg
3. **Transcription** - Uses Whisper for word-level timing
4. **Syllable Processing** - Splits words into syllables for karaoke timing
5. **ASS Generation** - Creates Advanced SubStation Alpha subtitle file
6. **Video Processing** - Burns subtitles into video using FFmpeg
7. **File Serving** - Returns download URL for processed video

## Technical Specifications

- **Video Output**: H.264 encoded MP4
- **Audio**: AAC, 320k bitrate
- **Quality**: CRF=18 (near-lossless)
- **Subtitle Format**: Advanced SubStation Alpha (.ass)
- **Transcription**: OpenAI Whisper "tiny" model
- **Processing**: Temporary file cleanup
- **Concurrent Requests**: Supported with unique IDs

## Rate Limits & Performance

- **Processing Time**: Varies by video length (typically 2-5x real-time)
- **File Size Limits**: No explicit limit, but processing time increases with size
- **Concurrent Requests**: Multiple requests supported
- **File Cleanup**: Automatic cleanup of temporary files

## Supported Video Formats

**Input Formats**:
- MP4 (recommended)
- AVI
- MOV
- WebM
- MKV

**Output Format**:
- MP4 (H.264 + AAC)

## Font Support

### Production-Ready Fonts (Linux/Docker/Render)
- `Liberation Sans` / `Liberation Sans Bold`
- `DejaVu Sans` / `DejaVu Sans Bold`
- `Noto Sans`
- `FreeSans`

### Local Development Fonts (macOS/Windows)
- `Arial Rounded MT Bold` (default)
- `Helvetica`
- `Arial`
- `Times New Roman`
- System fonts

## Best Practices

1. **Use HTTPS URLs** for video input
2. **Test positioning** with `subtitle_position: 0.75` for most videos
3. **Choose readable fonts** from the production-ready list
4. **Consider video orientation** when setting position
5. **Use appropriate font sizes** (24-32 for most cases)
6. **High contrast colors** for better readability

## Health Check

Check API status:
```bash
curl https://your-api-domain.com/health
```

Response:
```json
{
  "status": "healthy",
  "service": "Karaoke Subtitle API"
}
```

---

*Generated with ❤️ by the Karaoke Subtitle API*