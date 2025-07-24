#!/usr/bin/env python3

import requests
import json
import time
import sys

def test_health_endpoint():
    """Test the health check endpoint"""
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code == 200:
            print("✅ Health check passed!")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to server: {e}")
        return False

def test_karaoke_endpoint():
    """Test the karaoke subtitle generation endpoint with a sample video"""
    print("\n🎤 Testing karaoke subtitle generation...")
    
    # Use a short test video URL - you can replace this with your own
    test_video_url = "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"
    
    payload = {
        "video_url": test_video_url
    }
    
    try:
        print(f"Sending request to process video: {test_video_url}")
        print("⏳ This may take a few minutes...")
        
        response = requests.post(
            "http://localhost:8000/generate-karaoke-subtitles",
            json=payload,
            timeout=300  # 5 minutes timeout
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Karaoke subtitle generation successful!")
            print(f"Status: {result['status']}")
            print(f"Download URL: {result['download_url']}")
            print(f"Message: {result['message']}")
            return True
        else:
            print(f"❌ Request failed with status {response.status_code}")
            print(f"Error: {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print("❌ Request timed out - video processing may take longer than expected")
        return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False

def main():
    print("🚀 Testing Karaoke Subtitle API locally...")
    print("=" * 50)
    
    # Test health endpoint first
    if not test_health_endpoint():
        print("\n💡 Make sure the server is running with: python main.py")
        sys.exit(1)
    
    # Ask user if they want to test with a video
    print("\n" + "=" * 50)
    user_input = input("Do you want to test video processing? (y/n): ").lower().strip()
    
    if user_input in ['y', 'yes']:
        custom_url = input("\nEnter a video URL (or press Enter for default test video): ").strip()
        if custom_url:
            # Update the test with custom URL
            global test_video_url
            test_video_url = custom_url
        
        success = test_karaoke_endpoint()
        if success:
            print("\n🎉 All tests passed! Your API is working correctly.")
        else:
            print("\n⚠️  Video processing test failed - but the server is running.")
    else:
        print("\n✅ Server is running and ready for requests!")
        print("\nTo test manually, use:")
        print('curl -X POST "http://localhost:8000/generate-karaoke-subtitles" \\')
        print('  -H "Content-Type: application/json" \\')
        print('  -d \'{"video_url": "https://your-video-url.mp4"}\'')

if __name__ == "__main__":
    main()