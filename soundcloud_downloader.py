import os
import asyncio
import yt_dlp
import logging
from typing import Optional, Dict, List
from config import YTDL_OPTIONS, DOWNLOADS_DIR, TEMP_DIR, MAX_DOWNLOAD_SIZE_MB

logger = logging.getLogger(__name__)

class SoundCloudDownloader:
    def __init__(self):
        self.ytdl_opts = YTDL_OPTIONS.copy()
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Создает необходимые директории"""
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        os.makedirs(TEMP_DIR, exist_ok=True)
    
    async def search_tracks(self, query: str, limit: int = 5) -> List[Dict]:
        """Поиск треков на SoundCloud"""
        try:
            # Пробуем несколько вариантов поиска
            search_queries = [
                f"scsearch{limit}:{query}",  # Прямой поиск по SoundCloud
                f"ytsearch{limit}:{query} soundcloud",  # Поиск через YouTube с упоминанием SoundCloud
                f"ytsearch{limit}:{query}"  # Общий поиск
            ]
            
            tracks = []
            
            for search_url in search_queries:
                try:
                    logger.info(f"Поиск с запросом: {search_url}")
                    
                    with yt_dlp.YoutubeDL({'quiet': True, 'no_warnings': True}) as ydl:
                        search_results = await asyncio.get_event_loop().run_in_executor(
                            None, ydl.extract_info, search_url, False
                        )
                    
                    if search_results and 'entries' in search_results:
                        for entry in search_results['entries']:
                            if entry and len(tracks) < limit:
                                # Принимаем треки с SoundCloud или других источников
                                webpage_url = entry.get('webpage_url', '')
                                if webpage_url:
                                    track_info = {
                                        'title': entry.get('title', 'Unknown'),
                                        'uploader': entry.get('uploader', 'Unknown'),
                                        'duration': entry.get('duration', 0),
                                        'url': webpage_url,
                                        'id': entry.get('id', ''),
                                        'thumbnail': entry.get('thumbnail', ''),
                                        'source': 'SoundCloud' if 'soundcloud.com' in webpage_url else 'Other'
                                    }
                                    tracks.append(track_info)
                    
                    # Если нашли достаточно треков, прекращаем поиск
                    if len(tracks) >= limit:
                        break
                        
                except Exception as search_error:
                    logger.warning(f"Ошибка поиска с запросом {search_url}: {search_error}")
                    continue
            
            logger.info(f"Найдено треков: {len(tracks)}")
            return tracks[:limit]
            
        except Exception as e:
            logger.error(f"Общая ошибка поиска: {e}")
            return []
    
    async def get_track_info(self, url: str) -> Optional[Dict]:
        """Получение информации о треке"""
        try:
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(
                    None, ydl.extract_info, url, False
                )
            
            if info:
                return {
                    'title': info.get('title', 'Unknown'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'url': info.get('webpage_url', url),
                    'filesize': info.get('filesize', 0),
                    'thumbnail': info.get('thumbnail', '')
                }
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения информации: {e}")
            return None
    
    async def download_track(self, url: str, user_id: int) -> Optional[str]:
        """Скачивание трека"""
        try:
            # Создаем уникальную папку для пользователя
            user_dir = os.path.join(DOWNLOADS_DIR, str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # Настройки для скачивания
            opts = self.ytdl_opts.copy()
            opts['outtmpl'] = os.path.join(user_dir, '%(title)s.%(ext)s')
            
            # Проверяем размер файла перед скачиванием
            info = await self.get_track_info(url)
            if info and info.get('filesize', 0) > MAX_DOWNLOAD_SIZE_MB * 1024 * 1024:
                raise Exception(f"Файл слишком большой (>{MAX_DOWNLOAD_SIZE_MB}MB)")
            
            with yt_dlp.YoutubeDL(opts) as ydl:
                # Скачиваем файл
                await asyncio.get_event_loop().run_in_executor(
                    None, ydl.download, [url]
                )
                
                # Ищем скачанный файл
                for file in os.listdir(user_dir):
                    if file.endswith(('.mp3', '.wav', '.m4a', '.flac')):
                        file_path = os.path.join(user_dir, file)
                        
                        # Проверяем размер скачанного файла
                        if os.path.getsize(file_path) > MAX_DOWNLOAD_SIZE_MB * 1024 * 1024:
                            os.remove(file_path)
                            raise Exception(f"Скачанный файл слишком большой (>{MAX_DOWNLOAD_SIZE_MB}MB)")
                        
                        return file_path
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка скачивания: {e}")
            # Очищаем папку пользователя при ошибке
            user_dir = os.path.join(DOWNLOADS_DIR, str(user_id))
            if os.path.exists(user_dir):
                for file in os.listdir(user_dir):
                    try:
                        os.remove(os.path.join(user_dir, file))
                    except:
                        pass
            raise e
    
    def cleanup_user_files(self, user_id: int):
        """Очистка файлов пользователя"""
        user_dir = os.path.join(DOWNLOADS_DIR, str(user_id))
        if os.path.exists(user_dir):
            for file in os.listdir(user_dir):
                try:
                    os.remove(os.path.join(user_dir, file))
                except Exception as e:
                    logger.error(f"Ошибка удаления файла {file}: {e}")
    
    def format_duration(self, seconds) -> str:
        """Форматирование длительности трека"""
        if not seconds or seconds == 0:
            return "Unknown"
        
        # Преобразуем в int если это float
        try:
            seconds = int(float(seconds))
        except (ValueError, TypeError):
            return "Unknown"
        
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}:{seconds:02d}"
