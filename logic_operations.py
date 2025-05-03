# -- ملف يحتوي على الكلاسات المسؤولة عن التفاعل المباشر مع yt-dlp --
# Purpose: Contains classes that perform the actual work of interacting with yt-dlp.

import os
import yt_dlp
import sys
from pathlib import Path
from exceptions import DownloadCancelled
import re
import traceback
import time


# --- دالة find_ffmpeg ---
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
    print("Warning: Bundled ffmpeg not found.")
    return None


# --- START: Corrected InfoFetcher Class ---
class InfoFetcher:
    """كلاس مسؤول عن عملية جلب معلومات الفيديو/القائمة."""

    def __init__(
        self,
        url,
        cancel_event,
        success_callback,
        error_callback,
        status_callback,
        progress_callback,
        finished_callback,
    ):
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
            "quiet": True,
            "nocheckcertificate": True,
            "extract_flat": "in_playlist",
            "playlistend": 500,
            "ignoreerrors": True,
        }
        # استخدام المسافات البادئة الصحيحة Correct indentation
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if self.cancel_event.is_set():
                raise DownloadCancelled("Info fetch cancelled before starting.")
            # يجب أن يكون استدعاء extract_info داخل كتلة with
            info_dict = ydl.extract_info(self.url, download=False)

        # التحقق من الإلغاء بعد الخروج من with Check cancellation after exiting with
        if self.cancel_event.is_set():
            raise DownloadCancelled("Info fetch cancelled after fetching.")

        self.status_callback("Information fetched successfully.")
        self.success_callback(info_dict)

    def run(self):
        """تنفذ عملية جلب المعلومات."""
        # استخدام المسافات البادئة الصحيحة Correct indentation
        try:
            self._fetch_info_core()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split("ERROR:")[-1].strip()
            self.status_callback(f"Info Error: {error_message}")
            self.error_callback(
                error_message
            )  # لا ننسى استدعاء كول باك الخطأ Don't forget error callback
            print(f"yt-dlp DownloadError info fetch: {e}")
        except Exception as e:
            self.status_callback(f"Unexpected info fetch error: {type(e).__name__}")
            self.error_callback(
                f"Unexpected error: {e}"
            )  # لا ننسى استدعاء كول باك الخطأ Don't forget error callback
            print(f"Unexpected Error info fetch: {e}")
        finally:
            self.finished_callback()


# --- END: Corrected InfoFetcher Class ---


# --- كلاس لتنفيذ التحميل ---
class Downloader:
    """كلاس مسؤول عن عملية التحميل الفعلية باستخدام yt-dlp."""

    def __init__(
        self,
        url,
        save_path,
        format_choice,
        quality_format_id,
        is_playlist,
        playlist_items,
        playlist_items_count,
        ffmpeg_path,
        cancel_event,
        status_callback,
        progress_callback,
        finished_callback,
    ):
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
        # self.expected_final_path_template = None # لم نعد نعتمد عليه بهذه الطريقة
        self.last_downloaded_info = None  # لتخزين معلومات آخر ملف للتحقق النهائي
        self.final_known_path = None  # لتخزين المسار النهائي المعروف
        self.current_playlist_item_dl_index = 0

    def _calculate_and_update_progress(self, downloaded_bytes, total_bytes):
        """يحسب التقدم ويستدعي الكول باك الخاص به."""
        if total_bytes > 0 and downloaded_bytes is not None:
            progress = downloaded_bytes / total_bytes
            progress = max(0.0, min(1.0, progress))
            self.progress_callback(progress)
            return progress
        return None

    def _process_download_progress(self, d):
        """تحلل بيانات الهوك وتحدث الواجهة."""
        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded_bytes = d.get("downloaded_bytes")
        self._calculate_and_update_progress(downloaded_bytes, total_bytes)
        total_bytes_str = d.get("_total_bytes_str", "N/A")
        speed_str = d.get("_speed_str", "N/A")
        eta_str = d.get("_eta_str", "N/A")
        percent_str = d.get("_percent_str", "N/A").strip()
        downloaded_str = d.get("_downloaded_bytes_str", "N/A")
        filename = d.get("filename", "N/A")
        item_title = d.get("info_dict", {}).get("title", os.path.basename(filename))
        item_title_cleaned = re.sub(r"\.[a-zA-Z0-9]+$", "", item_title)
        if total_bytes and downloaded_bytes is not None:
            status_prefix = ""
            if self.is_playlist and self.playlist_items_count > 0:
                hook_playlist_index = d.get("info_dict", {}).get("playlist_index")
                # استخدام العداد الداخلي كـ fallback إذا لم يتوفر الفهرس
                display_index = (
                    hook_playlist_index
                    if hook_playlist_index
                    else (self.current_playlist_item_dl_index + 1)
                )
                status_prefix = f"Item {display_index}/{self.playlist_items_count} - "
            status_msg = f"{status_prefix}Downloading: {percent_str} ({downloaded_str}/{total_bytes_str}) at {speed_str}, ETA: {eta_str}"
            self.status_callback(status_msg)
        else:
            self.status_callback(
                f"Status: {d.get('status', 'N/A')} - {item_title_cleaned}"
            )

    def _clean_filename(self, filename):
        """ينظف اسم الملف من الرموز غير المرغوبة."""
        if not filename:
            return filename
        cleaned = (
            filename.replace("//", "")
            .replace("||", "")
            .replace("|", "")
            .replace("｜", "")
            .replace("/", "")
        )
        cleaned = cleaned.replace(":", " -")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _my_hook(self, d):
        """Hook لتقدم التحميل وتخزين المعلومات النهائية."""
        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled by user.")
        status = d["status"]

        # --- START: Store filepath on finish ---
        if status == "finished":
            # نحاول الحصول على المسار من 'filepath' أولاً، ثم 'filename'
            filepath = d.get("info_dict", {}).get("filepath") or d.get("filename")
            if filepath:
                self.final_known_path = filepath  # تخزين المسار المبلغ عنه
                self.last_downloaded_info = d.get(
                    "info_dict", self.last_downloaded_info
                )  # تحديث المعلومات
                print(f"Progress hook 'finished'. Final path reported: {filepath}")
                self.status_callback(
                    f"Processing finished for: {os.path.basename(filepath)}"
                )
                self.progress_callback(1.0)
                # تحديث عداد القائمة هنا عند انتهاء معالجة عنصر
                if self.is_playlist and d.get("info_dict"):
                    # الاعتماد على وجود info_dict لتجنب العد المزدوج (للصوت/الفيديو المنفصل)
                    # قد تحتاج لتعديل أدق إذا لم يكن info_dict متوفرًا دائمًا
                    self.current_playlist_item_dl_index += 1

            else:
                print("Progress hook 'finished' but no filepath found in info.")
                self.status_callback("Processing finished (unknown file path).")
                self.progress_callback(1.0)

        elif status == "downloading":
            self._process_download_progress(d)
        elif status == "error":
            self.status_callback("Error during download process.")
            print(f"yt-dlp hook error: {d}")
        # --- END: Store filepath on finish ---

    def _download_core(self):
        """المنطق الأساسي لعملية التحميل."""
        self.last_downloaded_info = None
        self.final_known_path = None
        self.current_playlist_item_dl_index = 0
        base_tmpl_name = (
            "%(playlist_index)s. %(title)s" if self.is_playlist else "%(title)s"
        )
        output_template_base = os.path.join(self.save_path, f"{base_tmpl_name}")

        core_postprocessors = []
        format_choice_lower = self.format_choice.lower()
        quality_format_selector = self.quality_format_id
        general_format_selector = None
        output_ext = "mp4"
        final_format_string = None

        # --- START: Updated Format Logic ---
        if self.is_playlist:
            # حالة قائمة التشغيل
            if "audio (mp3)" in format_choice_lower:
                final_format_string = "bestaudio/best"
                output_ext = "mp3"
                if self.ffmpeg_path:
                    core_postprocessors.append(
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    )
                else:
                    self.status_callback("Warning: FFmpeg not found...")
                    output_ext = None
            else:
                # فيديو قائمة التشغيل: تطبيق حد 720p الافتراضي
                final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
                output_ext = "mp4"
        else:
            # حالة الفيديو المفرد
            if quality_format_selector:
                final_format_string = quality_format_selector
                if "audio (mp3)" in format_choice_lower:
                    output_ext = "mp3"
                else:
                    output_ext = "mp4"
            elif "audio (mp3)" in format_choice_lower:
                final_format_string = "bestaudio/best"
                output_ext = "mp3"
                if self.ffmpeg_path:
                    core_postprocessors.append(
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    )
                else:
                    self.status_callback("Warning: FFmpeg not found...")
                    output_ext = None
            else:
                # فيديو مفرد، استخدام الخيار العام المحدد من الواجهة
                if "<= 720p" in format_choice_lower:
                    final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
                elif "<= 480p" in format_choice_lower:
                    final_format_string = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480][ext=mp4]/best[height<=480]"
                elif "<= 360p" in format_choice_lower:
                    final_format_string = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360][ext=mp4]/best[height<=360]"
                else:
                    final_format_string = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"  # Default 1080p+
                output_ext = "mp4"
        # --- END: Updated Format Logic ---

        # --- START: Set Output Template and Format Option ---
        if output_ext:
            final_outtmpl = f"{output_template_base}.{output_ext}"
        else:
            final_outtmpl = f"{output_template_base}.%(ext)s"  # Fallback

        ydl_opts = {
            "progress_hooks": [self._my_hook],
            "outtmpl": final_outtmpl,  # استخدام القالب النهائي المحدد
            "nocheckcertificate": True,
            "ignoreerrors": self.is_playlist,
            "merge_output_format": "mp4",
            # لم نعد نستخدم postprocessor_hooks هنا لإعادة التسمية
        }
        if self.ffmpeg_path:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_path
        if self.is_playlist:
            ydl_opts["noplaylist"] = False
            ydl_opts["playlist_items"] = (
                self.playlist_items if self.playlist_items else None
            )
        else:
            ydl_opts["noplaylist"] = True

        if final_format_string:
            ydl_opts["format"] = final_format_string
        elif "format" in ydl_opts:
            del ydl_opts["format"]  # تأكد من الحذف إذا كان None

        if core_postprocessors:
            ydl_opts["postprocessors"] = core_postprocessors
        # --- END: Set Output Template and Format Option ---

        self.status_callback("Starting download...")
        self.progress_callback(0)

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if self.cancel_event.is_set():
                raise DownloadCancelled("Download cancelled before starting.")
            try:
                ydl.download([self.url])
            except yt_dlp.utils.DownloadError as dl_err:
                raise dl_err

        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled after finishing.")

    # --- START: Modified Cleanup Method ---
    def _cleanup_final_file(self):
        """يحاول تنظيف وإعادة تسمية الملف النهائي المعروف بعد انتهاء التحميل."""
        print("Attempting final file cleanup...")
        # الاعتماد على المسار الذي تم تخزينه بواسطة الهوك
        if not self.final_known_path:
            print("Cleanup skipped: No final file path was reported by hooks.")
            if not getattr(self, "_cleaned_up", False):
                self.status_callback(
                    "Warning: Download finished, but final file path unknown."
                )
                self._cleaned_up = True
            return

        expected_final_path = self.final_known_path
        print(f"Cleanup: Checking final path '{expected_final_path}'")

        # تأكد من أن المجلد موجود (قد يكون هناك خطأ إذا تم حذفه يدويًا)
        if not os.path.dirname(expected_final_path) or not os.path.exists(
            os.path.dirname(expected_final_path)
        ):
            print(
                f"Cleanup Error: Directory for path '{expected_final_path}' not found."
            )
            if not getattr(self, "_cleaned_up", False):
                self.status_callback("Error: Save directory not found during cleanup.")
                self._cleaned_up = True
            return

        # إضافة انتظار قصير جدًا (اختياري)
        # time.sleep(0.2)

        if not os.path.exists(expected_final_path):
            print(
                f"Cleanup: Final file '{expected_final_path}' not found. Merge/Processing might have failed or path is incorrect."
            )
            if not getattr(self, "_cleaned_up", False):
                self.status_callback(
                    f"Warning: Processing completed but final file '{os.path.basename(expected_final_path)}' is missing."
                )
                self._cleaned_up = True
            return

        # الملف موجود، قم بتنظيف الاسم وإعادة التسمية إذا لزم الأمر
        current_basename = os.path.basename(expected_final_path)
        cleaned_basename = self._clean_filename(current_basename)
        # التأكد من أن المسار الجديد داخل مجلد الحفظ الصحيح
        save_directory = os.path.dirname(expected_final_path)
        new_final_filepath = os.path.join(save_directory, cleaned_basename)

        final_message = f"Download complete: {current_basename}"  # الرسالة الافتراضية

        if new_final_filepath != expected_final_path:
            try:
                if os.path.exists(expected_final_path):
                    os.rename(expected_final_path, new_final_filepath)
                    print(
                        f"Final Cleanup Rename: '{current_basename}' to '{cleaned_basename}'"
                    )
                    final_message = f"Download complete: {cleaned_basename}"
                else:
                    print(
                        f"File disappeared before final cleanup rename: {expected_final_path}"
                    )
                    final_message = f"Warning: Download complete, but file missing before rename ({current_basename})"
            except OSError as e:
                print(
                    f"Error during final cleanup rename for '{current_basename}': {e}"
                )
                final_message = f"Download complete (rename failed): {current_basename}"
        else:
            final_message = f"Download complete: {current_basename}"  # الاسم كان نظيفًا

        if not getattr(self, "_cleaned_up", False):
            self.status_callback(final_message)
            self._cleaned_up = True

    # --- END: Modified Cleanup Method ---

    def run(self):
        """تنفذ عملية التحميل الفعلية."""
        download_error_occurred = False
        self._cleaned_up = False  # إعادة تعيين علامة التنظيف
        try:
            self._download_core()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
            download_error_occurred = True
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split("ERROR:")[-1].strip()
            self.status_callback(f"Download Error: {error_message}")
            print(f"yt-dlp DownloadError: {e}")
            download_error_occurred = True
        except Exception as e:
            self._log_unexpected_error(e)
            download_error_occurred = True
        finally:
            if not download_error_occurred:
                self._cleanup_final_file()
            else:
                print("Skipping final cleanup due to download error/cancellation.")
            self.finished_callback()

    def _log_unexpected_error(self, e):
        print("--- UNEXPECTED ERROR ---")
        traceback.print_exc()
        print("----------------------")
        self.status_callback(f"Unexpected download error: {type(e).__name__} - {e}")
        print(f"Unexpected Error during download: {e}")
