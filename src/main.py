import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # DON'T CHANGE THIS !!!

from flask import Flask, render_template, request, jsonify
from src.routes.transcript import transcript_bp
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from youtube_transcript_api.formatters import TextFormatter
import re
import json
from urllib.parse import urlparse, parse_qs
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)
app.register_blueprint(transcript_bp)

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    if 'youtube.com' in url or 'youtu.be' in url:
        if 'youtu.be' in url:
            return url.split('/')[-1]
        parsed_url = urlparse(url)
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
        elif '/playlist' in parsed_url.path:
            return None
    return None

def extract_playlist_id(url):
    """Extract playlist ID from YouTube URL"""
    if 'youtube.com' in url:
        parsed_url = urlparse(url)
        if '/playlist' in parsed_url.path:
            return parse_qs(parsed_url.query)['list'][0]
    return None

def get_playlist_videos(playlist_id, max_videos=10):
    """Get video IDs from a playlist"""
    try:
        # Get playlist page
        url = f'https://www.youtube.com/playlist?list={playlist_id}'
        response = requests.get(url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all video links
        video_links = soup.find_all('a', {'class': 'yt-simple-endpoint'})
        video_ids = []
        
        for link in video_links:
            href = link.get('href', '')
            if '/watch?v=' in href:
                video_id = href.split('watch?v=')[1].split('&')[0]
                if video_id not in video_ids:
                    video_ids.append(video_id)
                    if len(video_ids) >= max_videos:
                        break
        
        return video_ids
    except Exception as e:
        print(f"Error getting playlist videos: {str(e)}")
        return []

def get_transcript(video_id, language='en'):
    """Get transcript for a video"""
    try:
        # Try to get transcript in specified language
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])
        return transcript, language, False
    except (TranscriptsDisabled, NoTranscriptFound):
        try:
            # If specified language is not available, try to get any available transcript
            transcript = YouTubeTranscriptApi.get_transcript(video_id)
            return transcript, transcript[0]['lang'], True
        except Exception as e:
            print(f"Error getting transcript: {str(e)}")
            return None, None, False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/extract', methods=['POST'])
def extract():
    try:
        data = request.get_json()
        url = data.get('url', '')
        language = data.get('language', 'en')
        max_videos = int(data.get('max_videos', 10))
        
        # Check if it's a playlist
        playlist_id = extract_playlist_id(url)
        if playlist_id:
            # Get videos from playlist
            video_ids = get_playlist_videos(playlist_id, max_videos)
            if not video_ids:
                return jsonify({'error': 'No videos found in playlist'}), 400
            
            # Get transcripts for all videos
            all_transcripts = []
            used_languages = set()
            success_count = 0
            fallback_count = 0
            failed_count = 0
            
            for video_id in video_ids:
                transcript, lang, is_fallback = get_transcript(video_id, language)
                if transcript:
                    all_transcripts.append(transcript)
                    used_languages.add(lang)
                    if is_fallback:
                        fallback_count += 1
                    else:
                        success_count += 1
                else:
                    failed_count += 1
            
            if not all_transcripts:
                return jsonify({'error': 'No transcripts found for any video in the playlist'}), 400
            
            # Format all transcripts
            formatter = TextFormatter()
            formatted_transcripts = []
            for i, transcript in enumerate(all_transcripts, 1):
                formatted = formatter.format_transcript(transcript)
                formatted_transcripts.append(f"Video {i}:\n{formatted}\n")
            
            return jsonify({
                'transcript': '\n'.join(formatted_transcripts),
                'title': f'Playlist Transcript ({len(all_transcripts)} videos)',
                'summary': {
                    'total': len(video_ids),
                    'success': success_count,
                    'fallback': fallback_count,
                    'failed': failed_count,
                    'languages': list(used_languages)
                }
            })
        
        # Single video
        video_id = extract_video_id(url)
        if not video_id:
            return jsonify({'error': 'Invalid YouTube URL'}), 400
        
        transcript, lang, is_fallback = get_transcript(video_id, language)
        if not transcript:
            return jsonify({'error': 'No transcript found for this video'}), 400
        
        # Format transcript
        formatter = TextFormatter()
        formatted_transcript = formatter.format_transcript(transcript)
        
        return jsonify({
            'transcript': formatted_transcript,
            'title': 'Video Transcript',
            'summary': {
                'total': 1,
                'success': 0 if is_fallback else 1,
                'fallback': 1 if is_fallback else 0,
                'failed': 0,
                'languages': [lang]
            }
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
