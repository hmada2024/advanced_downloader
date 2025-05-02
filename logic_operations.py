# -- ملف يحتوي على الكلاسات المسؤولة عن التفاعل المباشر مع yt-dlp --
import os
import yt_dlp
import sys
from pathlib import Path
from exceptions import DownloadCancelled
import re # استيراد للتعابير النمطية Import regex for title cleaning

# --- دالة البحث عن FFmpeg (بدون تغيير) ---
def find_ffmpeg():
    try: base_path = Path(sys.argv[0]).parent
    except Exception: base_path = Path(".")
    bundled_path = base_path / "ffmpeg_bin" / "ffmpeg.exe"
    if bundled_path.is_file():
        print(f"Found bundled ffmpeg: {bundled_path}")
        return str(bundled_path)
    print("Warning: Bundled ffmpeg not found.")
    return None

# --- كلاس InfoFetcher (بدون تغيير جوهري) ---
class InfoFetcher:
    def __init__(self, url, cancel_event, success_callback, error_callback, status_callback, progress_callback, finished_callback):
        self.url = url
        self.cancel_event = cancel_event
        self.success_callback = success_callback
        self.error_callback = error_callback
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

    def _fetch_info_core(self): # دالة معاد تسميتها
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
        try:
            self._fetch_info_core()
        except DownloadCancelled as e:
             self.status_callback(str(e)); print(e)
        except yt_dlp.utils.DownloadError as e:
             # سيتم تحسين هذا في المرحلة 3
             error_message = str(e).split('ERROR:')[-1].strip()
             self.status_callback(f"Info Error: {error_message}")
             self.error_callback(error_message); print(f"yt-dlp DownloadError info fetch: {e}")
        except Exception as e:
             # سيتم تحسين هذا في المرحلة 3
             self.status_callback(f"Unexpected info fetch error: {type(e).__name__}")
             self.error_callback(f"Unexpected error: {e}"); print(f"Unexpected Error info fetch: {e}")
        finally:
            self.finished_callback()

# --- كلاس Downloader ---
class Downloader:
    # -- START Phase 2 Change: Add playlist_items_count to init --
    def __init__(self, url, save_path, format_choice, quality_format_id,
                 is_playlist, playlist_items, playlist_items_count, ffmpeg_path,
                 cancel_event, status_callback, progress_callback, finished_callback):
    # -- END Phase 2 Change --
        self.url = url
        self.save_path = save_path
        self.format_choice = format_choice # الخيار الجديد من الواجهة
        self.quality_format_id = quality_format_id
        self.is_playlist = is_playlist
        self.playlist_items = playlist_items
        # -- START Phase 2 Change: Store count and initialize index --
        self.playlist_items_count = playlist_items_count # تخزين العدد
        self.current_playlist_item_dl_index = 0 # عداد داخلي للعنصر الحالي (يبدأ من 0)
        self.last_hook_filename = None # لتتبع تغيير اسم الملف في الهوك
        # -- END Phase 2 Change --
        self.ffmpeg_path = ffmpeg_path
        self.cancel_event = cancel_event
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

    def _process_download_progress(self, d): # دالة معاد تسميتها
        """تحلل بيانات الهوك وتحدث الواجهة."""
        total_bytes_str = d.get('_total_bytes_str', 'N/A')
        downloaded_bytes = d.get('downloaded_bytes')
        total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
        speed_str = d.get('_speed_str', 'N/A')
        eta_str = d.get('_eta_str', 'N/A')
        percent_str = d.get('_percent_str', 'N/A').strip()
        filename = d.get('filename', 'N/A')
        item_title = d.get('info_dict', {}).get('title', os.path.basename(filename)) # محاولة الحصول على العنوان
        # تنظيف بسيط للعنوان (إزالة الامتداد إن وجد في العنوان نفسه)
        item_title_cleaned = re.sub(r'\.[a-zA-Z0-9]+$', '', item_title)


        if total_bytes and downloaded_bytes:
            progress = downloaded_bytes / total_bytes
            self.progress_callback(progress)

            # -- START Phase 2 Change: Enhance status message for playlists --
            status_prefix = ""
            if self.is_playlist and self.playlist_items_count > 0:
                # محاولة الحصول على الفهرس الفعلي من الهوك إن أمكن
                hook_playlist_index = d.get('info_dict', {}).get('playlist_index')
                display_index = hook_playlist_index if hook_playlist_index else (self.current_playlist_item_dl_index + 1)
                status_prefix = f"Item {display_index}/{self.playlist_items_count} - "
            # -- END Phase 2 Change --

            status_msg = f"{status_prefix}Downloading: {percent_str} ({d.get('_downloaded_bytes_str', 'N/A')}/{total_bytes_str}) at {speed_str}, ETA: {eta_str}"
            self.status_callback(status_msg)
        else:
             # عرض اسم الملف إذا لم تتوفر معلومات التقدم التفصيلية
             self.status_callback(f"Status: {d['status']} - {item_title_cleaned}")


    def _my_hook(self, d):
        """Hook لتقدم التحميل."""
        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled by user.")

        status = d['status']
        filename = d.get('filename') # الحصول على اسم الملف الحالي

        if status == 'downloading':
            self._process_download_progress(d)
            self.last_hook_filename = filename # تحديث آخر اسم ملف شوهد

        elif status == 'finished':
            base_filename = os.path.basename(filename) if filename else 'N/A'
            total_bytes_str = d.get('_total_bytes_str', 'N/A')
            status_msg = f"Finished downloading '{base_filename}' ({total_bytes_str}). Post-processing..."

            # -- START Phase 2 Change: Increment playlist index carefully --
            # زيادة العداد فقط إذا تغير اسم الملف الرئيسي (لتجنب الزيادة المزدوجة للصوت/الفيديو)
            # وكانت العملية الحالية قد انتهت
            if self.is_playlist and filename and self.last_hook_filename != filename:
                self.current_playlist_item_dl_index += 1
                self.last_hook_filename = filename # تحديث الاسم بعد الزيادة
                # تحديث الحالة لتعكس العنصر المكتمل
                status_msg = f"Item {self.current_playlist_item_dl_index}/{self.playlist_items_count} downloaded: '{base_filename}'. Post-processing..."

            # -- END Phase 2 Change --

            self.status_callback(status_msg)
            self.progress_callback(1.0) # إظهار اكتمال التقدم للملف الحالي

        elif status == 'error':
            self.status_callback("Error during download process.") # سيتم تحسينه في المرحلة 3
            print(f"yt-dlp hook error: {d}")

    def _download_core(self): # دالة معاد تسميتها
        """المنطق الأساسي لعملية التحميل."""
        # تحديد قالب اسم الملف الأساسي
        base_tmpl_name = ('%(playlist_index)s. %(title)s' if self.is_playlist else '%(title)s')
        # إعداد خيارات yt-dlp الأساسية
        ydl_opts = {
            'progress_hooks': [self._my_hook],
            'outtmpl': os.path.join(self.save_path, f'{base_tmpl_name}.%(ext)s'),
            'nocheckcertificate': True,
            'ignoreerrors': self.is_playlist,
            'postprocessor_hooks': [],
            'merge_output_format': 'mp4',
            # 'restrictfilenames': True, # <-- تم إزالته بناءً على ملاحظتك Removed based on your feedback
        }

        # إضافة مسار FFmpeg
        if self.ffmpeg_path:
            ydl_opts['ffmpeg_location'] = self.ffmpeg_path
        elif "audio (mp3)" in self.format_choice.lower() or self.quality_format_id:
            self.status_callback("Warning: FFmpeg not found.") # سيتم تحسينه

        # التعامل مع خيارات قائمة التشغيل
        if self.is_playlist:
            ydl_opts['noplaylist'] = False
            if self.playlist_items: ydl_opts['playlist_items'] = self.playlist_items
        else: ydl_opts['noplaylist'] = True

        # --- START Phase 2 Change: Implement new format logic ---
        postprocessors = []
        format_choice_lower = self.format_choice.lower()

        # بناء سلسلة صيغة الجودة المحددة
        quality_format_selector = None
        if self.quality_format_id: # جودة محددة من القائمة السفلية (فيديو مفرد)
            quality_format_selector = self.quality_format_id

        # بناء سلسلة صيغة من الخيار العام
        general_format_selector = None
        output_ext = 'mp4' # الامتداد الافتراضي

        if "<= 720p" in format_choice_lower:
            general_format_selector = 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]'
        elif "<= 480p" in format_choice_lower:
            general_format_selector = 'bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480][ext=mp4]/best[height<=480]'
        elif "<= 360p" in format_choice_lower:
            general_format_selector = 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360][ext=mp4]/best[height<=360]'
        elif "audio (mp3)" in format_choice_lower:
            general_format_selector = 'bestaudio/best'
            output_ext = 'mp3'
            postprocessors.append({
                'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',
            })
        else: # الخيار الافتراضي (Best Quality MP4 <= 1080p+)
             general_format_selector = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best'

        # تحديد الصيغة النهائية المستخدمة
        # الأولوية للجودة المحددة (quality_format_id) إذا كانت موجودة (للفيديو المفرد فقط)
        # وإلا نستخدم الخيار العام (general_format_selector)
        final_format = quality_format_selector if quality_format_selector else general_format_selector
        ydl_opts['format'] = final_format

        # تحديث قالب الإخراج إذا كان صوت MP3
        if output_ext == 'mp3':
            ydl_opts['outtmpl'] = os.path.join(self.save_path, f'{base_tmpl_name}.mp3')
        else: # التأكد من استخدام الامتداد الصحيح للفيديو (عادة mp4 بسبب merge_output_format)
            ydl_opts['outtmpl'] = os.path.join(self.save_path, f'{base_tmpl_name}.%(ext)s')


        # إضافة المعالجات اللاحقة
        if postprocessors:
            ydl_opts['postprocessors'] = postprocessors
        # --- END Phase 2 Change ---

        # بدء التحميل
        self.status_callback("Starting download...")
        self.progress_callback(0)
        self.current_playlist_item_dl_index = 0 # إعادة تعيين عداد القائمة قبل البدء
        self.last_hook_filename = None        # إعادة تعيين اسم الملف للهوك

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if self.cancel_event.is_set(): raise DownloadCancelled("Download cancelled before starting.")
            ydl.download([self.url])

        if self.cancel_event.is_set(): raise DownloadCancelled("Download cancelled after finishing.")

        # تعديل رسالة الاكتمال النهائية
        final_completion_message = "Download and processing complete!"
        if self.is_playlist and self.playlist_items_count > 0:
            final_completion_message = f"Playlist download complete ({self.current_playlist_item_dl_index} items processed)."
            # ملاحظة: قد لا يكون العداد دقيقًا 100% إذا حدثت أخطاء أو تم الإلغاء
            # Note: Count might not be 100% accurate if errors/cancellation occurred

        self.status_callback(final_completion_message)


    def run(self):
        """تنفذ عملية التحميل الفعلية."""
        try:
            self._download_core() # استدعاء المنطق الأساسي
        except DownloadCancelled as e:
             self.status_callback(str(e)); print(e)
        except yt_dlp.utils.DownloadError as e:
             error_message = str(e).split('ERROR:')[-1].strip()
             self.status_callback(f"Download Error: {error_message}") # سيتم تحسينه
             print(f"yt-dlp DownloadError: {e}")
        except Exception as e:
             self.status_callback(f"Unexpected download error: {type(e).__name__}") # سيتم تحسينه
             print(f"Unexpected Error during download: {e}")
        finally:
            self.finished_callback()