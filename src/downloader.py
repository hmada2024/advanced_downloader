# src/downloader.py
# -- ملف يحتوي على كلاس التحميل الرئيسي --
# Purpose: Contains the main Downloader class responsible for the download process.

import os
import yt_dlp
import sys
from pathlib import Path
import traceback
import time
import humanize
import contextlib
import re  # <-- استيراد Regex Import Regex

from .exceptions import DownloadCancelled
from .logic_utils import clean_filename


class Downloader:
    """
    كلاس مسؤول عن عملية تحميل الفيديو/الصوت ومعالجته باستخدام yt-dlp.
    Class responsible for downloading and processing video/audio using yt-dlp.
    """

    def __init__(
        self,
        url,
        save_path,
        format_choice,  # <- هذا الآن يحتوي على النص الجديد This now contains the new text
        quality_format_id,  # <- لا يزال يُستخدم إذا اختار المستخدم جودة محددة من قائمة الجودات Still used if user picks specific quality from QualitySelector
        is_playlist,
        playlist_items,
        selected_items_count,
        total_playlist_count,
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
        self.selected_items_count = selected_items_count
        self.total_playlist_count = total_playlist_count
        self.ffmpeg_path = ffmpeg_path
        self.cancel_event = cancel_event
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

        # متغيرات الحالة الداخلية Internal state variables
        self._current_processing_playlist_idx_display = 1
        self._last_hook_playlist_index = 0
        self._processed_selected_count = 0

    def _check_cancel(self, stage=""):
        if self.cancel_event.is_set():
            raise DownloadCancelled(f"Download cancelled {stage}.")

    def _my_hook(self, d):
        # --- هذا المنطق يبقى كما هو في النسخة السابقة ---
        # --- This logic remains the same as the previous version ---
        # (Handles progress updates and pre-postprocessor 'finished' status)
        try:
            self._check_cancel("during progress hook")
        except DownloadCancelled as e:
            raise yt_dlp.utils.DownloadCancelled(str(e)) from e

        status = d.get("status")
        info_dict = d.get("info_dict", {})
        hook_playlist_index = info_dict.get("playlist_index")

        if (
            self.is_playlist
            and hook_playlist_index is not None
            and hook_playlist_index > self._last_hook_playlist_index
        ):
            # print(f"Hook detected transition to playlist index: {hook_playlist_index}. Updating display counter.") # DEBUG
            self._current_processing_playlist_idx_display = hook_playlist_index
            self._last_hook_playlist_index = hook_playlist_index

        if status == "finished":
            if filepath := info_dict.get("filepath") or d.get("filename"):
                self._extracted_from__my_hook_27(filepath, info_dict)
            else:
                # print("Hook 'finished' (pre-postprocessing) but no filepath found.") # DEBUG
                self.status_callback("Processing finished (unknown file path).")
            self.progress_callback(1.0)
        elif status == "downloading":
            downloaded_bytes = d.get("downloaded_bytes")
            if downloaded_bytes is not None:
                self._extracted_from__my_hook_53(d, downloaded_bytes)
            else:
                self.status_callback(f"Status: {d.get('status', 'Connecting')}...")

        elif status == "error":
            self.status_callback("Error during download process reported by yt-dlp.")
            print(
                f"yt-dlp hook reported error: {d.get('error', 'Unknown yt-dlp error')}"
            )

    # TODO Rename this here and in `_my_hook`
    def _extracted_from__my_hook_53(self, d, downloaded_bytes):
        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
        progress = 0.0
        percentage_str = "0.0%"
        if total_bytes and total_bytes > 0:
            progress = max(0.0, min(1.0, downloaded_bytes / total_bytes))
            percentage_str = f"{progress:.1%}"
        self.progress_callback(progress)

        status_lines = []
        if self.is_playlist:
            self._extracted_from__my_hook_63(status_lines)
        else:
            status_lines.append("Downloading Video")

        downloaded_size_str = humanize.naturalsize(
            downloaded_bytes, binary=True
        )
        total_size_str = (
            humanize.naturalsize(total_bytes, binary=True)
            if total_bytes
            else "Unknown size"
        )
        status_lines.append(
            f"Progress: {percentage_str} ({downloaded_size_str} / {total_size_str})"
        )

        speed = d.get("speed")
        speed_str = (
            f"{humanize.naturalsize(speed, binary=True, gnu=True)}/s"
            if speed
            else "Calculating..."
        )
        eta = d.get("eta")
        eta_str = "Calculating..."
        with contextlib.suppress(TypeError, ValueError):
            if eta is not None and isinstance(eta, (int, float)) and eta >= 0:
                eta_str = f"{int(round(eta))} seconds remaining"
        status_lines.append(f"Speed: {speed_str} | ETA: {eta_str}")

        status_msg = "\n".join(status_lines)
        self.status_callback(status_msg)

    # TODO Rename this here and in `_my_hook`
    def _extracted_from__my_hook_63(self, status_lines):
        current_absolute_index = (
            self._current_processing_playlist_idx_display
        )
        total_absolute_str = (
            f"out of {self.total_playlist_count} total"
            if self.total_playlist_count > 0
            else ""
        )
        status_lines.append(
            f"Video {current_absolute_index} {total_absolute_str}"
        )
        index_in_selection = self._processed_selected_count + 1
        index_in_selection = min(
            index_in_selection, self.selected_items_count
        )
        remaining_in_selection = max(
            0, self.selected_items_count - self._processed_selected_count
        )
        status_lines.append(
            f"Selected: {index_in_selection} of {self.selected_items_count} ({remaining_in_selection} remaining)"
        )

    # TODO Rename this here and in `_my_hook`
    def _extracted_from__my_hook_27(self, filepath, info_dict):
        # print(f"Hook 'finished' (pre-postprocessing): Path reported '{filepath}'.") # DEBUG
        base_filename = os.path.basename(filepath)
        final_ext_present = any(
            base_filename.lower().endswith(ext)
            for ext in [".mp4", ".mp3", ".mkv", ".webm", ".opus", ".ogg"]
        )
        title = info_dict.get("title")
        display_name = clean_filename(title or base_filename)

        if final_ext_present:
            status_msg = f"Finished: {display_name}"
            # Increment counter here based on assumption final file is done pre-merge
            self._processed_selected_count += 1
            # print(f"Processed selected items count incremented in pre-hook to: {self._processed_selected_count}") # DEBUG
        else:
            status_msg = f"Processing: {display_name}..."

        self.status_callback(status_msg)

    def _postprocessor_hook(self, d):
        # --- هذا المنطق يبقى كما هو في النسخة السابقة ---
        # --- This logic remains the same as the previous version ---
        # (Handles post-merge/conversion renaming)
        print(
            f"Postprocessor Hook called with status: {d.get('status')}, postprocessor: {d.get('postprocessor')}"
        )

        if d["status"] == "finished":
            info_dict = d.get("info_dict", {})
            final_filepath = info_dict.get("filepath")

            if not final_filepath or not Path(final_filepath).is_file():
                print(
                    f"Postprocessor Error: Final file path '{final_filepath}' not found or missing after postprocessing."
                )
                return

            print(
                f"Postprocessor Hook: Final file confirmed at '{final_filepath}'. Proceeding with rename check."
            )
            expected_final_path_obj = Path(final_filepath)
            current_basename = expected_final_path_obj.name
            target_basename = current_basename

            base_title = info_dict.get("title", "")
            base_ext = expected_final_path_obj.suffix.lstrip(".")
            playlist_index = info_dict.get("playlist_index")

            if playlist_index is not None:
                target_basename = f"{playlist_index}. {base_title}.{base_ext}"
            else:  # Single video
                target_basename = f"{base_title}.{base_ext}"

            target_basename = clean_filename(target_basename)

            if target_basename != current_basename:
                new_final_filepath_obj = expected_final_path_obj.with_name(
                    target_basename
                )
                print(
                    f"Postprocessor: Attempting rename: '{current_basename}' -> '{target_basename}'"
                )
                try:
                    expected_final_path_obj.rename(new_final_filepath_obj)
                    print(
                        f"Postprocessor: Rename successful: '{new_final_filepath_obj}'"
                    )
                except OSError as e:
                    print(
                        f"Postprocessor Error during rename for '{current_basename}': {e}"
                    )
            else:
                print(
                    f"Postprocessor: Filename '{current_basename}' already correct. No rename needed."
                )

        elif d["status"] == "started":
            print(f"Postprocessor Hook: '{d.get('postprocessor')}' started.")

    def _build_format_string(self):
        """
        يبني سلسلة خيارات التنسيق والجودة لـ yt-dlp والمعالجات اللاحقة بناءً على الاختيار العام الجديد.
        Builds the format/quality option string for yt-dlp and postprocessors based on the new general choice.
        Returns:
            tuple: (format_string, output_extension_hint, postprocessors_list)
        """
        # القيم الافتراضية Default values
        output_ext = "mp4"
        postprocessors = []
        final_format_string = None

        # --- *** تعديل المنطق بالكامل *** ---
        # --- *** Entire logic modified *** ---

        # الحالة 1: التحميل الصوتي فقط Case 1: Audio Only Download
        if self.format_choice == "Download Audio Only (MP3)":
            final_format_string = "bestaudio/best"  # اطلب أفضل صوت Request best audio
            output_ext = "mp3"
            if self.ffmpeg_path:
                # إضافة معالج لتحويل الصوت إلى MP3 Add postprocessor to convert audio to MP3
                postprocessors.append(
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",  # يمكنك تعديل الجودة You can adjust the quality
                    }
                )
                print("Selecting best audio for MP3 conversion.")
            else:
                # تحذير إذا لم يتم العثور على FFmpeg Warn if FFmpeg is not found
                print(
                    "Warning: MP3 requested but FFmpeg not found. Downloading best audio format."
                )
                # لا يمكن ضمان الامتداد MP3 بدون FFmpeg Cannot guarantee MP3 extension without FFmpeg
                output_ext = None  # سيقوم yt-dlp بتحديد الامتداد الأصلي yt-dlp will determine original extension
            print(
                f"BuildFormat: Audio mode selected. Format: '{final_format_string}', Ext: {output_ext}"
            )
        else:
            if match := re.search(r"\b(\d{3,4})p\b", self.format_choice):
                # تم العثور على رقم الدقة A resolution number was found
                height_limit = int(match[1])
                print(f"BuildFormat: Found height limit: {height_limit}p")

                # بناء سلسلة التنسيق التي تطلب أفضل فيديو حتى هذا الارتفاع
                # Build the format string requesting best video up to this height
                # هذه السلسلة هي نفسها المستخدمة سابقًا It's the same string used previously
                final_format_string = (
                    f"bestvideo[height<={height_limit}][ext=mp4]+bestaudio[ext=m4a]/"  # الأفضل: MP4 Video + M4A Audio
                    f"bestvideo[height<={height_limit}]+bestaudio/"  # بديل 1: أي فيديو + أي صوت Alternative 1: Any Video + Any Audio
                    f"best[height<={height_limit}][ext=mp4]/"  # بديل 2: أفضل ملف مدمج MP4 Alternative 2: Best merged MP4
                    f"best[height<={height_limit}]"  # بديل 3: أفضل ملف مدمج (أي امتداد) Alternative 3: Best merged (any ext)
                )
            else:
                # حالة احتياطية: لم يتم العثور على دقة في النص (لا يجب أن يحدث) Fallback case: No resolution found in text (should not happen)
                print(
                    f"BuildFormat Warning: Could not parse height from format choice '{self.format_choice}'. Falling back to default 720p."
                )
                # استخدام 720p كافتراضي آمن Use 720p as a safe default
                height_limit = 720
                final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
            postprocessors = (
                []
            )  # لا حاجة لمعالجات خاصة هنا No special postprocessors needed here

            output_ext = "mp4"  # نتوقع MP4 We expect MP4
            print(
                f"BuildFormat: Video mode selected. Format: '{final_format_string}', Ext: {output_ext}"
            )

        return final_format_string, output_ext, postprocessors
        # --------------------------------------------

    def _download_core(self):
        # --- أغلب هذا المنطق يبقى كما هو --- Most of this logic remains the same ---
        self._current_processing_playlist_idx_display = 1
        self._last_hook_playlist_index = 0
        self._processed_selected_count = 0

        self._check_cancel("before starting download")

        if self.is_playlist:
            outtmpl_pattern = os.path.join(
                self.save_path, "%(playlist_index)s. %(title)s.%(ext)s"
            )
        else:
            outtmpl_pattern = os.path.join(self.save_path, "%(title)s.%(ext)s")

        # *** استدعاء الدالة المعدلة للحصول على الخيارات ***
        # *** Call the modified function to get options ***
        final_format_string, output_ext_hint, core_postprocessors = (
            self._build_format_string()
        )

        ydl_opts = {
            "progress_hooks": [self._my_hook],
            "outtmpl": outtmpl_pattern,
            "nocheckcertificate": True,
            "ignoreerrors": self.is_playlist,
            "merge_output_format": "mp4",  # أو اتركه None إذا كان MP3 هو الهدف Or leave None if MP3 is target? yt-dlp handles it.
            "postprocessors": core_postprocessors,
            "restrictfilenames": False,
            "postprocessor_hooks": [self._postprocessor_hook],
        }

        if self.ffmpeg_path:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_path
        elif core_postprocessors:
            self.status_callback("Warning: FFmpeg needed for conversion but not found.")

        # *** لم نعد بحاجة لتحديد noplaylist بشكل خاص هنا، _build_format_string يتعامل مع الكل ***
        # *** We no longer need to specifically set noplaylist here, _build_format_string handles all ***
        if self.is_playlist and self.playlist_items:
            ydl_opts["playlist_items"] = self.playlist_items
        # Note: yt-dlp handles single video URLs correctly even if noplaylist isn't explicitly True

        if final_format_string:
            ydl_opts["format"] = final_format_string
        elif "format" in ydl_opts:
            del ydl_opts["format"]

        print("Final yt-dlp options:", ydl_opts)
        self.status_callback("Starting download...")
        self.progress_callback(0)

        self._check_cancel("right before calling ydl.download()")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            self._check_cancel("immediately after ydl.download() finished")
        except yt_dlp.utils.DownloadCancelled as e:
            raise DownloadCancelled(str(e)) from e
        except yt_dlp.utils.DownloadError as dl_err:
            error_message = str(dl_err).split("ERROR:")[-1].strip()
            print(f"Downloader yt-dlp DownloadError: {dl_err}")
            self.status_callback(f"Download Error: {error_message}")
        except Exception as e:
            self._log_unexpected_error(e, "during yt-dlp download execution")

    def run(self):
        # --- هذا المنطق يبقى كما هو --- This logic remains the same ---
        try:
            self._download_core()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
        except Exception as e:
            self._log_unexpected_error(e, "in main run loop")
        finally:
            print("Downloader: Reached finally block, calling finished_callback.")
            self.finished_callback()

    def _log_unexpected_error(self, e, context=""):
        # --- هذا المنطق يبقى كما هو --- This logic remains the same ---
        print(f"--- UNEXPECTED ERROR ({context}) ---")
        traceback.print_exc()
        print("------------------------------------")
        self.status_callback(
            f"Unexpected Error ({type(e).__name__})! Check logs for details."
        )
        print(f"Unexpected Error during download ({context}): {e}")
