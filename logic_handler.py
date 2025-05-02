# -- ملف يحتوي على الكلاس المسؤول عن منطق العمل الرئيسي (التفاعل مع yt-dlp و FFmpeg) --

import os
import yt_dlp
import threading
import sys
import time
from pathlib import Path
from exceptions import DownloadCancelled # استيراد الاستثناء المخصص

# الكلاس الرئيسي لمنطق التحميل والمعلومات
class LogicHandler:
    def __init__(self, status_callback, progress_callback, finished_callback, info_success_callback, info_error_callback):
        """
        تهيئة معالج المنطق.
        Args:
            status_callback: دالة لتحديث نص الحالة في الواجهة.
            progress_callback: دالة لتحديث شريط التقدم في الواجهة.
            finished_callback: دالة تُستدعى عند انتهاء المهمة (نجاح، فشل، إلغاء).
            info_success_callback: دالة تُستدعى عند جلب المعلومات بنجاح.
            info_error_callback: دالة تُستدعى عند فشل جلب المعلومات.
        """
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.info_success_callback = info_success_callback
        self.info_error_callback = info_error_callback

        self.ffmpeg_path = self._find_ffmpeg() # البحث عن مسار ffmpeg
        self.cancel_event = threading.Event() # حدث للتحكم في الإلغاء
        self.current_thread = None # لتتبع الخيط (thread) النشط حاليًا

    def _find_ffmpeg(self):
        """يحاول العثور على ملف ffmpeg.exe التنفيذي."""
        # تحديد المسار المتوقع لـ ffmpeg المرفق مع التطبيق
        bundled_path = Path(sys.argv[0]).parent / "ffmpeg_bin" / "ffmpeg.exe"
        if bundled_path.is_file():
            print(f"Found bundled ffmpeg: {bundled_path}")
            return str(bundled_path)
        print("Warning: Bundled ffmpeg not found. yt-dlp might rely on system PATH or fail some operations.")
        return None # لم يتم العثور عليه

    def _my_hook(self, d):
        """
        دالة خطاف التقدم (progress hook) لمكتبة yt-dlp. تتحقق من طلب الإلغاء.
        """
        # التحقق بشكل متكرر من إشارة الإلغاء
        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled by user.") # إطلاق الاستثناء المخصص

        # تحليل حالة التقدم من القاموس 'd'
        if d['status'] == 'downloading':
            filename = d.get('filename', 'N/A')
            total_bytes_str = d.get('_total_bytes_str', 'N/A')
            downloaded_bytes = d.get('downloaded_bytes')
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            speed_str = d.get('_speed_str', 'N/A')
            eta_str = d.get('_eta_str', 'N/A')
            percent_str = d.get('_percent_str', 'N/A').strip()

            # تحديث شريط التقدم والحالة في الواجهة
            if total_bytes and downloaded_bytes:
                progress = downloaded_bytes / total_bytes
                self.progress_callback(progress)
                status_msg = f"Downloading: {percent_str} ({d.get('_downloaded_bytes_str', 'N/A')}/{total_bytes_str}) at {speed_str}, ETA: {eta_str}"
                self.status_callback(status_msg)
            else:
                 self.status_callback(f"Status: {d['status']} - {filename}")

        elif d['status'] == 'finished':
            # اكتمل تحميل الملف، قد تبدأ المعالجة اللاحقة
            filename = d.get('filename', 'N/A')
            total_bytes_str = d.get('_total_bytes_str', 'N/A')
            self.status_callback(f"Finished downloading '{os.path.basename(filename)}' ({total_bytes_str}). Post-processing...")
            self.progress_callback(1.0) # إظهار اكتمال التقدم
        elif d['status'] == 'error':
            # حدث خطأ أثناء عملية الخطاف
            self.status_callback("Error during download process.")
            print(f"yt-dlp hook error: {d}") # طباعة تفاصيل الخطأ في الطرفية

    def _execute_info_fetch(self, url):
        """تجلب معلومات الفيديو/القائمة في خيط منفصل."""
        try:
            self.status_callback("Fetching information...")
            self.progress_callback(0)
            # خيارات yt-dlp لجلب المعلومات فقط
            ydl_opts = {
                'quiet': True,
                'nocheckcertificate': True,
                'extract_flat': 'in_playlist', # أسرع للقوائم
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if self.cancel_event.is_set(): raise DownloadCancelled("Info fetch cancelled.")
                # استدعاء لجلب المعلومات (بدون تحميل)
                info_dict = ydl.extract_info(url, download=False)

            if self.cancel_event.is_set(): raise DownloadCancelled("Info fetch cancelled.")

            # إرسال المعلومات للواجهة عبر الكول باك
            self.status_callback("Information fetched successfully.")
            self.info_success_callback(info_dict)

        except DownloadCancelled as e:
             # تم إلغاء العملية بواسطة المستخدم
             self.status_callback(str(e))
             print(str(e))
        except yt_dlp.utils.DownloadError as e:
             # خطأ محدد من yt-dlp (مثل رابط غير صالح)
            error_message = str(e).split('ERROR:')[-1].strip()
            self.status_callback(f"Info Error: {error_message}")
            self.info_error_callback(error_message) # إبلاغ الواجهة بالخطأ
            print(f"yt-dlp DownloadError during info fetch: {e}")
        except Exception as e:
             # أي خطأ آخر غير متوقع
            self.status_callback(f"An unexpected error occurred during info fetch: {type(e).__name__}")
            self.info_error_callback(f"Unexpected error: {e}")
            print(f"Unexpected Error during info fetch: {e}")
        finally:
            # دائمًا استدعاء finished_callback لإعلام الواجهة بانتهاء المهمة
            self.finished_callback()
            self.current_thread = None # تحرير مؤشر الخيط

    def start_info_fetch(self, url):
        """تبدأ عملية جلب المعلومات في خيط جديد."""
        if not url:
            self.status_callback("Error: Please enter a URL.")
            self.info_error_callback("URL is empty.")
            self.finished_callback()
            return
        # التأكد من عدم وجود عملية أخرى جارية
        if self.current_thread and self.current_thread.is_alive():
             self.status_callback("Error: Another operation is already in progress.")
             # لا تستدعي finished_callback هنا لأن المهمة لم تبدأ ولم تنتهِ
             return

        self.cancel_event.clear() # إعادة تعيين إشارة الإلغاء
        # إنشاء وتشغيل الخيط
        self.current_thread = threading.Thread(
            target=self._execute_info_fetch,
            args=(url,),
            daemon=True
        )
        self.current_thread.start()

    def _execute_download(self, url, save_path, format_choice, quality_format_id, is_playlist, playlist_items):
        """تنفذ عملية التحميل الفعلية في خيط منفصل."""
        try:
            # إعداد خيارات yt-dlp الأساسية للتحميل
            ydl_opts = {
                'progress_hooks': [self._my_hook], # استخدام خطاف التقدم الخاص بنا
                'outtmpl': os.path.join(save_path, '%(title)s [%(id)s].%(ext)s'), # قالب اسم الملف
                'nocheckcertificate': True,
                'ignoreerrors': is_playlist, # تجاهل الأخطاء في القائمة للمتابعة
            }

            # --- تحديد مسار FFmpeg ---
            if self.ffmpeg_path:
                ydl_opts['ffmpeg_location'] = self.ffmpeg_path
            else:
                 if format_choice == 'Audio (mp3)' or quality_format_id:
                     self.status_callback("Warning: FFmpeg not found. MP3 or merging might fail.")

            # --- التعامل مع خيارات قائمة التشغيل ---
            if is_playlist:
                ydl_opts['noplaylist'] = False
                if playlist_items: # إذا تم تحديد عناصر معينة
                    ydl_opts['playlist_items'] = playlist_items
            else: # فيديو مفرد أو قائمة كمفرد
                 ydl_opts['noplaylist'] = True

            # --- منطق اختيار الصيغة والجودة ---
            postprocessors = [] # قائمة للمعالجات اللاحقة (مثل تحويل mp3)
            if quality_format_id:
                # تم اختيار جودة محددة من الواجهة
                ydl_opts['format'] = quality_format_id
                # إضافة تحويل MP3 إذا كان مطلوبًا حتى مع اختيار جودة محددة
                if format_choice == 'Audio (mp3)':
                     postprocessors.append({
                        'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',
                     })
                     ydl_opts['outtmpl'] = os.path.join(save_path, '%(title)s [%(id)s].mp3')
            else:
                # تم اختيار الصيغة العامة (mp4 best أو mp3)
                if format_choice == 'Audio (mp3)':
                    ydl_opts['format'] = 'bestaudio/best'
                    postprocessors.append({
                        'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192',
                    })
                    ydl_opts['outtmpl'] = os.path.join(save_path, '%(title)s [%(id)s].mp3')
                elif format_choice == 'Video (mp4, Best)':
                    ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best'
                    # إضافة معالج لضمان حاوية MP4 (مهم عند الدمج)
                    postprocessors.append({
                         'key': 'FFmpegVideoConvertor', 'preferedformat': 'mp4',
                    })
                    ydl_opts['outtmpl'] = os.path.join(save_path, '%(title)s [%(id)s].mp4')
                else:
                    ydl_opts['format'] = 'best' # اختيار أفضل جودة كخيار احتياطي

            # إضافة قائمة المعالجات اللاحقة للخيارات إذا لم تكن فارغة
            if postprocessors:
                ydl_opts['postprocessors'] = postprocessors

            # البدء الفعلي للتحميل
            self.status_callback("Starting download...")
            self.progress_callback(0)

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                if self.cancel_event.is_set(): raise DownloadCancelled("Download cancelled before starting.")
                # استدعاء دالة التحميل
                ydl.download([url])

            if self.cancel_event.is_set(): raise DownloadCancelled("Download cancelled.")

            # اكتمل التحميل بنجاح
            self.status_callback("Download and processing complete!")

        except DownloadCancelled as e:
             self.status_callback(str(e))
             print(str(e))
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split('ERROR:')[-1].strip()
            self.status_callback(f"Download Error: {error_message}")
            print(f"yt-dlp DownloadError: {e}")
        except Exception as e:
            self.status_callback(f"An unexpected error occurred during download: {type(e).__name__}")
            print(f"Unexpected Error during download: {e}")
        finally:
            # إعلام الواجهة بانتهاء المهمة
            self.finished_callback()
            self.current_thread = None

    def start_download(self, url, save_path, format_choice, quality_format_id, is_playlist, playlist_items):
        """تبدأ عملية التحميل في خيط جديد."""
        if not url or not save_path:
            self.status_callback("Error: URL and Save Path are required.")
            self.finished_callback()
            return
        # التأكد من عدم وجود عملية أخرى جارية
        if self.current_thread and self.current_thread.is_alive():
             self.status_callback("Error: Another operation is already in progress.")
             # لا تستدعي finished_callback هنا
             return

        self.cancel_event.clear() # إعادة تعيين إشارة الإلغاء
        # إنشاء وتشغيل الخيط
        self.current_thread = threading.Thread(
            target=self._execute_download,
            args=(url, save_path, format_choice, quality_format_id, is_playlist, playlist_items),
            daemon=True
        )
        self.current_thread.start()

    def cancel_operation(self):
        """ترسل إشارة إلغاء للعملية الجارية حاليًا."""
        if self.current_thread and self.current_thread.is_alive():
            self.status_callback("Cancellation requested...")
            self.cancel_event.set() # تفعيل إشارة الإلغاء
        else:
            self.status_callback("No operation running to cancel.")