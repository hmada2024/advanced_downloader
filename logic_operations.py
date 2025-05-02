# -- ملف يحتوي على الكلاسات المسؤولة عن التفاعل المباشر مع yt-dlp --
# Purpose: Contains classes that perform the actual work of interacting with yt-dlp.

import os
import yt_dlp
import sys
from pathlib import Path
from exceptions import DownloadCancelled # استيراد الاستثناء المخصص

# --- دالة مساعدة للبحث عن FFmpeg (يمكن نقلها لملف utils لاحقًا إذا كبر المشروع) ---
def find_ffmpeg():
    """
    يحاول العثور على ملف ffmpeg.exe التنفيذي المرفق مع التطبيق.
    Tries to find the bundled ffmpeg executable.

    Returns:
        str or None: مسار FFmpeg إذا تم العثور عليه، وإلا None.
                     Path to ffmpeg if found, otherwise None.
    """
    # تحديد المسار المتوقع لـ ffmpeg بناءً على مسار السكربت الحالي
    # Determine expected path based on the current script's location
    try:
        # الطريقة المفضلة لمعرفة مسار السكربت
        # Preferred way to get script path
        base_path = Path(sys.argv[0]).parent
    except Exception:
        # طريقة بديلة إذا فشلت الطريقة الأولى
        # Fallback if the first method fails
        base_path = Path(".")

    bundled_path = base_path / "ffmpeg_bin" / "ffmpeg.exe"
    if bundled_path.is_file():
        print(f"Found bundled ffmpeg: {bundled_path}")
        return str(bundled_path)
    print("Warning: Bundled ffmpeg not found. yt-dlp might rely on system PATH or fail some operations.")
    return None

# --- كلاس لجلب المعلومات ---
# Class for fetching information
class InfoFetcher:
    """كلاس مسؤول عن عملية جلب معلومات الفيديو/القائمة."""
    """Class responsible for fetching video/playlist information."""

    def __init__(self, url, cancel_event, success_callback, error_callback, status_callback, progress_callback, finished_callback):
        """
        تهيئة جالب المعلومات.
        Initializes the InfoFetcher.

        Args:
            url (str): رابط الفيديو أو القائمة. URL of the video/playlist.
            cancel_event (threading.Event): حدث لمراقبة طلب الإلغاء. Event to monitor cancellation requests.
            success_callback (callable): دالة تُستدعى عند النجاح مع قاموس المعلومات. Callback on success with info dict.
            error_callback (callable): دالة تُستدعى عند الفشل مع رسالة الخطأ. Callback on error with error message.
            status_callback (callable): دالة لتحديث نص الحالة. Callback to update status text.
            progress_callback (callable): دالة لتحديث شريط التقدم. Callback to update progress bar.
            finished_callback (callable): دالة تُستدعى عند انتهاء العملية دائمًا. Callback always called when the operation finishes.
        """
        self.url = url
        self.cancel_event = cancel_event
        self.success_callback = success_callback
        self.error_callback = error_callback
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

    def run(self):
        """
        تنفذ عملية جلب المعلومات. يتم تشغيلها عادة في خيط منفصل.
        Executes the information fetching process. Usually run in a separate thread.
        """
        try:
            self.status_callback("Fetching information...")
            self.progress_callback(0) # إعادة تعيين التقدم Reset progress

            # خيارات yt-dlp لجلب المعلومات فقط
            # yt-dlp options for fetching info only
            ydl_opts = {
                'quiet': True,              # منع طباعة yt-dlp في الطرفية Suppress yt-dlp console output
                'nocheckcertificate': True, # تجاهل التحقق من شهادة SSL Ignore SSL certificate verification
                'extract_flat': 'in_playlist', # أسرع للقوائم، يجلب المعلومات الأساسية Faster for playlists, gets basic info
                # 'dump_single_json': True, # طريقة بديلة للحصول على المعلومات Alternative way to get info
                'playlistend': 500,        # تحديد حد أقصى لعدد عناصر القائمة المقروءة (لتجنب البطء الشديد في القوائم الضخمة) Limit playlist items read (performance)
                 'ignoreerrors': True,       # تجاهل الأخطاء الفردية في عناصر القائمة عند الجلب الأولي Ignore individual item errors during initial fetch
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                 # التحقق من الإلغاء قبل بدء الطلب Check for cancellation before starting the request
                if self.cancel_event.is_set():
                    raise DownloadCancelled("Info fetch cancelled before starting.")

                # استدعاء yt-dlp لجلب المعلومات Call yt-dlp to fetch info
                info_dict = ydl.extract_info(self.url, download=False)

            # التحقق من الإلغاء بعد انتهاء الطلب (قد يستغرق وقتًا) Check for cancellation after the potentially long request
            if self.cancel_event.is_set():
                 raise DownloadCancelled("Info fetch cancelled after fetching.")

            # النجاح: استدعاء الكول باك الخاص بالنجاح وإرسال البيانات
            # Success: Call the success callback and send the data
            self.status_callback("Information fetched successfully.")
            self.success_callback(info_dict)

        except DownloadCancelled as e:
             # تم الإلغاء Cancelled by user
             self.status_callback(str(e))
             print(str(e))
        except yt_dlp.utils.DownloadError as e:
             # خطأ محدد من yt-dlp Specific yt-dlp error
            error_message = str(e).split('ERROR:')[-1].strip()
            self.status_callback(f"Info Error: {error_message}")
            self.error_callback(error_message) # إبلاغ الواجهة بالخطأ Inform UI about the error
            print(f"yt-dlp DownloadError during info fetch: {e}")
        except Exception as e:
             # أي خطأ آخر غير متوقع Any other unexpected error
            self.status_callback(f"An unexpected error occurred during info fetch: {type(e).__name__}")
            self.error_callback(f"Unexpected error: {e}")
            print(f"Unexpected Error during info fetch: {e}")
        finally:
            # دائمًا استدعاء finished_callback في النهاية Always call finished_callback at the end
            self.finished_callback()


# --- كلاس لتنفيذ التحميل ---
# Class for executing downloads
class Downloader:
    """كلاس مسؤول عن عملية التحميل الفعلية باستخدام yt-dlp."""
    """Class responsible for the actual download process using yt-dlp."""

    def __init__(self, url, save_path, format_choice, quality_format_id,
                 is_playlist, playlist_items, ffmpeg_path,
                 cancel_event, status_callback, progress_callback, finished_callback):
        """
        تهيئة المحمل.
        Initializes the Downloader.

        Args:
            url (str): رابط الفيديو/القائمة. URL.
            save_path (str): مسار مجلد الحفظ. Save directory path.
            format_choice (str): الصيغة العامة المطلوبة ('Video (mp4, Best)' or 'Audio (mp3)'). General format choice.
            quality_format_id (str or None): معرف الجودة المحدد (إذا تم اختياره). Specific quality format ID (if selected).
            is_playlist (bool): هل يتم التعامل معه كقائمة تشغيل؟ Is it treated as a playlist?
            playlist_items (str or None): سلسلة العناصر المحددة في القائمة. String of selected playlist items.
            ffmpeg_path (str or None): مسار ملف ffmpeg.exe. Path to ffmpeg.exe.
            cancel_event (threading.Event): حدث لمراقبة الإلغاء. Event to monitor cancellation.
            status_callback (callable): كول باك لتحديث الحالة. Callback for status updates.
            progress_callback (callable): كول باك لتحديث التقدم. Callback for progress updates.
            finished_callback (callable): كول باك عند الانتهاء. Callback when finished.
        """
        self.url = url
        self.save_path = save_path
        self.format_choice = format_choice
        self.quality_format_id = quality_format_id
        self.is_playlist = is_playlist
        self.playlist_items = playlist_items
        self.ffmpeg_path = ffmpeg_path
        self.cancel_event = cancel_event
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

    def _my_hook(self, d):
        """
        دالة خطاف التقدم (progress hook) لـ yt-dlp، تتحقق من الإلغاء.
        Progress hook for yt-dlp, checks for cancellation.
        """
        # التحقق من إشارة الإلغاء Check for cancellation signal
        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled by user.")

        # تحليل حالة التقدم وتحديث الواجهة Analyze progress status and update UI
        if d['status'] == 'downloading':
            filename = d.get('filename', 'N/A')
            total_bytes_str = d.get('_total_bytes_str', 'N/A')
            downloaded_bytes = d.get('downloaded_bytes')
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            speed_str = d.get('_speed_str', 'N/A')
            eta_str = d.get('_eta_str', 'N/A')
            percent_str = d.get('_percent_str', 'N/A').strip()

            if total_bytes and downloaded_bytes:
                progress = downloaded_bytes / total_bytes
                self.progress_callback(progress) # تحديث شريط التقدم Update progress bar
                status_msg = f"Downloading: {percent_str} ({d.get('_downloaded_bytes_str', 'N/A')}/{total_bytes_str}) at {speed_str}, ETA: {eta_str}"
                self.status_callback(status_msg) # تحديث نص الحالة Update status text
            else:
                 self.status_callback(f"Status: {d['status']} - {filename}")

        elif d['status'] == 'finished':
            # انتهى تحميل الملف، قد تبدأ المعالجة اللاحقة File download finished, post-processing might start
            filename = d.get('filename', 'N/A')
            total_bytes_str = d.get('_total_bytes_str', 'N/A')
            self.status_callback(f"Finished downloading '{os.path.basename(filename)}' ({total_bytes_str}). Post-processing...")
            self.progress_callback(1.0) # إظهار اكتمال التقدم Show progress completion
        elif d['status'] == 'error':
            self.status_callback("Error during download process.")
            print(f"yt-dlp hook error: {d}") # طباعة الخطأ في الطرفية Print error to console

    def run(self):
        """
        تنفذ عملية التحميل الفعلية. يتم تشغيلها عادة في خيط منفصل.
        Executes the actual download process. Usually run in a separate thread.
        """
        try:
            # إعداد خيارات yt-dlp الأساسية Set up basic yt-dlp options
            ydl_opts = {
                'progress_hooks': [self._my_hook], # استخدام دالة الخطاف الخاصة بنا Use our hook function
                'outtmpl': os.path.join(self.save_path, '%(title)s [%(id)s].%(ext)s'), # قالب اسم الملف Output filename template
                'nocheckcertificate': True,
                'ignoreerrors': self.is_playlist, # تجاهل الأخطاء في القوائم Ignore errors in playlists
                 'postprocessor_hooks': [], # يمكن إضافة خطافات للمعالجة اللاحقة هنا Can add postprocessor hooks here
                 'merge_output_format': 'mp4', # تفضيل الدمج في mp4 Prefer merging into mp4
            }

            # --- إضافة مسار FFmpeg --- Add FFmpeg path ---
            if self.ffmpeg_path:
                ydl_opts['ffmpeg_location'] = self.ffmpeg_path
            else:
                 if self.format_choice == 'Audio (mp3)' or self.quality_format_id: # تحذير فقط إذا كان قد يكون مطلوبًا Warn only if potentially needed
                     self.status_callback("Warning: FFmpeg not found. MP3 conversion or format merging might fail.")

            # --- التعامل مع خيارات قائمة التشغيل --- Handle playlist options ---
            if self.is_playlist:
                ydl_opts['noplaylist'] = False # تأكيد أنها قائمة Confirm it's a playlist
                if self.playlist_items: # إذا تم تحديد عناصر محددة If specific items are selected
                    ydl_opts['playlist_items'] = self.playlist_items
            else: # فيديو مفرد أو قائمة كمفرد Single video or playlist as single
                 ydl_opts['noplaylist'] = True

            # --- منطق اختيار الصيغة والجودة --- Format and quality selection logic ---
            postprocessors = [] # قائمة للمعالجات اللاحقة List for postprocessors
            output_template = ydl_opts['outtmpl'] # القالب الافتراضي Default template

            if self.quality_format_id:
                # تم اختيار جودة محددة User selected a specific quality
                ydl_opts['format'] = self.quality_format_id
                # إضافة تحويل MP3 إذا كانت الصيغة العامة المطلوبة هي MP3 Add MP3 conversion if the general choice was MP3
                if self.format_choice == 'Audio (mp3)':
                     postprocessors.append({
                        'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',
                     })
                     # تعديل قالب الإخراج لضمان امتداد mp3 Update output template for mp3 extension
                     output_template = os.path.join(self.save_path, '%(title)s [%(id)s].mp3')
            else:
                # تم اختيار الصيغة العامة User selected the general format
                if self.format_choice == 'Audio (mp3)':
                    ydl_opts['format'] = 'bestaudio/best' # اختيار أفضل صوت Select best audio
                    postprocessors.append({
                        'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',
                    })
                    output_template = os.path.join(self.save_path, '%(title)s [%(id)s].mp3')
                elif self.format_choice == 'Video (mp4, Best)':
                    # طلب أفضل فيديو وصوت مدمجين في mp4 Request best video and audio merged into mp4
                    ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best'
                    # لا حاجة لمعالج لاحق لـ mp4 إذا استخدمنا هذا التنسيق Usually no need for mp4 postprocessor with this format string
                    # postprocessors.append({'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4'}) # قد يكون ضروريًا في حالات نادرة Might be needed in rare cases
                    output_template = os.path.join(self.save_path, '%(title)s [%(id)s].mp4')
                else: # صيغة افتراضية Fallback format
                    ydl_opts['format'] = 'best'

            # تحديث قالب الإخراج النهائي Update final output template
            ydl_opts['outtmpl'] = output_template
            # إضافة المعالجات اللاحقة إذا وجدت Add postprocessors if any
            if postprocessors:
                ydl_opts['postprocessors'] = postprocessors

            # بدء عملية التحميل Start the download process
            self.status_callback("Starting download...")
            self.progress_callback(0)

            # --- تشغيل yt-dlp --- Run yt-dlp ---
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # التحقق من الإلغاء قبل البدء Check cancellation before starting
                if self.cancel_event.is_set():
                    raise DownloadCancelled("Download cancelled before starting.")
                # استدعاء التحميل Call download
                ydl.download([self.url])

            # التحقق من الإلغاء بعد الانتهاء Check cancellation after finishing
            if self.cancel_event.is_set():
                 raise DownloadCancelled("Download cancelled after finishing.")

            # اكتمال التحميل بنجاح Download completed successfully
            self.status_callback("Download and processing complete!")

        except DownloadCancelled as e:
             # تم الإلغاء Cancelled by user
             self.status_callback(str(e))
             print(str(e))
        except yt_dlp.utils.DownloadError as e:
             # خطأ محدد من yt-dlp Specific yt-dlp error
            error_message = str(e).split('ERROR:')[-1].strip()
            self.status_callback(f"Download Error: {error_message}")
            print(f"yt-dlp DownloadError: {e}")
        except Exception as e:
             # أي خطأ آخر غير متوقع Any other unexpected error
            self.status_callback(f"An unexpected error occurred during download: {type(e).__name__} - {e}")
            print(f"Unexpected Error during download: {e}")
        finally:
            # دائمًا استدعاء finished_callback Always call finished_callback
            self.finished_callback()