# -- ملف يحتوي على الكلاسات المسؤولة عن التفاعل المباشر مع yt-dlp --
# Purpose: Contains classes that perform the actual work of interacting with yt-dlp.

import os
import yt_dlp
import sys
from pathlib import Path
# استخدام الاستيراد النسبي للملفات داخل نفس الحزمة
from .exceptions import DownloadCancelled  # <-- تم التعديل: استخدام .
import re
import traceback
import time # لاستخدامه المحتمل في التنظيف

# --- دالة find_ffmpeg ---
def find_ffmpeg():
    """
    يحاول العثور على ملف ffmpeg.exe التنفيذي المرفق مع التطبيق.
    Attempts to find the bundled ffmpeg.exe executable.
    """
    try:
        # الحصول على مسار المجلد الذي يحتوي على السكربت الحالي أو الملف التنفيذي
        if getattr(sys, 'frozen', False):
            # إذا كان التطبيق مجمداً (بواسطة PyInstaller)
            base_path = Path(sys.executable).parent
        else:
            # إذا كان يعمل كسكربت بايثون عادي
            base_path = Path(__file__).parent.parent # .parent للوصول لـ src، .parent مرة أخرى للجذر
    except Exception:
        # في حال فشل الطرق السابقة، استخدم المجلد الحالي كاحتياط
        base_path = Path(".")

    # بناء المسار المتوقع لمجلد ffmpeg_bin
    bundled_path = base_path / "ffmpeg_bin" / "ffmpeg.exe"

    if bundled_path.is_file():
        print(f"Found bundled ffmpeg: {bundled_path}")
        return str(bundled_path)
    else:
        # محاولة البحث في المسار العام (PATH) كاحتياط
        try:
            ffmpeg_path_in_env = yt_dlp.utils.ffmpeg_executable()
            if ffmpeg_path_in_env and Path(ffmpeg_path_in_env).is_file():
                 print(f"Warning: Bundled ffmpeg not found at '{bundled_path}'. Using ffmpeg from PATH: {ffmpeg_path_in_env}")
                 return ffmpeg_path_in_env
        except Exception:
             pass # فشل العثور عليه في PATH أيضًا

        print(f"Warning: Bundled ffmpeg not found at '{bundled_path}' and not found in system PATH.")
        return None # لم يتم العثور عليه

# --- كلاس لجلب المعلومات ---
class InfoFetcher:
    """كلاس مسؤول عن عملية جلب معلومات الفيديو/القائمة."""
    """Class responsible for fetching video/playlist information."""

    def __init__(self, url, cancel_event, success_callback, error_callback, status_callback, progress_callback, finished_callback):
        self.url = url
        self.cancel_event = cancel_event
        self.success_callback = success_callback
        self.error_callback = error_callback
        self.status_callback = status_callback
        self.progress_callback = progress_callback # قد لا يستخدم لكن نحافظ عليه للتناسق
        self.finished_callback = finished_callback

    def _check_cancel(self, stage=""):
        """يتحقق من طلب الإلغاء ويطلق استثناء إذا تم طلبه."""
        """Checks for cancellation request and raises exception if requested."""
        if self.cancel_event.is_set():
            raise DownloadCancelled(f"Info fetch cancelled {stage}.")

    def _fetch_info_core(self):
        """المنطق الأساسي لجلب المعلومات باستخدام yt-dlp."""
        """Core logic for fetching info using yt-dlp."""
        self.status_callback("Fetching information...")
        self.progress_callback(0) # إظهار بداية التقدم
        self._check_cancel("before starting fetch")

        # خيارات yt-dlp لجلب المعلومات فقط
        ydl_opts = {
            'quiet': True,                 # منع المخرجات النصية من yt-dlp
            'nocheckcertificate': True,    # تجاهل أخطاء شهادة SSL (مفيد لبعض المواقع)
            'extract_flat': 'in_playlist', # جلب سريع لعناوين القائمة بدون تحليل كل فيديو
            'playlistend': 500,            # حد أقصى لعدد عناصر القائمة (لتجنب قوائم ضخمة جدًا)
            'ignoreerrors': True,          # تجاهل الأخطاء الفردية في عناصر القائمة
            'forcejson': True,             # ضمان إخراج JSON حتى مع الأخطاء
            'skip_download': True,         # التأكيد على عدم التحميل
            # 'dump_single_json': True,      # يمكن استخدامه بدل extract_info للحصول على JSON مباشرة
        }

        info_dict = None
        try:
            # استخدام context manager لضمان تنظيف الموارد
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._check_cancel("before calling extract_info")
                # استدعاء extract_info لجلب البيانات الوصفية
                # ملاحظة: هذا قد يكون بطيئًا للقوائم الكبيرة جدًا رغم extract_flat
                info_dict = ydl.extract_info(self.url, download=False)
                self._check_cancel("after calling extract_info")

        except yt_dlp.utils.DownloadError as e:
            # التعامل مع أخطاء yt-dlp المحددة
            error_message = str(e)
            # محاولة تنظيف رسالة الخطأ قليلًا
            if 'ERROR:' in error_message:
                 error_message = error_message.split('ERROR:')[-1].strip()
            print(f"InfoFetcher yt-dlp DownloadError: {e}")
            # استدعاء كول باك الخطأ مع الرسالة المنظفة
            self.error_callback(error_message)
            return # الخروج من الدالة لأن الجلب فشل

        except DownloadCancelled:
             # إعادة إطلاق الاستثناء ليتم التقاطه في run
             raise

        except Exception as e:
            # التعامل مع أي أخطاء غير متوقعة أخرى
            print(f"InfoFetcher Unexpected Error: {e}")
            traceback.print_exc() # طباعة التتبع الكامل للخطأ للمساعدة في التشخيص
            self.error_callback(f"An unexpected error occurred: {type(e).__name__}")
            return # الخروج من الدالة

        # التحقق من أننا حصلنا على نتيجة صالحة
        if info_dict:
            # تنظيف قائمة التشغيل من الإدخالات الفارغة المحتملة بسبب ignoreerrors
            if 'entries' in info_dict and isinstance(info_dict['entries'], list):
                 info_dict['entries'] = [entry for entry in info_dict['entries'] if entry]
                 if not info_dict['entries']: # إذا أصبحت القائمة فارغة بعد التنظيف
                      print("InfoFetcher: Playlist found but contained no valid entries.")
                      self.error_callback("Playlist found but contained no valid entries.")
                      return

            # استدعاء كول باك النجاح مع القاموس الناتج
            self.status_callback("Information fetched successfully.")
            self.success_callback(info_dict)
        else:
            # لم يتم إرجاع أي بيانات (قد يحدث مع dump_single_json والفشل)
            print("InfoFetcher: No information dictionary returned by yt-dlp.")
            self.error_callback("Could not retrieve information (no data returned).")


    def run(self):
        """تنفذ عملية جلب المعلومات وتدير الاستثناءات النهائية والكول باك."""
        """Executes the info fetching process and handles final exceptions and callbacks."""
        try:
            self._fetch_info_core()
        except DownloadCancelled as e:
            # تم إلغاء العملية بواسطة المستخدم
            self.status_callback(str(e))
            print(e)
        except Exception as e:
            # أي خطأ غير متوقع لم يتم التقاطه في _fetch_info_core (نادر)
            print(f"InfoFetcher FATAL UNEXPECTED Error in run: {e}")
            traceback.print_exc()
            # التأكد من استدعاء كول باك الخطأ إذا لم يكن قد استدعي بالفعل
            self.error_callback(f"A critical unexpected error occurred: {type(e).__name__}")
        finally:
            # استدعاء finished_callback دائمًا في النهاية، بغض النظر عن النتيجة
            print("InfoFetcher: Reached finally block, calling finished_callback.")
            self.finished_callback()


# --- كلاس لتنفيذ التحميل ---
class Downloader:
    """كلاس مسؤول عن عملية التحميل الفعلية باستخدام yt-dlp."""
    """Class responsible for the actual download process using yt-dlp."""

    def __init__(self, url, save_path, format_choice, quality_format_id, is_playlist,
                 playlist_items, playlist_items_count, ffmpeg_path, cancel_event,
                 status_callback, progress_callback, finished_callback):
        self.url = url
        self.save_path = save_path
        self.format_choice = format_choice
        self.quality_format_id = quality_format_id
        self.is_playlist = is_playlist
        self.playlist_items = playlist_items
        self.playlist_items_count = playlist_items_count
        self.ffmpeg_path = ffmpeg_path
        self.cancel_event = cancel_event
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

        # متغيرات لتتبع حالة التحميل والتنظيف
        self.last_downloaded_info = None # لتخزين معلومات آخر ملف للتحقق النهائي
        self.final_known_path = None     # لتخزين المسار النهائي المعروف الذي أبلغ عنه الهوك
        self.current_playlist_item_dl_index = 0 # عداد لعناصر القائمة التي تم البدء في تحميلها/معالجتها
        self._cleaned_up_path = None     # لتخزين المسار بعد التنظيف لتجنب إعادة التنظيف

    def _check_cancel(self, stage=""):
        """يتحقق من طلب الإلغاء ويطلق استثناء."""
        """Checks for cancellation request and raises exception."""
        if self.cancel_event.is_set():
            raise DownloadCancelled(f"Download cancelled {stage}.")

    def _clean_filename(self, filename):
        """ينظف اسم الملف من الرموز غير الصالحة أو غير المرغوبة لنظام الملفات."""
        """Cleans the filename from invalid or unwanted characters for the filesystem."""
        if not filename: return filename
        # إزالة / \ : * ? " < > | وغيرها من الرموز غير المسموح بها في ويندوز
        # واستبدال بعضها ببدائل مقبولة (مثل ':' بـ ' - ')
        cleaned = re.sub(r'[\\/*?:"<>|]', '', filename)
        cleaned = cleaned.replace(':', ' -') # استبدال النقطتين بمسافة وشرطة
        # استبدال المسافات المتعددة بمسافة واحدة وإزالة المسافات البادئة/اللاحقة
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        # التأكد من عدم انتهاء الاسم بنقطة أو مسافة (مشكلة في ويندوز)
        cleaned = cleaned.rstrip('. ')
        # التأكد من أن الاسم ليس فارغًا بعد التنظيف
        if not cleaned: return "downloaded_file" # اسم افتراضي إذا كان فارغًا
        return cleaned

    def _my_hook(self, d):
        """Hook لتقدم التحميل وتخزين المعلومات النهائية."""
        """Hook for download progress and storing final information."""
        # التحقق من الإلغاء في بداية الهوك
        try:
            self._check_cancel("during progress hook")
        except DownloadCancelled as e:
            raise yt_dlp.utils.DownloadCancelled(str(e)) # تحويله لخطأ يفهمه yt-dlp لإيقاف التحميل

        status = d.get('status')

        if status == 'finished':
            # اكتمل تحميل الملف (أو مرحلة منه، مثل الفيديو قبل الدمج)
            filepath = d.get('info_dict', {}).get('filepath') or d.get('filename')
            if filepath:
                # --- تخزين المسار المبلغ عنه ---
                # هذا المسار قد يكون للملف المؤقت أو النهائي (بعد الدمج إذا حدث)
                self.final_known_path = filepath
                # تخزين معلومات الملف الحالية
                self.last_downloaded_info = d.get('info_dict', self.last_downloaded_info)
                print(f"Hook 'finished': Path reported '{filepath}'.")

                # تحديث الحالة والتقدم
                base_filename = os.path.basename(filepath)
                # فحص إذا كان اسم الملف مؤقتًا (غالبًا لا يحتوي على الامتداد النهائي)
                is_likely_temp = not any(base_filename.lower().endswith(ext) for ext in ['.mp4', '.mp3', '.mkv', '.webm'])
                if is_likely_temp:
                     status_msg = f"Processing: {self._clean_filename(base_filename)}..."
                else:
                     status_msg = f"Finished: {self._clean_filename(base_filename)}" # استخدام اسم نظيف للعرض

                self.status_callback(status_msg)
                self.progress_callback(1.0) # اكتمل تحميل هذا الملف

                # تحديث عداد القائمة هنا فقط عند انتهاء معالجة عنصر نهائي
                # (التحقق من الامتداد يساعد على تجنب العد المزدوج)
                if self.is_playlist and not is_likely_temp:
                    # التأكد من أن هذا هو الانتهاء الفعلي للعنصر وليس ملف مؤقت
                    # (هذا تقديري وقد يحتاج لتعديل بناءً على سلوك yt-dlp الدقيق)
                    self.current_playlist_item_dl_index += 1
                    print(f"Playlist item index counter incremented to: {self.current_playlist_item_dl_index}")

            else:
                # لم يتم العثور على مسار ملف في بيانات الهوك
                print("Hook 'finished' but no filepath found in hook data.")
                self.status_callback("Processing finished (unknown file path).")
                self.progress_callback(1.0)

        elif status == 'downloading':
            # تحديث شريط التقدم ورسالة الحالة أثناء التحميل
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded_bytes = d.get('downloaded_bytes')

            if total_bytes and downloaded_bytes is not None:
                 progress = downloaded_bytes / total_bytes
                 self.progress_callback(max(0.0, min(1.0, progress))) # ضمان التقدم بين 0 و 1

                 # بناء رسالة الحالة
                 status_prefix = ""
                 if self.is_playlist and self.playlist_items_count > 0:
                      # استخدام العداد الداخلي لأنه أضمن من الفهرس في الهوك أحيانًا
                      display_index = self.current_playlist_item_dl_index + 1 # +1 لأن العداد يبدأ من 0
                      status_prefix = f"Item {display_index}/{self.playlist_items_count} - "

                 percent_str = d.get('_percent_str', 'N/A').strip()
                 downloaded_str = d.get('_downloaded_bytes_str', 'N/A')
                 total_bytes_str = d.get('_total_bytes_str', 'N/A')
                 speed_str = d.get('_speed_str', 'N/A')
                 eta_str = d.get('_eta_str', 'N/A')

                 status_msg = f"{status_prefix}Downloading: {percent_str} ({downloaded_str}/{total_bytes_str}) at {speed_str}, ETA: {eta_str}"
                 self.status_callback(status_msg)

            else:
                 # حالة تحميل غير محددة (مثل بداية الاتصال)
                 self.status_callback(f"Status: {d.get('status', 'N/A')}...")

        elif status == 'error':
            # حدث خطأ أثناء التحميل أبلغ عنه yt-dlp
            self.status_callback("Error during download process reported by yt-dlp.")
            print(f"yt-dlp hook reported error: {d.get('error', 'Unknown yt-dlp error')}")
            # يمكن إطلاق استثناء هنا لإيقاف العملية فورًا إذا لزم الأمر
            # raise yt_dlp.utils.DownloadError("yt-dlp hook reported an error.")

    def _build_format_string(self):
        """يبني سلسلة اختيار الصيغة بناءً على خيارات المستخدم."""
        """Builds the format selection string based on user options."""
        format_choice_lower = self.format_choice.lower()
        output_ext = "mp4" # الامتداد الافتراضي
        postprocessors = []
        final_format_string = None

        # 1. التحقق من جودة الفيديو المفرد المحددة (لها الأولوية إذا لم تكن قائمة)
        if not self.is_playlist and self.quality_format_id:
            final_format_string = self.quality_format_id
            # محاولة تحديد الامتداد من الهوك (أو تركه لـ yt-dlp) - هذا معقد
            # قد نحتاج لجلب معلومات الصيغة المحددة لمعرفة امتدادها
            # للتبسيط، نفترض mp4 أو نتركه لـ yt-dlp عبر %(ext)s لاحقًا
            print(f"Using specific quality format ID: {self.quality_format_id}")
            # إذا كان المستخدم يريد MP3 بالرغم من اختيار جودة محددة (غير منطقي لكن ممكن)
            if "audio (mp3)" in format_choice_lower:
                output_ext = "mp3" # نغير الامتداد و نضيف معالج MP3
                if self.ffmpeg_path:
                     postprocessors.append({'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'})
                else: print("Warning: MP3 requested but FFmpeg not found.")

        # 2. إذا لم يتم تحديد جودة مفردة، أو كانت قائمة تشغيل، نستخدم الخيار العام
        else:
            if "audio (mp3)" in format_choice_lower:
                # طلب صوت MP3
                final_format_string = "bestaudio/best" # اختيار أفضل صوت متاح
                output_ext = "mp3"
                if self.ffmpeg_path:
                     postprocessors.append({'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'})
                else:
                    print("Warning: MP3 requested but FFmpeg not found. Format might not be MP3.")
                    output_ext = None # السماح لـ yt-dlp بتحديد الامتداد

            elif self.is_playlist:
                 # فيديو قائمة التشغيل: تطبيق حد 720p الافتراضي (كما في المرحلة 2)
                 final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
                 output_ext = "mp4"
                 print("Using default playlist format (max 720p MP4)")

            else:
                 # فيديو مفرد، باستخدام الخيار العام من القائمة المنسدلة
                 if "<= 720p" in format_choice_lower:
                     final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
                     print("Using general format: max 720p MP4")
                 elif "<= 480p" in format_choice_lower:
                     final_format_string = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480][ext=mp4]/best[height<=480]"
                     print("Using general format: max 480p MP4")
                 elif "<= 360p" in format_choice_lower:
                     final_format_string = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360][ext=mp4]/best[height<=360]"
                     print("Using general format: max 360p MP4")
                 else: # الخيار الافتراضي "Best Quality MP4 (<= 1080p+)"
                     final_format_string = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
                     print("Using general format: best available MP4 (1080p+)")
                 output_ext = "mp4"

        return final_format_string, output_ext, postprocessors


    def _download_core(self):
        """المنطق الأساسي لعملية التحميل وإعداد خيارات yt-dlp."""
        """Core logic for the download process and setting up yt-dlp options."""
        # إعادة تعيين المتغيرات لكل عملية تحميل
        self.last_downloaded_info = None
        self.final_known_path = None
        self.current_playlist_item_dl_index = 0
        self._cleaned_up_path = None # مسح المسار المنظف سابقًا
        self._check_cancel("before starting download")

        # بناء قالب اسم الملف
        # استخدام اسم نظيف للعنوان مباشرة في القالب
        base_tmpl_name = "%(playlist_index)s. %(title)s" if self.is_playlist else "%(title)s"
        output_template_base = Path(self.save_path) / base_tmpl_name # استخدام pathlib

        # بناء سلسلة الصيغة والامتداد ومعالجات ما بعد التحميل
        final_format_string, output_ext, core_postprocessors = self._build_format_string()

        # تحديد قالب الإخراج النهائي مع الامتداد
        if output_ext:
            final_outtmpl = str(output_template_base.with_suffix(f".{output_ext}"))
        else:
            # إذا لم نتمكن من تحديد الامتداد (مثل طلب MP3 بدون ffmpeg)
            final_outtmpl = str(output_template_base.with_suffix(".%(ext)s")) # نترك yt-dlp يحدد الامتداد

        # إعداد خيارات yt-dlp
        ydl_opts = {
            'progress_hooks': [self._my_hook],
            'outtmpl': final_outtmpl,
            'nocheckcertificate': True,
            'ignoreerrors': self.is_playlist, # تجاهل الأخطاء في عناصر القائمة للمتابعة
            'merge_output_format': 'mp4',     # تفضيل الدمج في MP4 إذا أمكن
            # 'writethumbnail': True, # إلغاء التعليق إذا أردت تحميل الصورة المصغرة
            'postprocessors': core_postprocessors, # إضافة معالجات MP3 إذا كانت موجودة
             # --- تعديل مهم: تعطيل restrictfilenames للسماح بالمسافات ---
            'restrictfilenames': False, # يسمح بالمسافات والأحرف الأخرى المدعومة في ويندوز
            # -------------------------------------------------------------
        }

        # إضافة مسار ffmpeg إذا تم العثور عليه
        if self.ffmpeg_path:
            ydl_opts['ffmpeg_location'] = self.ffmpeg_path
        elif core_postprocessors: # إذا احتجنا ffmpeg ولم نجده
             self.status_callback("Warning: FFmpeg needed but not found. Conversion/Merge might fail.")

        # إعدادات خاصة بقائمة التشغيل
        if self.is_playlist:
            ydl_opts['noplaylist'] = False # نريد معالجة القائمة
            if self.playlist_items:
                ydl_opts['playlist_items'] = self.playlist_items # تحديد العناصر المطلوبة
        else:
            ydl_opts['noplaylist'] = True # معالجة الفيديو كرابط مفرد

        # إضافة سلسلة الصيغة إذا تم تحديدها
        if final_format_string:
            ydl_opts['format'] = final_format_string
        elif 'format' in ydl_opts:
             del ydl_opts['format'] # إزالة المفتاح إذا كانت القيمة None

        # طباعة الخيارات للتشخيص (اختياري)
        # print("yt-dlp options:", ydl_opts)

        # بدء عملية التحميل الفعلية
        self.status_callback("Starting download...")
        self.progress_callback(0)
        self._check_cancel("right before calling ydl.download()")

        download_successful = False
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            # إذا وصل هنا بدون استثناءات من yt-dlp، نعتبره نجاحًا مبدئيًا
            download_successful = True
            self._check_cancel("immediately after ydl.download() finished")

        except yt_dlp.utils.DownloadCancelled as e:
             # تم الإلغاء بواسطة الهوك أو الفحص المباشر
             raise DownloadCancelled(str(e)) # إعادة إطلاق استثناءنا الخاص
        except yt_dlp.utils.DownloadError as dl_err:
             # خطأ محدد من yt-dlp أثناء التحميل
             error_message = str(dl_err).split('ERROR:')[-1].strip()
             print(f"Downloader yt-dlp DownloadError: {dl_err}")
             self.status_callback(f"Download Error: {error_message}")
             # لا نرفع استثناء هنا، سنعتمد على download_successful=False
        except Exception as e:
             # أخطاء غير متوقعة أخرى
             self._log_unexpected_error(e, "during yt-dlp download execution")
             # لا نرفع استثناء هنا أيضًا

        # إعادة التحقق من الإلغاء مرة أخرى بعد انتهاء كتلة التحميل
        self._check_cancel("after download block completion")

        # إذا لم يكن التحميل ناجحًا، لا داعي لمحاولة التنظيف
        if not download_successful:
             print("Download process reported errors. Skipping final cleanup.")
             return # الخروج من الدالة

        # --- التنظيف النهائي بعد التحميل الناجح ---
        # هذا يتم استدعاؤه فقط إذا لم تحدث أخطاء DownloadError أو إلغاء
        # الهدف الرئيسي هو التأكد من أن اسم الملف النهائي نظيف
        try:
            self._cleanup_final_file()
        except Exception as e:
             self._log_unexpected_error(e, "during final file cleanup")
             self.status_callback("Warning: Download complete, but cleanup failed.")


    def _cleanup_final_file(self):
        """يحاول تنظيف اسم الملف النهائي المعروف بعد انتهاء التحميل."""
        """Attempts to clean the name of the final known file after download."""
        if self._cleaned_up_path: # إذا تم التنظيف بالفعل لهذا الملف
            print(f"Cleanup skipped: Already cleaned path '{self._cleaned_up_path}'")
            return

        print("Attempting final file cleanup...")
        if not self.final_known_path:
            print("Cleanup skipped: No final file path was reported by hooks.")
            # قد تكون هناك حالة لم يبلغ الهوك عن مسار (نادر)
            self.status_callback("Warning: Download finished, but final file path is unknown.")
            return

        expected_final_path_obj = Path(self.final_known_path)
        print(f"Cleanup: Checking final path '{expected_final_path_obj}'")

        # التأكد من وجود الملف قبل محاولة إعادة تسميته
        # إضافة انتظار قصير جدًا للسماح لنظام الملفات باللحاق (اختياري وموضع نقاش)
        time.sleep(0.1)
        if not expected_final_path_obj.exists():
            print(f"Cleanup Error: Expected final file '{expected_final_path_obj}' not found. Merge/Processing might have failed or path is incorrect.")
            self.status_callback(f"Error: Processing completed but final file '{expected_final_path_obj.name}' is missing.")
            return

        # الملف موجود، نقوم بتنظيف الاسم
        current_basename = expected_final_path_obj.name
        cleaned_basename = self._clean_filename(current_basename)
        new_final_filepath_obj = expected_final_path_obj.with_name(cleaned_basename)

        final_message = f"Download complete: {cleaned_basename}" # الرسالة الافتراضية بعد التنظيف

        # إعادة التسمية فقط إذا كان الاسم الجديد مختلفًا عن الحالي
        if new_final_filepath_obj != expected_final_path_obj:
            print(f"Attempting rename: '{current_basename}' -> '{cleaned_basename}'")
            try:
                # التأكد مرة أخرى من وجود الملف قبل إعادة التسمية مباشرة
                if expected_final_path_obj.exists():
                    expected_final_path_obj.rename(new_final_filepath_obj)
                    print(f"Rename successful: '{new_final_filepath_obj}'")
                    self._cleaned_up_path = str(new_final_filepath_obj) # تخزين المسار المنظف
                else:
                    print(f"File disappeared before rename: {expected_final_path_obj}")
                    final_message = f"Warning: Download ok, but file missing before rename ({current_basename})"
                    self._cleaned_up_path = None # لم يتم التنظيف بنجاح

            except OSError as e:
                print(f"Error during final rename for '{current_basename}': {e}")
                final_message = f"Download complete (rename failed): {current_basename}"
                self._cleaned_up_path = str(expected_final_path_obj) # اعتبار المسار القديم هو النهائي
        else:
            # الاسم كان نظيفًا بالفعل، لا حاجة لإعادة التسمية
            print("Filename already clean. No rename needed.")
            self._cleaned_up_path = str(expected_final_path_obj) # تخزين المسار الحالي

        # تحديث رسالة الحالة النهائية (فقط إذا لم يتم الإلغاء أو حدوث خطأ تحميل)
        self.status_callback(final_message)


    def run(self):
        """تنفذ عملية التحميل الفعلية وتدير الاستثناءات والكول باك النهائي."""
        """Executes the actual download process, managing exceptions and final callback."""
        download_error_occurred = False
        self._cleaned_up_path = None # إعادة تعيين للمحاولة الجديدة

        try:
            self._download_core()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
            download_error_occurred = True # اعتبار الإلغاء كخطأ يمنع رسالة النجاح
        except Exception as e:
            # هذا يلتقط أي استثناء غير متوقع لم يتم التعامل معه داخل _download_core
            self._log_unexpected_error(e, "in main run loop")
            download_error_occurred = True
        finally:
            # استدعاء finished_callback دائمًا في النهاية
            print("Downloader: Reached finally block, calling finished_callback.")
            self.finished_callback()
            # لا تطبع رسالة نجاح عامة هنا، الهوك أو التنظيف قام بذلك

    def _log_unexpected_error(self, e, context=""):
        """يسجل الأخطاء غير المتوقعة ويحدث الحالة."""
        """Logs unexpected errors and updates the status."""
        print(f"--- UNEXPECTED ERROR ({context}) ---")
        traceback.print_exc()
        print("------------------------------------")
        self.status_callback(f"Unexpected Error ({type(e).__name__})! Check logs.")
        print(f"Unexpected Error during download ({context}): {e}")