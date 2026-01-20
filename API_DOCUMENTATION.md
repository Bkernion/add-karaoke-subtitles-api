# Karaoke Subtitle API - Complete Documentation

## Table of Contents
- [Overview](#overview)
- [Base URL](#base-url)
- [Endpoints](#endpoints)
  - [Karaoke Subtitle Endpoints](#karaoke-subtitle-endpoints)
  - [Artistic Video Endpoints](#artistic-video-endpoints)
  - [Font Management Endpoints](#font-management-endpoints)
  - [Utility Endpoints](#utility-endpoints)
- [Request Parameters](#request-parameters)
- [Subtitle Position Guide](#subtitle-position-guide)
- [Output Format Guide](#output-format-guide)
- [Response Format](#response-format)
- [Error Handling](#error-handling)
- [Code Examples](#code-examples)

## Overview

The Karaoke Subtitle API provides two main features:

1. **Karaoke Subtitles**: Generates karaoke-style subtitles for videos using OpenAI's Whisper for transcription and FFmpeg for video processing. Creates syllable-by-syllable timing and burns subtitles directly into the video.

2. **Artistic Word Videos**: Creates scroll-stopping social media videos with dynamic typography, where each word appears on its own artistic frame with varying fonts, colors, positions, backgrounds (solid/gradient), and effects (shadows, glow, highlights).

## Base URL

- **Production**: `https://your-render-domain.onrender.com`
- **Local Development**: `http://localhost:10000`

## Endpoints

### Karaoke Subtitle Endpoints

#### 1. Generate Karaoke Subtitles (JSON Response)

**Endpoint**: `POST /generate-karaoke-subtitles`

Main endpoint that returns a JSON response with the download URL and processing status.

#### 2. Generate Karaoke Subtitles (Simple Response)

**Endpoint**: `POST /generate-karaoke-subtitles-simple`

Alternative endpoint that returns only the download URL as plain text.

### Artistic Video Endpoints

#### 3. Generate Artistic Video (URL-based)

**Endpoint**: `POST /generate-artistic-video`

Creates artistic word-by-word videos with dynamic typography using URLs to source files.

**Request Body (JSON)**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `caption_url` | string (URL) | Optional | - | URL to .ass or .srt caption file |
| `audio_url` | string (URL) | Optional* | - | URL to audio file (.mp3, .wav) |
| `video_url` | string (URL) | Optional* | - | URL to video file (audio will be extracted) |
| `output_format` | string | Optional | `"9:16"` | Output format: `9:16`, `1:1`, or `16:9` |
| `headers` | object | Optional | - | Extra request headers for fetching URLs |
| `base64_urls` | boolean | Optional | `false` | If true, URLs are base64-encoded |

*At least one of `audio_url` or `video_url` must be provided.

**Notes**:
- If no `caption_url` is provided, Whisper transcription will be used to generate word-level timing automatically.
- If `video_url` is provided instead of `audio_url`, audio will be extracted from the video.

**Response**: `ArtisticVideoResponse` (see [Response Format](#artistic-video-response))

#### 4. Generate Artistic Video (File Upload)

**Endpoint**: `POST /generate-artistic-video-upload`

Creates artistic word-by-word videos using file uploads instead of URLs.

**Request Body (multipart/form-data)**:
| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `caption_file` | file | Optional | - | .ass or .srt caption file |
| `audio_file` | file | Optional* | - | Audio file (.mp3, .wav) |
| `video_file` | file | Optional* | - | Video file (audio will be extracted) |
| `output_format` | string (form) | Optional | `"9:16"` | Output format: `9:16`, `1:1`, or `16:9` |

*At least one of `audio_file` or `video_file` must be provided.

**Notes**:
- If no `caption_file` is provided, Whisper transcription will be used to generate word-level timing automatically.
- If `video_file` is provided instead of `audio_file`, audio will be extracted from the video.

**Response**: `ArtisticVideoResponse` (see [Response Format](#artistic-video-response))

### Font Management Endpoints

#### 5. Upload Custom Font

**Endpoint**: `POST /upload-font`

Upload a custom TTF font for use in artistic video generation.

**Request Body (multipart/form-data)**:
| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `font_file` | file | Required | TTF or OTF font file to upload |

**Validations**:
- File must be a valid TTF or OTF font (magic bytes validated)
- Maximum file size: 10MB
- Filename is sanitized for security

**Response**: `FontUploadResponse`
```json
{
  "status": "success",
  "font_name": "MyCustomFont",
  "message": "Font 'MyCustomFont' uploaded successfully and is now available for use"
}
```

#### 6. List Available Fonts

**Endpoint**: `GET /fonts`

List all available fonts for artistic video generation, including bundled fonts and user-uploaded fonts.

**Response**: `FontListResponse`
```json
{
  "fonts": ["BebasNeue", "Oswald", "Anton", "MyCustomFont", ...],
  "count": 26
}
```

### Utility Endpoints

#### 7. Health Check

**Endpoint**: `GET /health`

Returns API health status.

#### 8. Root Information

**Endpoint**: `GET /`

Returns basic API information and available endpoints.

#### 9. Test Endpoint

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

## Output Format Guide

The `output_format` parameter (for artistic video endpoints) controls the dimensions and aspect ratio of the generated video.

### Supported Output Formats

| Format | Dimensions | Aspect Ratio | Best For |
|--------|------------|--------------|----------|
| `9:16` | 1080x1920 | Portrait | TikTok, Instagram Reels, YouTube Shorts |
| `1:1` | 1080x1080 | Square | Instagram Feed, Facebook |
| `16:9` | 1920x1080 | Landscape | YouTube, Traditional video |

### Format Selection Guide

| Platform | Recommended Format | Notes |
|----------|-------------------|-------|
| **TikTok** | `9:16` | Portrait is required |
| **Instagram Reels** | `9:16` | Portrait for maximum engagement |
| **Instagram Feed** | `1:1` | Square works best in feed |
| **YouTube Shorts** | `9:16` | Portrait for Shorts |
| **YouTube** | `16:9` | Traditional landscape |
| **Facebook** | `1:1` or `16:9` | Both work well |

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

### Artistic Video Response

```json
{
  "status": "success",
  "download_url": "https://your-domain.com/public/abc12345_artistic.mp4",
  "message": "Artistic video generated successfully with 42 words"
}
```

### Font Upload Response

```json
{
  "status": "success",
  "font_name": "MyCustomFont",
  "message": "Font 'MyCustomFont' uploaded successfully and is now available for use"
}
```

### Font List Response

```json
{
  "fonts": ["BebasNeue", "Oswald", "Anton", "ArchivoBold", "PassionOne", ...],
  "count": 25
}
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

### Artistic Video Examples

#### cURL - Generate Artistic Video with Caption URL

```bash
curl -X POST "https://your-api-domain.com/generate-artistic-video" \
  -H "Content-Type: application/json" \
  -d '{
    "caption_url": "https://example.com/captions.srt",
    "audio_url": "https://example.com/voiceover.mp3",
    "output_format": "9:16"
  }'
```

#### cURL - Generate Artistic Video without Captions (Whisper Transcription)

```bash
curl -X POST "https://your-api-domain.com/generate-artistic-video" \
  -H "Content-Type: application/json" \
  -d '{
    "audio_url": "https://example.com/voiceover.mp3",
    "output_format": "9:16"
  }'
```

#### cURL - Generate Artistic Video from Video URL

```bash
curl -X POST "https://your-api-domain.com/generate-artistic-video" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://example.com/video.mp4",
    "output_format": "1:1"
  }'
```

#### cURL - Generate Artistic Video with File Upload

```bash
curl -X POST "https://your-api-domain.com/generate-artistic-video-upload" \
  -F "caption_file=@captions.srt" \
  -F "audio_file=@voiceover.mp3" \
  -F "output_format=9:16"
```

#### cURL - Upload Custom Font

```bash
curl -X POST "https://your-api-domain.com/upload-font" \
  -F "font_file=@MyCustomFont.ttf"
```

#### cURL - List Available Fonts

```bash
curl "https://your-api-domain.com/fonts"
```

#### Python - Generate Artistic Video

```python
import requests

# With caption URL
response = requests.post(
    "https://your-api-domain.com/generate-artistic-video",
    json={
        "caption_url": "https://example.com/captions.srt",
        "audio_url": "https://example.com/voiceover.mp3",
        "output_format": "9:16"
    }
)

result = response.json()
print(f"Status: {result['status']}")
print(f"Download URL: {result['download_url']}")
print(f"Message: {result['message']}")
```

#### Python - Generate Artistic Video without Captions

```python
import requests

# Whisper will transcribe the audio automatically
response = requests.post(
    "https://your-api-domain.com/generate-artistic-video",
    json={
        "audio_url": "https://example.com/voiceover.mp3",
        "output_format": "9:16"
    }
)

if response.status_code == 200:
    result = response.json()
    print(f"Download: {result['download_url']}")
else:
    print(f"Error: {response.json()['detail']}")
```

#### Python - Upload File with multipart/form-data

```python
import requests

# Upload files directly
with open("captions.srt", "rb") as caption_f, open("voiceover.mp3", "rb") as audio_f:
    response = requests.post(
        "https://your-api-domain.com/generate-artistic-video-upload",
        files={
            "caption_file": ("captions.srt", caption_f, "text/plain"),
            "audio_file": ("voiceover.mp3", audio_f, "audio/mpeg"),
        },
        data={
            "output_format": "9:16"
        }
    )

result = response.json()
print(f"Download URL: {result['download_url']}")
```

#### Python - Upload Custom Font

```python
import requests

with open("MyCustomFont.ttf", "rb") as font_f:
    response = requests.post(
        "https://your-api-domain.com/upload-font",
        files={
            "font_file": ("MyCustomFont.ttf", font_f, "font/ttf"),
        }
    )

result = response.json()
print(f"Font name: {result['font_name']}")
# Use this font name in future requests
```

#### Python - List Available Fonts

```python
import requests

response = requests.get("https://your-api-domain.com/fonts")
result = response.json()

print(f"Available fonts ({result['count']}):")
for font in result['fonts']:
    print(f"  - {font}")
```

#### JavaScript/Node.js - Generate Artistic Video

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

// URL-based request
async function generateArtisticVideo(audioUrl, captionUrl = null) {
  try {
    const response = await axios.post(
      'https://your-api-domain.com/generate-artistic-video',
      {
        audio_url: audioUrl,
        caption_url: captionUrl,
        output_format: '9:16'
      },
      {
        headers: { 'Content-Type': 'application/json' }
      }
    );

    console.log('Download URL:', response.data.download_url);
    return response.data.download_url;
  } catch (error) {
    console.error('Error:', error.response?.data?.detail || error.message);
    throw error;
  }
}

// File upload request
async function uploadAndGenerateVideo(captionPath, audioPath) {
  const form = new FormData();
  form.append('caption_file', fs.createReadStream(captionPath));
  form.append('audio_file', fs.createReadStream(audioPath));
  form.append('output_format', '9:16');

  try {
    const response = await axios.post(
      'https://your-api-domain.com/generate-artistic-video-upload',
      form,
      {
        headers: form.getHeaders()
      }
    );

    console.log('Download URL:', response.data.download_url);
    return response.data.download_url;
  } catch (error) {
    console.error('Error:', error.response?.data?.detail || error.message);
    throw error;
  }
}
```

## Processing Pipeline

### Karaoke Subtitle Pipeline

1. **Video Download** - Downloads video from provided URL
2. **Audio Extraction** - Extracts audio using FFmpeg
3. **Transcription** - Uses Whisper for word-level timing
4. **Syllable Processing** - Splits words into syllables for karaoke timing
5. **ASS Generation** - Creates Advanced SubStation Alpha subtitle file
6. **Video Processing** - Burns subtitles into video using FFmpeg
7. **File Serving** - Returns download URL for processed video

### Artistic Video Pipeline

1. **File Acquisition** - Downloads files from URLs or receives file uploads
2. **Audio Handling** - Uses provided audio or extracts from video using FFmpeg
3. **Word Timing** - Parses caption file (.ass/.srt) or transcribes with Whisper
4. **Style Generation** - Generates random but cohesive styles for each word (fonts, colors, positions, effects)
5. **Frame Generation** - Creates individual image frames using Pillow with:
   - Solid or gradient backgrounds
   - Custom fonts from bundled or uploaded fonts
   - Text positioning (center, top-third, bottom-third, left-offset, right-offset)
   - Text rotation (-15 to +15 degrees)
   - Highlight boxes/parallelograms behind text
   - Drop shadows and glow effects
6. **Video Assembly** - Combines frames into video synced with audio using FFmpeg
7. **File Serving** - Returns download URL for generated video

## Technical Specifications

### Karaoke Subtitle Output
- **Video Output**: H.264 encoded MP4
- **Audio**: AAC, 320k bitrate
- **Quality**: CRF=18 (near-lossless)
- **Subtitle Format**: Advanced SubStation Alpha (.ass)
- **Transcription**: OpenAI Whisper "base" model
- **Processing**: Temporary file cleanup
- **Concurrent Requests**: Supported with unique IDs

### Artistic Video Output
- **Video Output**: H.264 encoded MP4, optimized for web (faststart, yuv420p)
- **Audio**: AAC encoded
- **Frame Dimensions**:
  - Portrait (9:16): 1080x1920
  - Square (1:1): 1080x1080
  - Landscape (16:9): 1920x1080
- **Frame Generation**: Pillow (PIL) with RGBA support
- **Font Size Range**: 80-200px (auto-scaled for longer words)
- **Supported Caption Formats**: .ass, .srt
- **Transcription**: OpenAI Whisper "base" model (when no captions provided)

### Font Upload Specifications
- **Supported Formats**: TTF, OTF
- **Maximum File Size**: 10MB
- **Validation**: Magic bytes verification for security
- **Filename Sanitization**: Path traversal prevention, special character removal

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

### Karaoke Subtitle Fonts

#### Production-Ready Fonts (Linux/Docker/Render)
- `Liberation Sans` / `Liberation Sans Bold`
- `DejaVu Sans` / `DejaVu Sans Bold`
- `Noto Sans`
- `FreeSans`

#### Local Development Fonts (macOS/Windows)
- `Arial Rounded MT Bold` (default)
- `Helvetica`
- `Arial`
- `Times New Roman`
- System fonts

### Artistic Video Fonts

The artistic video endpoints use bundled Google Fonts for consistent visual impact across environments. Use the `/fonts` endpoint to list all available fonts.

#### Bundled Fonts (25 fonts)
- **Bold/Impact**: Bebas Neue, Oswald, Anton, Archivo Black, Passion One, Russo One, Titan One, Black Ops One
- **Display**: Bangers, Righteous, Fredoka One, Luckiest Guy, Boogaloo, Lobster, Rubik Bold
- **Handwritten**: Permanent Marker, Pacifico, Caveat, Kaushan Script, Rock Salt, Shadows Into Light
- **Modern**: Montserrat Bold, Poppins Bold, Quicksand Bold, Raleway Black

#### Custom Font Upload
Upload your own TTF/OTF fonts via the `/upload-font` endpoint. Uploaded fonts are immediately available for use and will appear in the `/fonts` list.

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