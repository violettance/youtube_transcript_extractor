from flask import Blueprint, render_template, request, jsonify, send_file
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
from youtube_transcript_api.formatters import TextFormatter
from pytube import Playlist
import re
import os
from datetime import datetime
import requests

transcript_bp = Blueprint('transcript', __name__)

def ensure_transcripts_dir():
    """
    Altyazıların kaydedileceği dizini oluşturur
    """
    transcripts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'transcripts')
    if not os.path.exists(transcripts_dir):
        os.makedirs(transcripts_dir)
    return transcripts_dir

def get_video_ids_from_playlist(playlist_url):
    """
    Playlist URL'inden video ID'lerini çıkarır
    """
    try:
        # Playlist ID'sini URL'den çıkar
        if 'list=' in playlist_url:
            playlist_id = playlist_url.split('list=')[1].split('&')[0]
        else:
            raise ValueError("Geçerli bir playlist URL'si değil")

        # YouTube Data API endpoint'i
        api_url = f"https://www.youtube.com/playlist?list={playlist_id}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        video_ids = []
        page = 1
        max_pages = 10  # Maksimum sayfa sayısı (her sayfada yaklaşık 20 video)
        
        while page <= max_pages:
            try:
                response = requests.get(api_url, headers=headers)
                if response.status_code != 200:
                    break
                
                # Video ID'lerini bul
                new_ids = re.findall(r"watch\?v=(\S{11})", response.text)
                if not new_ids:
                    break
                
                # Yeni ID'leri ekle ve tekrarları kaldır
                video_ids.extend(new_ids)
                video_ids = list(dict.fromkeys(video_ids))
                
                # Playlist başlığını bul
                title_match = re.search(r'<title>(.*?)</title>', response.text)
                playlist_title = title_match.group(1).replace(' - YouTube', '') if title_match else f"Playlist_{playlist_id}"
                
                # Sonraki sayfa için URL'yi güncelle
                page += 1
                api_url = f"https://www.youtube.com/playlist?list={playlist_id}&page={page}"
                
            except Exception as e:
                print(f"Sayfa {page} işlenirken hata: {str(e)}")
                break
        
        if not video_ids:
            raise ValueError("Playlist'ten video ID'leri çekilemedi")
        
        return video_ids, playlist_title
        
    except Exception as e:
        print(f"Playlist işlenirken hata oluştu: {str(e)}")
        return [], ""

def get_video_info(video_url):
    """
    Video URL'sinden video ID'sini ve başlığını çıkarır
    """
    try:
        if 'watch?v=' in video_url:
            video_id = video_url.split('watch?v=')[1].split('&')[0]
        else:
            raise ValueError("Geçerli bir video URL'si değil")

        # Video sayfasını çek
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(video_url, headers=headers)
        
        # Video başlığını bul
        title_match = re.search(r'<title>(.*?)</title>', response.text)
        video_title = title_match.group(1).replace(' - YouTube', '') if title_match else f"Video_{video_id}"
        
        return video_id, video_title
    except Exception as e:
        print(f"Video bilgisi alınırken hata oluştu: {str(e)}")
        return None, None

def get_transcript_with_fallback(video_id, primary_language='tr', fallback_languages=None):
    """
    Video ID'si verilen bir YouTube videosunun altyazısını çeker
    İstenen dilde altyazı bulunamazsa, fallback dilleri dener
    """
    if fallback_languages is None:
        fallback_languages = ['en', 'auto']
    
    # Tüm dilleri bir listeye ekle, önce birincil dil
    languages_to_try = [primary_language] + [lang for lang in fallback_languages if lang != primary_language]
    
    transcript_text = None
    used_language = None
    error_message = None
    
    for language in languages_to_try:
        try:
            if language == 'auto':
                # Otomatik olarak mevcut herhangi bir dili al
                transcript = YouTubeTranscriptApi.list_transcripts(video_id)
                # Mevcut ilk transkripti al
                first_transcript = transcript.find_transcript(['tr', 'en', 'de', 'fr', 'es'])
                transcript_data = first_transcript.fetch()
                used_language = first_transcript.language_code
            else:
                transcript_data = YouTubeTranscriptApi.get_transcript(video_id, languages=[language])
                used_language = language
            
            formatter = TextFormatter()
            transcript_text = formatter.format_transcript(transcript_data)
            break
        
        except NoTranscriptFound:
            if language == primary_language:
                error_message = f"Bu video için {language} altyazısı bulunamadı. Diğer diller deneniyor..."
            continue
        except TranscriptsDisabled:
            error_message = "Bu video için altyazılar devre dışı bırakılmış."
            break
        except VideoUnavailable:
            error_message = "Bu video kullanılamıyor veya özel olabilir."
            break
        except Exception as e:
            error_message = f"Altyazı çekilirken hata oluştu: {str(e)}"
            continue
    
    if transcript_text:
        language_info = ""
        if used_language != primary_language:
            language_map = {
                'en': 'İngilizce',
                'tr': 'Türkçe',
                'de': 'Almanca',
                'fr': 'Fransızca',
                'es': 'İspanyolca'
            }
            language_name = language_map.get(used_language, used_language)
            language_info = f"(Not: {primary_language} altyazı bulunamadı, {language_name} altyazı kullanıldı)"
        
        return transcript_text, used_language, language_info
    else:
        return None, None, error_message

@transcript_bp.route('/extract', methods=['POST'])
def extract_transcript():
    """
    Video veya playlist URL'sinden altyazıları çıkarır ve txt dosyalarına kaydeder
    """
    data = request.get_json()
    url = data.get('url')  # URL parametresi (video veya playlist)
    primary_language = data.get('language', 'tr')
    max_videos = data.get('max_videos', 50)
    
    if not url:
        return jsonify({'error': 'URL gereklidir'}), 400
    
    # URL'nin video mu playlist mi olduğunu kontrol et
    is_playlist = 'list=' in url
    
    if is_playlist:
        video_ids, title = get_video_ids_from_playlist(url)
        if not video_ids:
            return jsonify({'error': 'Playlist işlenemedi veya boş'}), 400
        
        # Maksimum video sayısını kontrol et
        if len(video_ids) > max_videos:
            video_ids = video_ids[:max_videos]
    else:
        video_id, title = get_video_info(url)
        if not video_id:
            return jsonify({'error': 'Video işlenemedi'}), 400
        video_ids = [video_id]
    
    # Altyazılar için klasör oluştur
    transcripts_dir = ensure_transcripts_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    save_dir = os.path.join(transcripts_dir, f"{title}_{timestamp}")
    os.makedirs(save_dir, exist_ok=True)
    
    all_transcripts = []
    video_count = len(video_ids)
    success_count = 0
    fallback_count = 0
    failed_count = 0
    used_languages = set()
    saved_files = []
    
    for i, video_id in enumerate(video_ids):
        video_number = i + 1
        try:
            transcript, used_language, message = get_transcript_with_fallback(
                video_id, 
                primary_language=primary_language,
                fallback_languages=['en', 'de', 'fr', 'es', 'auto']
            )
            
            if transcript:
                success_count += 1
                if used_language != primary_language:
                    fallback_count += 1
                used_languages.add(used_language)
                
                # Altyazıyı txt dosyasına kaydet
                filename = f"video_{video_number}_{video_id}.txt"
                filepath = os.path.join(save_dir, filename)
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(f"--- Video {video_number}/{video_count} ---\n\n")
                    f.write(transcript)
                    if message:
                        f.write(f"\n{message}")
                saved_files.append(filename)
                
                all_transcripts.append(f"--- Video {video_number}/{video_count} ---\n\n{transcript}\n{message if message else ''}\n\n")
            else:
                failed_count += 1
                all_transcripts.append(f"--- Video {video_number}/{video_count} ---\n\nBu video için {primary_language} altyazısı bulunamadı.\n{message if message else ''}\n\n")
        except Exception as e:
            failed_count += 1
            all_transcripts.append(f"--- Video {video_number}/{video_count} ---\n\nAltyazı çekilemedi: {str(e)}\n\n")
    
    # Tüm altyazıları birleştirip tek bir dosyaya kaydet
    full_transcript = "\n".join(all_transcripts)
    full_transcript_path = os.path.join(save_dir, "tum_altyazilar.txt")
    with open(full_transcript_path, 'w', encoding='utf-8') as f:
        f.write(full_transcript)
    saved_files.append("tum_altyazilar.txt")
    
    # Özet bilgisi
    summary = {
        'total': video_count,
        'success': success_count,
        'fallback': fallback_count,
        'failed': failed_count,
        'languages': list(used_languages),
        'saved_files': saved_files,
        'save_directory': save_dir
    }
    
    return jsonify({
        'title': title,
        'transcript': full_transcript,
        'video_count': video_count,
        'summary': summary
    })
