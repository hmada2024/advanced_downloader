# -- ملف يحتوي على الكلاسات المسؤولة عن التفاعل المباشر مع yt-dlp --
# Purpose: Contains classes that perform the actual work of interacting with yt-dlp.

import os
import yt_dlp
import sys
from pathlib import Path

# استخدام الاستيراد النسبي للملفات داخل نفس الحزمة
from .exceptions import DownloadCancelled
import re
import traceback
import time  # لاستخدامه المحتمل في التنظيف


# --- دالة find_ffmpeg ---
def find_ffmpeg():
    """
    يحاول العثور على ملف ffmpeg.exe التنفيذي المرفق مع التطبيق أو في PATH.
    Attempts to find the bundled ffmpeg.exe or one in the system PATH.
    """
    try:
        if getattr(sys, "frozen", False):
            base_path = Path(sys.executable).parent
        else:
            base_path = Path(__file__).parent.parent
    except Exception:
        base_path = Path(".")

    bundled_path = base_path / "ffmpeg_bin" / "ffmpeg.exe"

    if bundled_path.is_file():
        print(f"Found bundled ffmpeg: {bundled_path}")
        return str(bundled_path)
    else:
        print(f"Bundled ffmpeg not found at '{bundled_path}'. Checking PATH...")
        try:
            ffmpeg_path_in_env = yt_dlp.utils.ffmpeg_executable()
            if ffmpeg_path_in_env and Path(ffmpeg_path_in_env).is_file():
                print(f"Using ffmpeg from PATH: {ffmpeg_path_in_env}")
                return ffmpeg_path_in_env
        except Exception as e:
            print(f"Error checking for ffmpeg in PATH: {e}")

        print("Warning: ffmpeg not found in bundle or system PATH.")
        return None


# --- كلاس لجلب المعلومات ---
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

    def _check_cancel(self, stage=""):
        if self.cancel_event.is_set():
            raise DownloadCancelled(f"Info fetch cancelled {stage}.")

    def _fetch_info_core(self):
        self.status_callback("Fetching information...")
        self.progress_callback(0)
        self._check_cancel("before starting fetch")

        ydl_opts = {
            "quiet": True,
            "nocheckcertificate": True,
            "extract_flat": "in_playlist",
            "playlistend": 500,
            "ignoreerrors": True,  # استمر في حالة وجود خطأ في عنصر واحد
            "forcejson": True,
            "skip_download": True,
            # 'socket_timeout': 15, # إضافة مهلة للشبكة (اختياري)
        }

        info_dict = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._check_cancel("before calling extract_info")
                info_dict = ydl.extract_info(self.url, download=False)
                self._check_cancel("after calling extract_info")

        except yt_dlp.utils.DownloadError as e:
            error_message = str(e)
            if "ERROR:" in error_message:
                error_message = error_message.split("ERROR:")[-1].strip()
            # قد يكون هناك معلومات جزئية مع الخطأ، حاول التحقق
            partial_info = getattr(e, "partial", False) and getattr(e, "data", None)
            if partial_info:
                print(f"InfoFetcher yt-dlp DownloadError with partial data: {e}")
                self.success_callback(partial_info)  # إرسال البيانات الجزئية للواجهة
            else:
                print(f"InfoFetcher yt-dlp DownloadError: {e}")
                self.error_callback(error_message)
            return

        except DownloadCancelled:
            raise
        except Exception as e:
            print(f"InfoFetcher Unexpected Error: {e}")
            traceback.print_exc()
            self.error_callback(f"An unexpected error occurred: {type(e).__name__}")
            return

        if info_dict:
            if "entries" in info_dict and isinstance(info_dict["entries"], list):
                valid_entries = [entry for entry in info_dict["entries"] if entry]
                if not valid_entries and info_dict.get("extractor_key") == "YoutubeTab":
                    # حالة خاصة: قائمة تشغيل يوتيوب فارغة أو خاصة
                    print("InfoFetcher: YouTube playlist seems empty or private.")
                    self.error_callback(
                        "Playlist is empty, private, or could not be accessed."
                    )
                    return
                info_dict["entries"] = (
                    valid_entries  # تحديث القائمة بالإدخالات الصالحة فقط
                )

            self.status_callback("Information fetched successfully.")
            self.success_callback(info_dict)
        else:
            # قد يحدث هذا إذا لم يتم العثور على الفيديو/القائمة على الإطلاق
            print(
                "InfoFetcher: No information dictionary returned (URL might be invalid)."
            )
            self.error_callback(
                "Could not retrieve information (URL might be invalid or video unavailable)."
            )

    def run(self):
        try:
            self._fetch_info_core()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
        except Exception as e:
            print(f"InfoFetcher FATAL UNEXPECTED Error in run: {e}")
            traceback.print_exc()
            self.error_callback(
                f"A critical unexpected error occurred: {type(e).__name__}"
            )
        finally:
            print("InfoFetcher: Reached finally block, calling finished_callback.")
            self.finished_callback()


# --- كلاس لتنفيذ التحميل ---
class Downloader:
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
        self.last_downloaded_info = None
        self.final_known_path = None
        self.current_playlist_item_dl_index = 0
        self._cleaned_up_path = None

    def _check_cancel(self, stage=""):
        if self.cancel_event.is_set():
            raise DownloadCancelled(f"Download cancelled {stage}.")

    def _clean_filename(self, filename):
        if not filename:
            return filename
        cleaned = re.sub(r'[\\/*?:"<>|]', "", filename)
        cleaned = cleaned.replace(":", " -")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = cleaned.rstrip(". ")
        if not cleaned:
            return "downloaded_file"
        return cleaned

    def _my_hook(self, d):
        try:
            self._check_cancel("during progress hook")
        except DownloadCancelled as e:
            raise yt_dlp.utils.DownloadCancelled(str(e))

        status = d.get("status")

        if status == "finished":
            filepath = d.get("info_dict", {}).get("filepath") or d.get("filename")
            if filepath:
                self.final_known_path = filepath
                self.last_downloaded_info = d.get(
                    "info_dict", self.last_downloaded_info
                )
                print(f"Hook 'finished': Path reported '{filepath}'.")
                base_filename = os.path.basename(filepath)
                # --- تحسين رسالة الانتهاء ---
                # التحقق مما إذا كان الملف قد تم دمجه (الامتداد النهائي موجود)
                final_ext_present = any(
                    base_filename.lower().endswith(ext)
                    for ext in [".mp4", ".mp3", ".mkv", ".webm"]
                )
                display_name = self._clean_filename(
                    d.get("info_dict", {}).get("title", base_filename)
                )

                if final_ext_present:
                    # إذا كان الامتداد النهائي موجودًا، فهذا هو نهاية العنصر
                    status_msg = f"Finished: {display_name}"
                    if self.is_playlist:
                        # زيادة العداد فقط عند الانتهاء الفعلي
                        self.current_playlist_item_dl_index += 1
                        print(
                            f"Playlist item index counter incremented to: {self.current_playlist_item_dl_index}"
                        )
                else:
                    # إذا كان الامتداد غير نهائي، فهو لا يزال قيد المعالجة (تنزيل جزء، دمج قادم)
                    status_msg = f"Processing: {display_name}..."

                self.status_callback(status_msg)
                self.progress_callback(1.0)

            else:
                print("Hook 'finished' but no filepath found in hook data.")
                self.status_callback("Processing finished (unknown file path).")
                self.progress_callback(1.0)

        elif status == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded_bytes = d.get("downloaded_bytes")
            if total_bytes and downloaded_bytes is not None:
                progress = downloaded_bytes / total_bytes
                self.progress_callback(max(0.0, min(1.0, progress)))
                status_prefix = ""
                if self.is_playlist and self.playlist_items_count > 0:
                    display_index = self.current_playlist_item_dl_index + 1
                    status_prefix = (
                        f"Item {display_index}/{self.playlist_items_count} - "
                    )
                percent_str = d.get("_percent_str", "N/A").strip()
                downloaded_str = d.get("_downloaded_bytes_str", "N/A")
                total_bytes_str = d.get("_total_bytes_str", "N/A")
                speed_str = d.get("_speed_str", "N/A")
                eta_str = d.get("_eta_str", "N/A")
                status_msg = f"{status_prefix}Downloading: {percent_str} ({downloaded_str}/{total_bytes_str}) at {speed_str}, ETA: {eta_str}"
                self.status_callback(status_msg)
            else:
                self.status_callback(f"Status: {d.get('status', 'N/A')}...")

        elif status == "error":
            self.status_callback("Error during download process reported by yt-dlp.")
            print(
                f"yt-dlp hook reported error: {d.get('error', 'Unknown yt-dlp error')}"
            )

    def _build_format_string(self):
        # (هذا الجزء لم يتغير، يبدو أنه كان صحيحًا)
        format_choice_lower = self.format_choice.lower()
        output_ext = "mp4"
        postprocessors = []
        final_format_string = None

        if not self.is_playlist and self.quality_format_id:
            final_format_string = self.quality_format_id
            print(f"Using specific quality format ID: {self.quality_format_id}")
            if "audio (mp3)" in format_choice_lower:
                output_ext = "mp3"
                if self.ffmpeg_path:
                    postprocessors.append(
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    )
                else:
                    print("Warning: MP3 requested but FFmpeg not found.")
        else:
            if "audio (mp3)" in format_choice_lower:
                final_format_string = "bestaudio/best"
                output_ext = "mp3"
                if self.ffmpeg_path:
                    postprocessors.append(
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    )
                else:
                    print(
                        "Warning: MP3 requested but FFmpeg not found. Format might not be MP3."
                    )
                    output_ext = None
            elif self.is_playlist:
                final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
                output_ext = "mp4"
                print("Using default playlist format (max 720p MP4)")
            else:
                if "<= 720p" in format_choice_lower:
                    final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
                    print("Using general format: max 720p MP4")
                elif "<= 480p" in format_choice_lower:
                    final_format_string = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480][ext=mp4]/best[height<=480]"
                    print("Using general format: max 480p MP4")
                elif "<= 360p" in format_choice_lower:
                    final_format_string = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360][ext=mp4]/best[height<=360]"
                    print("Using general format: max 360p MP4")
                else:
                    final_format_string = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
                    print("Using general format: best available MP4 (1080p+)")
                output_ext = "mp4"

        return final_format_string, output_ext, postprocessors

    def _download_core(self):
        self.last_downloaded_info = None
        self.final_known_path = None
        self.current_playlist_item_dl_index = 0
        self._cleaned_up_path = None
        self._check_cancel("before starting download")

        # --- تعديل بناء قالب اسم الملف ---
        # تأكد من استخدام الشرطة المائلة الصحيحة لنظام التشغيل
        # ووضع العنوان دائمًا
        if self.is_playlist:
            # استخدام format لضمان تفسير الحقول بشكل صحيح
            outtmpl_pattern = os.path.join(
                self.save_path, "%(playlist_index)s. %(title)s.%(ext)s"
            )
        else:
            outtmpl_pattern = os.path.join(self.save_path, "%(title)s.%(ext)s")
        # -----------------------------------

        final_format_string, output_ext, core_postprocessors = (
            self._build_format_string()
        )

        # --- إزالة بناء القالب اليدوي باستخدام pathlib ---
        # final_outtmpl = ... (تمت إزالته)
        # ---------------------------------------------

        ydl_opts = {
            "progress_hooks": [self._my_hook],
            # --- استخدام outtmpl pattern مباشرة ---
            "outtmpl": outtmpl_pattern,
            # --------------------------------------
            "nocheckcertificate": True,
            "ignoreerrors": self.is_playlist,
            "merge_output_format": "mp4",  # تفضيل الدمج لـ MP4
            "postprocessors": core_postprocessors,
            "restrictfilenames": False,  # السماح بالمسافات وغيرها
            # --- إضافة خيار مهم: إصلاح ما بعد المعالجة للدمج ---
            # هذا قد يساعد في ضمان الدمج الصحيح لـ MP4 في بعض الحالات
            "postprocessor_args": {
                "ffmpeg": [
                    "-vcodec",
                    "copy",
                    "-acodec",
                    "copy",
                ]  # نسخ الترميز لتسريع الدمج
            },
            # --- خيار لطلب معلومات إضافية (قد يبطئ قليلاً) ---
            # 'writeinfojson': True, # للحصول على ملف .info.json لكل فيديو
        }

        if self.ffmpeg_path:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_path
        elif core_postprocessors:
            self.status_callback("Warning: FFmpeg needed but not found.")

        if self.is_playlist:
            ydl_opts["noplaylist"] = False
            if self.playlist_items:
                ydl_opts["playlist_items"] = self.playlist_items
        else:
            ydl_opts["noplaylist"] = True

        if final_format_string:
            ydl_opts["format"] = final_format_string
        elif "format" in ydl_opts:
            del ydl_opts["format"]

        # طباعة الخيارات النهائية للتحقق
        print("Final yt-dlp options:", ydl_opts)

        self.status_callback("Starting download...")
        self.progress_callback(0)
        self._check_cancel("right before calling ydl.download()")

        download_successful = False
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            download_successful = True
            self._check_cancel("immediately after ydl.download() finished")
        except yt_dlp.utils.DownloadCancelled as e:
            raise DownloadCancelled(str(e))
        except yt_dlp.utils.DownloadError as dl_err:
            error_message = str(dl_err).split("ERROR:")[-1].strip()
            print(f"Downloader yt-dlp DownloadError: {dl_err}")
            self.status_callback(f"Download Error: {error_message}")
            # تحقق مما إذا كان الخطأ متعلقًا بالفهرس المطلوب
            if "requested format not available" in error_message.lower():
                # قد يكون من المفيد عرض رسالة أكثر تحديدًا هنا
                pass
        except Exception as e:
            self._log_unexpected_error(e, "during yt-dlp download execution")

        self._check_cancel("after download block completion")

        if not download_successful:
            print("Download process reported errors. Skipping final cleanup.")
            return

        try:
            # تأخير بسيط قبل التنظيف للسماح بإغلاق الملفات
            time.sleep(0.2)
            self._cleanup_final_file()
        except Exception as e:
            self._log_unexpected_error(e, "during final file cleanup")
            self.status_callback("Warning: Download complete, but cleanup failed.")

    def _cleanup_final_file(self):
        # (الكود هنا لم يتغير، يعتمد على final_known_path)
        if self._cleaned_up_path:
            print(f"Cleanup skipped: Already cleaned path '{self._cleaned_up_path}'")
            return

        print("Attempting final file cleanup...")
        if not self.final_known_path:
            print("Cleanup skipped: No final file path was reported by hooks.")
            self.status_callback(
                "Warning: Download finished, but final file path is unknown."
            )
            return

        expected_final_path_obj = Path(self.final_known_path)
        print(f"Cleanup: Checking final path '{expected_final_path_obj}'")

        # زيادة وقت الانتظار قليلًا
        time.sleep(0.3)
        if not expected_final_path_obj.exists():
            # محاولة إيجاد الملف باسم متوقع (بناءً على آخر معلومات)
            if self.last_downloaded_info:
                expected_name = f"{self.last_downloaded_info.get('playlist_index', '')}. {self.last_downloaded_info.get('title', '')}.{self.last_downloaded_info.get('ext', 'mp4')}"
                alt_path = expected_final_path_obj.with_name(
                    self._clean_filename(expected_name)
                )
                if alt_path.exists():
                    print(f"Found file at alternative path: {alt_path}")
                    expected_final_path_obj = alt_path
                else:
                    print(
                        f"Cleanup Error: Expected final file '{expected_final_path_obj}' and alt '{alt_path}' not found."
                    )
                    self.status_callback(
                        f"Error: Processing completed but final file '{expected_final_path_obj.name}' is missing."
                    )
                    return
            else:
                print(
                    f"Cleanup Error: Expected final file '{expected_final_path_obj}' not found and no info to guess alternative."
                )
                self.status_callback(
                    f"Error: Processing completed but final file '{expected_final_path_obj.name}' is missing."
                )
                return

        current_basename = expected_final_path_obj.name
        # --- استخدام اسم الملف من المعلومات المجوبة إذا كان متاحًا ---
        # هذا قد يكون أدق من تنظيف الاسم الحالي الذي قد يكون تم تعديله بواسطة yt-dlp
        target_basename = current_basename
        if self.last_downloaded_info:
            base_title = self.last_downloaded_info.get("title", "")
            base_ext = self.last_downloaded_info.get(
                "ext", expected_final_path_obj.suffix.lstrip(".")
            )
            if self.is_playlist:
                playlist_index = self.last_downloaded_info.get("playlist_index")
                if playlist_index is not None:
                    target_basename = f"{playlist_index}. {base_title}.{base_ext}"
                else:  # في حال لم يتوفر الفهرس لسبب ما
                    target_basename = f"{base_title}.{base_ext}"
            else:
                target_basename = f"{base_title}.{base_ext}"
            target_basename = self._clean_filename(
                target_basename
            )  # تنظيف الاسم المستهدف
        # -------------------------------------------------------

        cleaned_basename = self._clean_filename(
            current_basename
        )  # تنظيف الاسم الحالي للمقارنة
        new_final_filepath_obj = expected_final_path_obj.with_name(
            target_basename
        )  # استخدام الاسم المستهدف

        final_message = f"Download complete: {target_basename}"

        if new_final_filepath_obj != expected_final_path_obj:
            print(f"Attempting rename: '{current_basename}' -> '{target_basename}'")
            try:
                if expected_final_path_obj.exists():
                    expected_final_path_obj.rename(new_final_filepath_obj)
                    print(f"Rename successful: '{new_final_filepath_obj}'")
                    self._cleaned_up_path = str(new_final_filepath_obj)
                else:
                    print(f"File disappeared before rename: {expected_final_path_obj}")
                    final_message = f"Warning: Download ok, but file missing before rename ({current_basename})"
                    self._cleaned_up_path = None
            except OSError as e:
                print(f"Error during final rename for '{current_basename}': {e}")
                final_message = f"Download complete (rename failed): {current_basename}"
                self._cleaned_up_path = str(expected_final_path_obj)
        else:
            print("Filename already correct. No rename needed.")
            self._cleaned_up_path = str(expected_final_path_obj)

        # تحديث الحالة بالرسالة النهائية
        # self.status_callback(final_message) # <- الهوك يقوم الآن بإظهار رسالة "Finished: ..."

    def run(self):
        download_error_occurred = False
        self._cleaned_up_path = None

        try:
            self._download_core()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
            download_error_occurred = True
        except Exception as e:
            self._log_unexpected_error(e, "in main run loop")
            download_error_occurred = True
        finally:
            print("Downloader: Reached finally block, calling finished_callback.")
            self.finished_callback()

    def _log_unexpected_error(self, e, context=""):
        print(f"--- UNEXPECTED ERROR ({context}) ---")
        traceback.print_exc()
        print("------------------------------------")
        self.status_callback(f"Unexpected Error ({type(e).__name__})! Check logs.")
        print(f"Unexpected Error during download ({context}): {e}")
