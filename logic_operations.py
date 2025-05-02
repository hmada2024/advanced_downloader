# -- ملف يحتوي على الكلاسات المسؤولة عن التفاعل المباشر مع yt-dlp --
# Purpose: Contains classes that perform the actual work of interacting with yt-dlp.

import os
import yt_dlp
import sys
from pathlib import Path
from exceptions import DownloadCancelled # استيراد الاستثناء المخصص

# --- دالة مساعدة للبحث عن FFmpeg ---
def find_ffmpeg():
    """
    يحاول العثور على ملف ffmpeg.exe التنفيذي المرفق مع التطبيق.
    Tries to find the bundled ffmpeg executable.
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

    def run(self):
        try:
            self._extracted_from_run_3()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split('ERROR:')[-1].strip()
            self.status_callback(f"Info Error: {error_message}")
            self.error_callback(error_message)
            print(f"yt-dlp DownloadError during info fetch: {e}")
        except Exception as e:
            self.status_callback(f"An unexpected error occurred during info fetch: {type(e).__name__}")
            self.error_callback(f"Unexpected error: {e}")
            print(f"Unexpected Error during info fetch: {e}")
        finally:
            self.finished_callback()

    # TODO Rename this here and in `run`
    def _extracted_from_run_3(self):
        self.status_callback("Fetching information...")
        self.progress_callback(0)

        ydl_opts = {
            'quiet': True,
            'nocheckcertificate': True,
            'extract_flat': 'in_playlist',
            'playlistend': 500,
            'ignoreerrors': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if self.cancel_event.is_set():
                raise DownloadCancelled("Info fetch cancelled before starting.")
            info_dict = ydl.extract_info(self.url, download=False)

        if self.cancel_event.is_set():
             raise DownloadCancelled("Info fetch cancelled after fetching.")

        self.status_callback("Information fetched successfully.")
        self.success_callback(info_dict)


# --- كلاس لتنفيذ التحميل ---
class Downloader:
    """كلاس مسؤول عن عملية التحميل الفعلية باستخدام yt-dlp."""
    def __init__(self, url, save_path, format_choice, quality_format_id,
                 is_playlist, playlist_items, ffmpeg_path,
                 cancel_event, status_callback, progress_callback, finished_callback):
        self.url = url
        self.save_path = save_path
        self.format_choice = format_choice # سيحتوي على الأسماء الجديدة Contains the new names
        self.quality_format_id = quality_format_id
        self.is_playlist = is_playlist
        self.playlist_items = playlist_items
        self.ffmpeg_path = ffmpeg_path
        self.cancel_event = cancel_event
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

    def _my_hook(self, d):
        """Hook لتقدم التحميل."""
        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled by user.")

        if d['status'] == 'downloading':
            self._extracted_from__my_hook_7(d)
        elif d['status'] == 'finished':
            filename = d.get('filename', 'N/A')
            total_bytes_str = d.get('_total_bytes_str', 'N/A')
            self.status_callback(f"Finished downloading '{os.path.basename(filename)}' ({total_bytes_str}). Post-processing...")
            self.progress_callback(1.0)
        elif d['status'] == 'error':
            self.status_callback("Error during download process.")
            print(f"yt-dlp hook error: {d}")

    # TODO Rename this here and in `_my_hook`
    def _extracted_from__my_hook_7(self, d):
        total_bytes_str = d.get('_total_bytes_str', 'N/A')
        downloaded_bytes = d.get('downloaded_bytes')
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
        speed_str = d.get('_speed_str', 'N/A')
        eta_str = d.get('_eta_str', 'N/A')
        percent_str = d.get('_percent_str', 'N/A').strip()

        if total_bytes and downloaded_bytes:
            progress = downloaded_bytes / total_bytes
            self.progress_callback(progress)
            # !! ملاحظة: سيتم تحسين هذه الرسالة في المرحلة الثانية لعرض تفاصيل القائمة
            # !! NOTE: This message will be enhanced in Phase 2 for playlist details
            status_msg = f"Downloading: {percent_str} ({d.get('_downloaded_bytes_str', 'N/A')}/{total_bytes_str}) at {speed_str}, ETA: {eta_str}"
            self.status_callback(status_msg)
        else:
             filename = d.get('filename', 'N/A') # الحصول على اسم الملف هنا
             self.status_callback(f"Status: {d['status']} - {os.path.basename(filename)}") # عرض اسم الملف الأساسي

    def run(self):
        """تنفذ عملية التحميل الفعلية."""
        try:
            self._extracted_from_run_()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split('ERROR:')[-1].strip()
            self.status_callback(f"Download Error: {error_message}") # سيتم تحسين هذا في المرحلة 3 This will be improved in Phase 3
            print(f"yt-dlp DownloadError: {e}")
        except Exception as e:
            self.status_callback(f"An unexpected error occurred: {type(e).__name__}") # سيتم تحسين هذا في المرحلة 3 This will be improved in Phase 3
            print(f"Unexpected Error during download: {e}")
        finally:
            self.finished_callback()

    # TODO Rename this here and in `run`
    def _extracted_from_run_(self):
            # --- START Phase 1 Change: Modify output template and add restrictfilenames ---
            # تحديد قالب اسم الملف الأساسي بناءً على نوع التحميل
            # Determine base filename template based on download type
        base_tmpl_name = (
            '%(playlist_index)s. %(title)s' if self.is_playlist else '%(title)s'
        )
        ydl_opts = {
            'progress_hooks': [self._my_hook],
            'outtmpl': os.path.join(self.save_path, f'{base_tmpl_name}.%(ext)s'),
            'nocheckcertificate': True,
            'ignoreerrors': self.is_playlist,
            'postprocessor_hooks': [],
            'merge_output_format': 'mp4',
        }
        # --- END Phase 1 Change ---

        # --- إضافة مسار FFmpeg ---
        if self.ffmpeg_path:
            ydl_opts['ffmpeg_location'] = self.ffmpeg_path
        elif "Audio (mp3)" in self.format_choice.lower() or self.quality_format_id:
            self.status_callback("Warning: FFmpeg not found. MP3 conversion or format merging might fail.")

        # --- التعامل مع خيارات قائمة التشغيل ---
        if self.is_playlist:
            ydl_opts['noplaylist'] = False
            if self.playlist_items:
                ydl_opts['playlist_items'] = self.playlist_items
        else:
             ydl_opts['noplaylist'] = True

        # --- منطق اختيار الصيغة والجودة (سيتم تعديله في المرحلة 2) ---
        # --- Format/Quality Logic (Will be modified in Phase 2) ---
        postprocessors = []
        if self.quality_format_id:
                 # تم اختيار جودة محددة من القائمة السفلية (فيديو مفرد)
                 # Specific quality selected from bottom list (single video)
            ydl_opts['format'] = self.quality_format_id
                # إضافة تحويل MP3 إذا كانت الصيغة العامة المطلوبة هي MP3
            if "audio (mp3)" in self.format_choice.lower(): # تحقق غير حساس لحالة الأحرف Case-insensitive check
                postprocessors.append({
                   'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',
                })
                     # تعديل قالب الإخراج لضمان امتداد mp3 (yt-dlp سيفعل هذا غالبًا)
                     # Adjust template for mp3 (yt-dlp usually handles this)
                ydl_opts['outtmpl'] = os.path.join(self.save_path, f'{base_tmpl_name}.mp3')
        elif "audio (mp3)" in self.format_choice.lower(): # تحقق غير حساس لحالة الأحرف
            ydl_opts['format'] = 'bestaudio/best'
            postprocessors.append({
                'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',
            })
            ydl_opts['outtmpl'] = os.path.join(self.save_path, f'{base_tmpl_name}.mp3')
        else: # أي خيار آخر يعتبر فيديو MP4 حاليًا Any other choice is currently treated as MP4 video
            # الصيغة القديمة لأفضل MP4 The old format string for best MP4
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best'
            # لا نحتاج لمعالج MP4 هنا No MP4 postprocessor needed here

        # إضافة المعالجات اللاحقة إذا وجدت
        if postprocessors:
            ydl_opts['postprocessors'] = postprocessors

        # بدء عملية التحميل
        self.status_callback("Starting download...")
        self.progress_callback(0)

        # --- تشغيل yt-dlp ---
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if self.cancel_event.is_set():
                raise DownloadCancelled("Download cancelled before starting.")
            ydl.download([self.url])

        if self.cancel_event.is_set():
             raise DownloadCancelled("Download cancelled after finishing.")

        self.status_callback("Download and processing complete!")