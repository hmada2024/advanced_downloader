# -- ملف يحتوي على الكلاسات المسؤولة عن التفاعل المباشر مع yt-dlp --
# Purpose: Contains classes that perform the actual work of interacting with yt-dlp.

import os
import yt_dlp
import sys
from pathlib import Path
from exceptions import DownloadCancelled # استيراد الاستثناء المخصص
import re # استيراد للتعابير النمطية

# --- دالة مساعدة للبحث عن FFmpeg ---
def find_ffmpeg():
    """
    يحاول العثور على ملف ffmpeg.exe التنفيذي المرفق مع التطبيق.
    """
    try:
        base_path = Path(sys.argv[0]).parent
    except Exception:
        base_path = Path(".")

    bundled_path = base_path / "ffmpeg_bin" / "ffmpeg.exe"
    if bundled_path.is_file():
        print(f"Found bundled ffmpeg: {bundled_path}")
        return str(bundled_path)
    print("Warning: Bundled ffmpeg not found. yt-dlp might rely on system PATH or fail some operations.")
    return None

# --- كلاس لجلب المعلومات ---
class InfoFetcher:
    """كلاس مسؤول عن عملية جلب معلومات الفيديو/القائمة."""
    def __init__(self, url, cancel_event, success_callback, error_callback, status_callback, progress_callback, finished_callback):
        self.url = url
        self.cancel_event = cancel_event
        self.success_callback = success_callback
        self.error_callback = error_callback
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

    def _fetch_info_core(self):
        """المنطق الأساسي لجلب المعلومات."""
        self.status_callback("Fetching information...")
        self.progress_callback(0)
        ydl_opts = {
            'quiet': True, 'nocheckcertificate': True, 'extract_flat': 'in_playlist',
            'playlistend': 500, 'ignoreerrors': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if self.cancel_event.is_set(): raise DownloadCancelled("Info fetch cancelled before starting.")
            info_dict = ydl.extract_info(self.url, download=False)
        if self.cancel_event.is_set(): raise DownloadCancelled("Info fetch cancelled after fetching.")
        self.status_callback("Information fetched successfully.")
        self.success_callback(info_dict)

    def run(self):
        """تنفذ عملية جلب المعلومات."""
        try:
            self._fetch_info_core()
        except DownloadCancelled as e:
             self.status_callback(str(e)); print(e)
        except yt_dlp.utils.DownloadError as e:
             error_message = str(e).split('ERROR:')[-1].strip()
             self.status_callback(f"Info Error: {error_message}")
             self.error_callback(error_message); print(f"yt-dlp DownloadError info fetch: {e}")
        except Exception as e:
             self.status_callback(f"Unexpected info fetch error: {type(e).__name__}")
             self.error_callback(f"Unexpected error: {e}"); print(f"Unexpected Error info fetch: {e}")
        finally:
            self.finished_callback()


# --- كلاس لتنفيذ التحميل ---
class Downloader:
    """كلاس مسؤول عن عملية التحميل الفعلية باستخدام yt-dlp."""
    def __init__(self, url, save_path, format_choice, quality_format_id,
                 is_playlist, playlist_items, playlist_items_count, ffmpeg_path,
                 cancel_event, status_callback, progress_callback, finished_callback):
        self.url = url
        self.save_path = save_path
        self.format_choice = format_choice
        self.quality_format_id = quality_format_id
        self.is_playlist = is_playlist
        self.playlist_items = playlist_items
        self.playlist_items_count = playlist_items_count
        self.current_playlist_item_dl_index = 0
        self.last_hook_filename = None
        self.last_final_filepath = None
        self.ffmpeg_path = ffmpeg_path
        self.cancel_event = cancel_event
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

    def _process_download_progress(self, d):
        """تحلل بيانات الهوك وتحدث الواجهة."""
        total_bytes_str = d.get('_total_bytes_str', 'N/A')
        downloaded_bytes = d.get('downloaded_bytes')
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
        speed_str = d.get('_speed_str', 'N/A')
        eta_str = d.get('_eta_str', 'N/A')
        percent_str = d.get('_percent_str', 'N/A').strip()
        filename = d.get('filename', 'N/A')
        item_title = d.get('info_dict', {}).get('title', os.path.basename(filename))
        item_title_cleaned = re.sub(r'\.[a-zA-Z0-9]+$', '', item_title)

        if total_bytes and downloaded_bytes:
            progress = downloaded_bytes / total_bytes
            self.progress_callback(progress)
            status_prefix = ""
            if self.is_playlist and self.playlist_items_count > 0:
                hook_playlist_index = d.get('info_dict', {}).get('playlist_index')
                display_index = hook_playlist_index or self.current_playlist_item_dl_index + 1
                status_prefix = f"Item {display_index}/{self.playlist_items_count} - "
            status_msg = f"{status_prefix}Downloading: {percent_str} ({d.get('_downloaded_bytes_str', 'N/A')}/{total_bytes_str}) at {speed_str}, ETA: {eta_str}"
            self.status_callback(status_msg)
        else:
             self.status_callback(f"Status: {d['status']} - {item_title_cleaned}")


    # ----- START of Updated Function -----
    def _clean_filename(self, filename):
        """ينظف اسم الملف من الرموز غير المرغوبة."""
        if not filename:
            return filename
        # إزالة السلاسل والرموز المحددة (مع إضافة الرمز العريض)
        cleaned = filename.replace('//', '')
        cleaned = cleaned.replace('||', '')
        cleaned = cleaned.replace('|', '')  # البايب العادي
        cleaned = cleaned.replace('｜', '') # <-- إضافة البايب العريض Fullwidth Pipe
        cleaned = cleaned.replace('/', '')
        # يمكن إضافة رموز أخرى إذا لزم الأمر، مثل ':' التي قد تكون غير آمنة
        cleaned = cleaned.replace(':', ' -') # استبدال النقطتين بـ " - " للأمان

        # إزالة المسافات المتعددة واستبدالها بمسافة واحدة
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        return cleaned
    # ----- END of Updated Function -----


    def _my_hook(self, d):
        """Hook لتقدم التحميل مع تنظيف اسم الملف."""
        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled by user.")

        status = d['status']
        original_filepath = d.get('filename')

        if status == 'downloading':
            self._process_download_progress(d)
            self.last_hook_filename = original_filepath

        elif status == 'error':
            self.status_callback("Error during download process.")
            print(f"yt-dlp hook error: {d}")
        elif status == 'finished':
            if not original_filepath:
                print("Hook 'finished' status without filename.")
                self.status_callback("Processing finished file (unknown name)...")
                self.progress_callback(1.0)
                return

            dirname = os.path.dirname(original_filepath)
            original_basename = os.path.basename(original_filepath)
            # استخدام الدالة المحدثة للتنظيف Use the updated cleaning function
            cleaned_basename = self._clean_filename(original_basename)
            new_filepath = os.path.join(dirname, cleaned_basename)

            final_filepath_to_report = original_filepath

            if new_filepath != original_filepath and os.path.exists(original_filepath):
                try:
                    os.rename(original_filepath, new_filepath)
                    print(f"Renamed '{original_basename}' to '{cleaned_basename}'")
                    final_filepath_to_report = new_filepath
                    self.last_final_filepath = new_filepath
                except OSError as e:
                    print(f"Error renaming file '{original_basename}' to '{cleaned_basename}': {e}")
                    self.status_callback(f"Warning: Could not clean filename for {original_basename}")
            elif os.path.exists(new_filepath):
                 final_filepath_to_report = new_filepath
                 self.last_final_filepath = final_filepath_to_report
            elif os.path.exists(original_filepath):
                 final_filepath_to_report = original_filepath
                 self.last_final_filepath = final_filepath_to_report
            else:
                print(f"Warning: File '{original_filepath}' not found for reporting.")
                final_filepath_to_report = (
                    self.last_final_filepath
                    if self.last_final_filepath
                    and os.path.exists(self.last_final_filepath)
                    else None
                )
            final_basename = os.path.basename(final_filepath_to_report) if final_filepath_to_report else 'N/A'
            total_bytes_str = d.get('_total_bytes_str', 'N/A')
            status_msg = f"Finished: '{final_basename}' ({total_bytes_str}). Post-processing..."

            if self.is_playlist and original_filepath and self.last_hook_filename != original_filepath:
                self.current_playlist_item_dl_index += 1
                self.last_hook_filename = original_filepath
                status_msg = f"Item {self.current_playlist_item_dl_index}/{self.playlist_items_count} done: '{final_basename}'. Post-processing..."

            self.status_callback(status_msg)
            self.progress_callback(1.0)


    def _download_core(self):
        """المنطق الأساسي لعملية التحميل."""
        # ... (إعداد ydl_opts كما في الرد السابق) ...
        base_tmpl_name = ('%(playlist_index)s. %(title)s' if self.is_playlist else '%(title)s')
        ydl_opts = {
            'progress_hooks': [self._my_hook],
            'outtmpl': os.path.join(self.save_path, f'{base_tmpl_name}.%(ext)s'),
            'nocheckcertificate': True,
            'ignoreerrors': self.is_playlist,
            'postprocessor_hooks': [],
            'merge_output_format': 'mp4',
        }
        if self.ffmpeg_path: ydl_opts['ffmpeg_location'] = self.ffmpeg_path
        if self.is_playlist:
            ydl_opts['noplaylist'] = False
            if self.playlist_items: ydl_opts['playlist_items'] = self.playlist_items
        else: ydl_opts['noplaylist'] = True

        postprocessors = []
        format_choice_lower = self.format_choice.lower()
        quality_format_selector = None
        if self.quality_format_id: quality_format_selector = self.quality_format_id
        general_format_selector = None
        output_ext = 'mp4'

        if "<= 720p" in format_choice_lower:
            general_format_selector = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]'
        elif "<= 480p" in format_choice_lower:
            general_format_selector = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480][ext=mp4]/best[height<=480]'
        elif "<= 360p" in format_choice_lower:
            general_format_selector = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360][ext=mp4]/best[height<=360]'
        elif "audio (mp3)" in format_choice_lower:
            general_format_selector = 'bestaudio/best'
            output_ext = 'mp3'
            if self.ffmpeg_path:
                postprocessors.append({'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'})
            else:
                 self.status_callback("Warning: FFmpeg not found. Cannot convert to MP3.")
                 general_format_selector = 'bestaudio/best'
                 output_ext = None
        else: # Default
             general_format_selector = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best'

        final_format = quality_format_selector if quality_format_selector and not self.is_playlist else general_format_selector
        ydl_opts['format'] = final_format

        if output_ext:
            ydl_opts['outtmpl'] = os.path.join(self.save_path, f'{base_tmpl_name}.{output_ext}')

        if postprocessors: ydl_opts['postprocessors'] = postprocessors

        self.status_callback("Starting download...")
        self.progress_callback(0)
        self.current_playlist_item_dl_index = 0
        self.last_hook_filename = None
        self.last_final_filepath = None

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if self.cancel_event.is_set(): raise DownloadCancelled("Download cancelled before starting.")
            ydl.download([self.url])

        if self.cancel_event.is_set(): raise DownloadCancelled("Download cancelled after finishing.")

        final_completion_message = "Download and processing complete!"
        if self.is_playlist and self.playlist_items_count > 0:
            processed_count = self.current_playlist_item_dl_index
            final_completion_message = f"Playlist download complete ({processed_count}/{self.playlist_items_count} items processed)."

        self.status_callback(final_completion_message)


    def run(self):
        """تنفذ عملية التحميل الفعلية."""
        try:
            self._download_core()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split('ERROR:')[-1].strip()
            self.status_callback(f"Download Error: {error_message}")
            print(f"yt-dlp DownloadError: {e}")
        except Exception as e:
            self.status_callback(f"Unexpected download error: {type(e).__name__} - {e}")
            print(f"Unexpected Error during download: {e}")
        finally:
            self.finished_callback()