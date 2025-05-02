# -- ملف يحتوي على الكلاسات المسؤولة عن التفاعل المباشر مع yt-dlp --
# Purpose: Contains classes that perform the actual work of interacting with yt-dlp.

import os
import yt_dlp
import sys
from pathlib import Path
from exceptions import DownloadCancelled  # استيراد الاستثناء المخصص
import re  # استيراد للتعابير النمطية


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
    print(
        "Warning: Bundled ffmpeg not found. yt-dlp might rely on system PATH or fail some operations."
    )
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
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if self.cancel_event.is_set():
                raise DownloadCancelled("Info fetch cancelled before starting.")
            info_dict = ydl.extract_info(self.url, download=False)
        if self.cancel_event.is_set():
            raise DownloadCancelled("Info fetch cancelled after fetching.")
        self.status_callback("Information fetched successfully.")
        self.success_callback(info_dict)

    def run(self):
        """تنفذ عملية جلب المعلومات."""
        try:
            self._fetch_info_core()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split("ERROR:")[-1].strip()
            self.status_callback(f"Info Error: {error_message}")
            self.error_callback(error_message)
            print(f"yt-dlp DownloadError info fetch: {e}")
        except Exception as e:
            self.status_callback(f"Unexpected info fetch error: {type(e).__name__}")
            self.error_callback(f"Unexpected error: {e}")
            print(f"Unexpected Error info fetch: {e}")
        finally:
            self.finished_callback()


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
        self.current_playlist_item_dl_index = 0
        self.last_hook_filename = None
        self.last_final_filepath = None
        self.ffmpeg_path = ffmpeg_path
        self.cancel_event = cancel_event
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        # --- START Verification Change: Store expected path template ---
        self.expected_final_path_template = None  # لتخزين قالب المسار النهائي المتوقع
        # --- END Verification Change ---

    def _process_download_progress(self, d):
        """تحلل بيانات الهوك وتحدث الواجهة."""
        total_bytes_str = d.get("_total_bytes_str", "N/A")
        downloaded_bytes = d.get("downloaded_bytes")
        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
        speed_str = d.get("_speed_str", "N/A")
        eta_str = d.get("_eta_str", "N/A")
        percent_str = d.get("_percent_str", "N/A").strip()
        filename = d.get("filename", "N/A")
    def _my_hook(self, d):
        """Hook لتقدم التحميل مع تنظيف اسم الملف والتحقق النهائي."""
        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled by user.")

        status = d['status']
        original_filepath = d.get('filename') # المسار الذي تم الإبلاغ عنه بواسطة yt-dlp

        if status == 'downloading':
            self._process_download_progress(d)
            self.last_hook_filename = original_filepath

        elif status in ['error', "error"]:
            self.status_callback("Error during download process.")
            print(f"yt-dlp hook error: {d}")
        elif status == 'finished':
            if not original_filepath:
                print("Hook 'finished' status without filename.")
                self.status_callback("Processing finished file (unknown name)...")
                self.progress_callback(1.0)
                return

            # --- منطق تنظيف وإعادة تسمية الملف ---
            dirname = os.path.dirname(original_filepath)
            original_basename = os.path.basename(original_filepath)
            cleaned_basename = self._clean_filename(original_basename)
            new_filepath = os.path.join(dirname, cleaned_basename)
            final_filepath_to_report = original_filepath # القيمة الافتراضية

            # محاولة إعادة التسمية
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
            else: # لا يوجد ملف يمكن الإبلاغ عنه
                print(f"Warning: File '{original_filepath}' not found for reporting.")
                final_filepath_to_report = (
                    self.last_final_filepath
                    if self.last_final_filepath
                    and os.path.exists(self.last_final_filepath)
                    else None
                )
            final_basename = os.path.basename(final_filepath_to_report) if final_filepath_to_report else 'N/A'
            total_bytes_str = d.get('_total_bytes_str', 'N/A')
            # رسالة الحالة الأساسية بعد الانتهاء
            base_status_msg = f"Finished processing: '{final_basename}' ({total_bytes_str})."

            # --- START Final Verification Logic ---
            expected_final_path = None
            info_dict_hook = d.get('info_dict', {}) # الحصول على معلومات الفيديو من الهوك

            # بناء المسار المتوقع فقط إذا كان لدينا القالب والمعلومات
            if self.expected_final_path_template and info_dict_hook:
                 try:
                      # استخدام مثيل ydlp بسيط لتطبيق القالب
                      with yt_dlp.YoutubeDL({'quiet': True, 'nocheckcertificate': True}) as ydl_templater:
                           # بناء اسم الملف المتوقع باستخدام معلومات الفيديو الحالية
                           expected_filename = ydl_templater.prepare_filename(info_dict_hook, outtmpl=self.expected_final_path_template)
                           # تنظيف اسم الملف المتوقع بنفس الطريقة
                           expected_filename_cleaned = self._clean_filename(os.path.basename(expected_filename))
                           # بناء المسار الكامل المتوقع في مجلد الحفظ
                           expected_final_path = os.path.join(self.save_path, expected_filename_cleaned)

                 except Exception as template_err:
                      print(f"Error constructing expected final path: {template_err}")

            # التحقق من وجود الملف النهائي المتوقع
            if expected_final_path and not os.path.exists(expected_final_path):
                 print(f"Verification Failed: Expected final file '{expected_final_path}' not found!")
                 # تحديث رسالة الحالة لتشير إلى فشل الدمج/المعالجة
                 base_status_msg = f"Warning: Merge/Processing failed for '{original_basename}'. Expected file missing."
                 # يمكن إضافة تفاصيل أخرى مثل "Separate files might exist."
            elif not expected_final_path:
                 # لم نتمكن من بناء المسار المتوقع، تحقق فقط من الملف المبلغ عنه
                 if not final_filepath_to_report or not os.path.exists(final_filepath_to_report):
                    print(f"Verification Warning: Reported final file '{final_basename}' not found and expected path unknown.")
                    base_status_msg = f"Warning: Post-processing issue for '{original_basename}'. Final file may be missing."
            # --- END Final Verification Logic ---

            # رسالة الحالة النهائية (قد تكون تم تعديلها بواسطة التحقق)
            status_msg = base_status_msg

            # تحديث عداد القائمة
            if self.is_playlist and original_filepath and self.last_hook_filename != original_filepath:
                self.current_playlist_item_dl_index += 1
                self.last_hook_filename = original_filepath
                item_prefix = f"Item {self.current_playlist_item_dl_index}/{self.playlist_items_count} - "
                status_msg = f"{item_prefix}{base_status_msg}"

            self.status_callback(status_msg)
            self.progress_callback(1.0) # إظهار اكتمال الملف الحالي

            # --- START Final Verification Logic ---
            expected_final_path = None
            info_dict_hook = d.get(
                "info_dict", {}
            )  # الحصول على معلومات الفيديو من الهوك

            # بناء المسار المتوقع فقط إذا كان لدينا القالب والمعلومات
            if self.expected_final_path_template and info_dict_hook:
                try:
                    # استخدام مثيل ydlp بسيط لتطبيق القالب
                    with yt_dlp.YoutubeDL(
                        {"quiet": True, "nocheckcertificate": True}
                    ) as ydl_templater:
                        # بناء اسم الملف المتوقع باستخدام معلومات الفيديو الحالية
                        expected_filename = ydl_templater.prepare_filename(
                            info_dict_hook, outtmpl=self.expected_final_path_template
                        )
                        # تنظيف اسم الملف المتوقع بنفس الطريقة
                        expected_filename_cleaned = self._clean_filename(
                            os.path.basename(expected_filename)
                        )
                        # بناء المسار الكامل المتوقع في مجلد الحفظ
                        expected_final_path = os.path.join(
                            self.save_path, expected_filename_cleaned
                        )

                except Exception as template_err:
                    print(f"Error constructing expected final path: {template_err}")

            # التحقق من وجود الملف النهائي المتوقع
            if expected_final_path and not os.path.exists(expected_final_path):
                print(
                    f"Verification Failed: Expected final file '{expected_final_path}' not found!"
                )
                # تحديث رسالة الحالة لتشير إلى فشل الدمج/المعالجة
                base_status_msg = f"Warning: Merge/Processing failed for '{original_basename}'. Expected file missing."
                # يمكن إضافة تفاصيل أخرى مثل "Separate files might exist."
            elif not expected_final_path:
                # لم نتمكن من بناء المسار المتوقع، تحقق فقط من الملف المبلغ عنه
                if not final_filepath_to_report or not os.path.exists(
                    final_filepath_to_report
                ):
                    print(
                        f"Verification Warning: Reported final file '{final_basename}' not found and expected path unknown."
                    )
                    base_status_msg = f"Warning: Post-processing issue for '{original_basename}'. Final file may be missing."
            # --- END Final Verification Logic ---

            # رسالة الحالة النهائية (قد تكون تم تعديلها بواسطة التحقق)
            status_msg = base_status_msg

            # تحديث عداد القائمة
            if (
                self.is_playlist
                and original_filepath
                and self.last_hook_filename != original_filepath
            ):
                self.current_playlist_item_dl_index += 1
                self.last_hook_filename = original_filepath
                item_prefix = f"Item {self.current_playlist_item_dl_index}/{self.playlist_items_count} - "
                status_msg = f"{item_prefix}{base_status_msg}"

            self.status_callback(status_msg)
            self.progress_callback(1.0)  # إظهار اكتمال الملف الحالي

    def _download_core(self):
        """المنطق الأساسي لعملية التحميل."""
        # --- START Verification Change: Define base output template ---
        base_tmpl_name = (
            "%(playlist_index)s. %(title)s" if self.is_playlist else "%(title)s"
        )
        output_template_base = os.path.join(self.save_path, f"{base_tmpl_name}")
        # --- END Verification Change ---

        ydl_opts = {
            "progress_hooks": [self._my_hook],
            "outtmpl": f"{output_template_base}.%(ext)s",  # استخدام %(ext)s هنا
            "nocheckcertificate": True,
            "ignoreerrors": self.is_playlist,
            "postprocessor_hooks": [],
            "merge_output_format": "mp4",
        }
        if self.ffmpeg_path:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_path
        if self.is_playlist:
            ydl_opts["noplaylist"] = False
            if self.playlist_items:
                ydl_opts["playlist_items"] = self.playlist_items
        else:
            ydl_opts["noplaylist"] = True

        # --- منطق تحديد الصيغة والجودة والمعالجات ---
        postprocessors = []
        format_choice_lower = self.format_choice.lower()
        quality_format_selector = None
        if self.quality_format_id:
            quality_format_selector = self.quality_format_id
        general_format_selector = None
        output_ext = "mp4"  # الامتداد المتوقع الافتراضي

        # (تحديد general_format_selector و output_ext و postprocessors بناءً على format_choice_lower)
        if "<= 720p" in format_choice_lower:
            general_format_selector = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
        elif "<= 480p" in format_choice_lower:
            general_format_selector = "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=480]+bestaudio/best[height<=480][ext=mp4]/best[height<=480]"
        elif "<= 360p" in format_choice_lower:
            general_format_selector = "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360][ext=mp4]/best[height<=360]"
        elif "audio (mp3)" in format_choice_lower:
            general_format_selector = "bestaudio/best"
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
                self.status_callback(
                    "Warning: FFmpeg not found. Cannot convert to MP3."
                )
                general_format_selector = "bestaudio/best"
                output_ext = None  # غير متأكدين من الامتداد
        else:  # Default
            general_format_selector = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"

        final_format = (
            quality_format_selector
            if quality_format_selector and not self.is_playlist
            else general_format_selector
        )
        ydl_opts["format"] = final_format

        # --- START Verification Change: Store the final expected path template ---
        if output_ext:
            # تخزين القالب بالامتداد المتوقع
            self.expected_final_path_template = f"{output_template_base}.{output_ext}"
        else:
            # تخزين القالب العام إذا لم نكن متأكدين من الامتداد
            self.expected_final_path_template = f"{output_template_base}.%(ext)s"
        # --- END Verification Change ---

        # إضافة المعالجات اللاحقة إذا وجدت
        if postprocessors:
            ydl_opts["postprocessors"] = postprocessors
        # --- نهاية منطق الصيغة والجودة ---

        self.status_callback("Starting download...")
        self.progress_callback(0)
        self.current_playlist_item_dl_index = 0
        self.last_hook_filename = None
        self.last_final_filepath = None

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if self.cancel_event.is_set():
                raise DownloadCancelled("Download cancelled before starting.")
            try:
                ydl.download([self.url])
            except yt_dlp.utils.DownloadError as dl_err:
                raise dl_err  # إعادة الإطلاق ليتم التعامل معه في run

        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled after finishing.")

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
            error_message = str(e).split("ERROR:")[-1].strip()
            self.status_callback(f"Download Error: {error_message}")
            print(f"yt-dlp DownloadError: {e}")
        except Exception as e:
            self._extracted_from_run_14(e)
        finally:
            self.finished_callback()

    # TODO Rename this here and in `run`
    def _extracted_from_run_14(self, e):
        # إضافة تتبع أكثر تفصيلاً للخطأ غير المتوقع
        import traceback

        print("--- UNEXPECTED ERROR ---")
        traceback.print_exc()  # طباعة تتبع الخطأ الكامل في الطرفية
        print("----------------------")
        self.status_callback(f"Unexpected download error: {type(e).__name__} - {e}")
        print(f"Unexpected Error during download: {e}")
