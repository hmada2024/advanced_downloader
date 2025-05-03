# -- ملف يحتوي على الكلاسات المسؤولة عن التفاعل المباشر مع yt-dlp --
# Purpose: Contains classes that perform the actual work of interacting with yt-dlp.

import contextlib
import os
import yt_dlp
import sys
from pathlib import Path
from .exceptions import DownloadCancelled
import re
import traceback
import time
import humanize

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
            base_path = Path(__file__).resolve().parent.parent
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
            "playlistend": 500, # Limit playlist items fetched initially
            "ignoreerrors": True, # Continue fetching even if some items fail
            "forcejson": True, # Ensure JSON output even on errors
            "skip_download": True, # Only fetch info
        }
        info_dict = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._check_cancel("before calling extract_info")
                info_dict = ydl.extract_info(self.url, download=False)
                self._check_cancel("after calling extract_info")
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e)
            partial_info = None
            if "ERROR:" in error_message:
                error_message = error_message.split("ERROR:")[-1].strip()
            # Attempt to use partial data if available (e.g., some playlist items loaded)
            if getattr(e, "partial", False):
                partial_info = getattr(e, "data", None)
            if partial_info:
                print(f"InfoFetcher yt-dlp DownloadError with partial data: {e}")
                self.success_callback(partial_info)
            else:
                print(f"InfoFetcher yt-dlp DownloadError: {e}")
                self.error_callback(error_message)
            return # Stop processing on error
        except DownloadCancelled:
            raise # Propagate cancellation
        except Exception as e:
            self._extracted_from_run_38(
                'InfoFetcher Unexpected Error: ',
                e,
                'An unexpected error occurred: ',
            )
            return # Stop processing on error

        if info_dict:
            # Clean up potential null entries in playlist due to ignoreerrors
            if "entries" in info_dict and isinstance(info_dict["entries"], list):
                valid_entries = [entry for entry in info_dict["entries"] if entry]
                # Handle case where playlist might appear empty (e.g., private, region-locked)
                if not valid_entries and info_dict.get("extractor_key") == "YoutubeTab":
                    print("InfoFetcher: YouTube playlist seems empty or private.")
                    self.error_callback(
                        "Playlist is empty, private, or could not be accessed."
                    )
                    return
                info_dict["entries"] = valid_entries # Update with only valid entries

            self.status_callback("Information fetched successfully.")
            self.success_callback(info_dict)
        else:
            # URL might be completely invalid or inaccessible
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
        except Exception as e: # Catch unexpected errors from _fetch_info_core
            self._extracted_from_run_38(
                'InfoFetcher FATAL UNEXPECTED Error in run: ',
                e,
                'A critical unexpected error occurred: ',
            )
        finally:
            # Always notify the UI that the operation has concluded
            print("InfoFetcher: Reached finally block, calling finished_callback.")
            self.finished_callback()

    # TODO Rename this here and in `_fetch_info_core` and `run`
    def _extracted_from_run_38(self, arg0, e, arg2):
        print(f"{arg0}{e}")
        traceback.print_exc()
        self.error_callback(f"{arg2}{type(e).__name__}")


# --- كلاس لتنفيذ التحميل ---
class Downloader:
    # --- تعديل: استقبال وتخزين العددين، وإضافة عداد جديد ---
    def __init__(
        self,
        url,
        save_path,
        format_choice,
        quality_format_id,
        is_playlist,
        playlist_items,
        selected_items_count, # <-- تم استقبال العدد المختار
        total_playlist_count, # <-- تم استقبال العدد الكلي
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
        self.selected_items_count = selected_items_count # <-- تخزين العدد المختار
        self.total_playlist_count = total_playlist_count # <-- تخزين العدد الكلي
        self.ffmpeg_path = ffmpeg_path
        self.cancel_event = cancel_event
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.last_downloaded_info = None
        self.final_known_path = None
        self._current_processing_playlist_idx_display = 1 # الفهرس في القائمة الكاملة (للعرض)
        self._last_hook_playlist_index = 0
        self._processed_selected_count = 0 # <-- إضافة: عداد للعناصر المحددة المعالجة (يبدأ من 0)
        self._cleaned_up_path = None
    # --------------------------------------------------------

    def _check_cancel(self, stage=""):
        if self.cancel_event.is_set():
            raise DownloadCancelled(f"Download cancelled {stage}.")

    def _clean_filename(self, filename):
        if not filename: return filename
        cleaned = re.sub(r'[\\/*?:"<>|]', "", filename)
        cleaned = cleaned.replace(":", " -")
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        cleaned = cleaned.rstrip(". ")
        return cleaned or "downloaded_file"

    def _my_hook(self, d):
        """Hook for download progress with detailed status message."""
        try:
            self._check_cancel("during progress hook")
        except DownloadCancelled as e:
            raise yt_dlp.utils.DownloadCancelled(str(e)) from e

        status = d.get("status")
        info_dict = d.get("info_dict", {})
        hook_playlist_index = info_dict.get("playlist_index") # Absolute index (1-based)

        # --- Update internal absolute index counter ---
        if self.is_playlist and hook_playlist_index is not None and hook_playlist_index > self._last_hook_playlist_index:
            print(f"Hook detected transition to playlist index: {hook_playlist_index}. Updating display counter.")
            self._current_processing_playlist_idx_display = hook_playlist_index
            self._last_hook_playlist_index = hook_playlist_index

        # --- Process based on status ---
        if status == "finished":
            if filepath := info_dict.get("filepath") or d.get("filename"):
                self._extracted_from__my_hook_23(filepath, info_dict)
            else:
                print("Hook 'finished' but no filepath found in hook data.")
                self.status_callback("Processing finished (unknown file path).")
            self.progress_callback(1.0)
        elif status == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded_bytes = d.get("downloaded_bytes")

            if downloaded_bytes is not None:
                self._extracted_from__my_hook_57(total_bytes, downloaded_bytes, d)
                                # ----------------------------------------------------

            else:
                # Fallback status (e.g., connecting)
                self.status_callback(f"Status: {d.get('status', 'Connecting')}...")

        elif status == "error":
            self.status_callback("Error during download process reported by yt-dlp.")
            print(f"yt-dlp hook reported error: {d.get('error', 'Unknown yt-dlp error')}")

    # TODO Rename this here and in `_my_hook`
    def _extracted_from__my_hook_57(self, total_bytes, downloaded_bytes, d):
        # Calculate progress for the current file
        progress = 0.0
        percentage_str = "0.0%" # Default percentage string
        if total_bytes and total_bytes > 0:
            progress = max(0.0, min(1.0, downloaded_bytes / total_bytes))
            percentage_str = f"{progress:.1%}"
        self.progress_callback(progress)

        # --- تعديل: بناء الرسالة التفصيلية المطلوبة ---
        # Format sizes
        downloaded_size_str = humanize.naturalsize(downloaded_bytes, binary=True)
        total_size_str = humanize.naturalsize(total_bytes, binary=True) if total_bytes else "Unknown size"

        if speed := d.get("speed"):
            speed_str = f"{humanize.naturalsize(speed, binary=True, gnu=True)}/s"
        else:
            speed_str = "Calculating..."
        # Format ETA
        eta = d.get("eta")
        eta_str = "Calculating..."
        with contextlib.suppress(TypeError, ValueError):
            if eta is not None and isinstance(eta, (int, float)) and eta >= 0:
                # Format seconds remaining
                eta_str = f"{int(round(eta))} seconds remaining" # More direct format
                # Alternatively, use naturaldelta:
                # eta_str = humanize.naturaldelta(eta) + " remaining"

                # --- تعديل: بناء الرسالة كقائمة من الأسطر ---
        status_lines = []
        if self.is_playlist:
            self._extracted_from__extracted_from__my_hook_57_32(status_lines)
        else:
            status_lines.append("Downloading Video") # سطر واحد للفيديو المفرد

        status_lines.extend(
            (
                f"Progress: {percentage_str} ({downloaded_size_str} / {total_size_str})",
                f"Speed: {speed_str} | ETA: {eta_str}",
            )
        )
        # تجميع الأسطر باستخدام "\n"
        status_msg = "\n".join(status_lines)
        self.status_callback(status_msg)

    # TODO Rename this here and in `_extracted_from__my_hook_57`
    def _extracted_from__extracted_from__my_hook_57_32(self, status_lines):
        current_absolute_index = self._current_processing_playlist_idx_display
        total_absolute_str = f"out of {self.total_playlist_count} total" if self.total_playlist_count > 0 else ""
        status_lines.append(f"Video {current_absolute_index} {total_absolute_str}") # السطر الأول: الفيديو الحالي/الإجمالي

        index_in_selection = self._processed_selected_count + 1
        index_in_selection = min(index_in_selection, self.selected_items_count)
        remaining_in_selection = max(0, self.selected_items_count - self._processed_selected_count)
        status_lines.append(f"Selected: {index_in_selection} of {self.selected_items_count} ({remaining_in_selection} remaining)") # السطر الثاني: تقدم التحديد
        # -------------------------------------------

    def _extracted_from__my_hook_23(self, filepath, info_dict):
        self.final_known_path = filepath; self.last_downloaded_info = info_dict; print(f"Hook 'finished': Path reported '{filepath}'.")
        base_filename = os.path.basename(filepath); final_ext_present = any(base_filename.lower().endswith(ext) for ext in ['.mp4', '.mp3', '.mkv', '.webm', '.opus', '.ogg'])
        title = info_dict.get("title"); display_name = self._clean_filename(title or base_filename)
        if final_ext_present:
            status_msg = f"Finished: {display_name}"; self._processed_selected_count += 1; print(f"Processed selected items count incremented to: {self._processed_selected_count}")
        else: status_msg = f"Processing: {display_name}..."
        self.status_callback(status_msg)

    # --- باقي الدوال (_build_format_string, _download_core, _cleanup_final_file, run, _log_unexpected_error) ---
    # --- تبقى كما هي ---
    def _build_format_string(self):
        format_choice_lower = self.format_choice.lower()
        output_ext = "mp4"
        postprocessors = []
        final_format_string = None
        if not self.is_playlist and self.quality_format_id:
            final_format_string = self.quality_format_id; print(f"Using specific quality format ID: {self.quality_format_id}")
            if "audio (mp3)" in format_choice_lower:
                print("Warning: MP3 format chosen despite specific quality ID selection. Will attempt audio extraction.")
                output_ext = "mp3";
                if self.ffmpeg_path: postprocessors.append({'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'})
                else: print("Error: MP3 conversion requires FFmpeg, which was not found."); output_ext = None
        elif "audio (mp3)" in format_choice_lower:
            final_format_string = "bestaudio/best"; output_ext = "mp3"
            if self.ffmpeg_path: postprocessors.append({'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}); print("Selecting best audio for MP3 conversion.")
            else: print("Warning: MP3 requested but FFmpeg not found. Downloading best audio format."); output_ext = None
        elif self.is_playlist:
             final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"; output_ext = "mp4"; print("Using default playlist format (max 720p MP4)")
        else:
            height_limit = None
            if "<= 720p" in format_choice_lower: height_limit = 720
            elif "<= 480p" in format_choice_lower: height_limit = 480
            elif "<= 360p" in format_choice_lower: height_limit = 360
            if height_limit: final_format_string = f"bestvideo[height<={height_limit}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height_limit}]+bestaudio/best[height<={height_limit}][ext=mp4]/best[height<={height_limit}]"; print(f"Using general format: max {height_limit}p MP4")
            else: final_format_string = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"; print("Using general format: best available MP4 (1080p+)")
            output_ext = "mp4"
        return final_format_string, output_ext, postprocessors

    def _download_core(self):
        # Reset state variables for this download attempt
        self.last_downloaded_info = None
        self.final_known_path = None;
        self._current_processing_playlist_idx_display = 1 # Reset display counter
        self._last_hook_playlist_index = 0
        self._processed_selected_count = 0 # Reset selected counter
        self._cleaned_up_path = None
        self._check_cancel("before starting download")
        if self.is_playlist: outtmpl_pattern = os.path.join(self.save_path, "%(playlist_index)s. %(title)s.%(ext)s")
        else: outtmpl_pattern = os.path.join(self.save_path, "%(title)s.%(ext)s")
        final_format_string, output_ext_hint, core_postprocessors = self._build_format_string()
        ydl_opts = {
            'progress_hooks': [self._my_hook], 'outtmpl': outtmpl_pattern, 'nocheckcertificate': True,
            'ignoreerrors': self.is_playlist, 'merge_output_format': 'mp4', 'postprocessors': core_postprocessors,
            'restrictfilenames': False, #'postprocessor_args': {'ffmpeg': ['-vcodec', 'copy', '-acodec', 'copy']},
        }
        if self.ffmpeg_path: ydl_opts['ffmpeg_location'] = self.ffmpeg_path
        elif core_postprocessors: self.status_callback("Warning: FFmpeg needed for conversion but not found.")
        if self.is_playlist:
            ydl_opts['noplaylist'] = False;
            if self.playlist_items: ydl_opts['playlist_items'] = self.playlist_items
        else: ydl_opts['noplaylist'] = True
        if final_format_string: ydl_opts['format'] = final_format_string
        elif 'format' in ydl_opts: del ydl_opts['format']
        print("Final yt-dlp options:", ydl_opts)
        self.status_callback("Starting download...")
        self.progress_callback(0)
        self._check_cancel("right before calling ydl.download()")
        download_successful = False
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([self.url])
            download_successful = True; self._check_cancel("immediately after ydl.download() finished")
        except yt_dlp.utils.DownloadCancelled as e:
            raise DownloadCancelled(str(e)) from e
        except yt_dlp.utils.DownloadError as dl_err:
             error_message = str(dl_err).split('ERROR:')[-1].strip(); print(f"Downloader yt-dlp DownloadError: {dl_err}"); self.status_callback(f"Download Error: {error_message}")
        except Exception as e: self._log_unexpected_error(e, "during yt-dlp download execution")
        self._check_cancel("after download block completion")
        if not download_successful: print("Download process reported errors or was unsuccessful. Skipping final cleanup."); return
        try: time.sleep(0.2); self._cleanup_final_file()
        except Exception as e: self._log_unexpected_error(e, "during final file cleanup"); self.status_callback("Warning: Download complete, but filename cleanup failed.")

    def _cleanup_final_file(self):
        if self._cleaned_up_path: print(f"Cleanup skipped: Already cleaned path '{self._cleaned_up_path}'"); return
        print("Attempting final file cleanup...");
        if not self.final_known_path: print("Cleanup skipped: No final file path was reported by hooks."); self.status_callback("Warning: Download finished, but final file path is unknown."); return
        expected_final_path_obj = Path(self.final_known_path)
        print(f"Cleanup: Checking final path '{expected_final_path_obj}'")
        time.sleep(0.4)
        if not expected_final_path_obj.exists():
            print(f"Cleanup Error: Expected final file '{expected_final_path_obj}' not found after delay.")
            if self.last_downloaded_info:
                pl_idx = self.last_downloaded_info.get('playlist_index'); pl_idx_str = f"{pl_idx}." if pl_idx is not None else ""
                expected_ext = self._build_format_string()[1] or 'mp4'; expected_name = f"{pl_idx_str}{self.last_downloaded_info.get('title', 'untitled')}.{expected_ext}"
                alt_path = expected_final_path_obj.parent / self._clean_filename(expected_name); print(f"Cleanup: Checking alternative path '{alt_path}'")
                if alt_path.exists(): print(f"Found file at alternative path: {alt_path}"); expected_final_path_obj = alt_path
                else: print(f"Cleanup Error: Alternative path '{alt_path}' also not found."); self.status_callback(f"Error: Processing completed but final file '{expected_final_path_obj.name}' is missing."); return
            else:
                print("Cleanup Error: File not found and no info to guess alternative.")
                self.status_callback(f"Error: Processing completed but final file '{expected_final_path_obj.name}' is missing.")
                return
        current_basename = expected_final_path_obj.name
        target_basename = current_basename
        if self.last_downloaded_info:
            base_title = self.last_downloaded_info.get('title', ''); base_ext = expected_final_path_obj.suffix.lstrip('.')
            if self.is_playlist:
                 playlist_index = self.last_downloaded_info.get('playlist_index')
                 if playlist_index is not None: target_basename = f"{playlist_index}. {base_title}.{base_ext}"
                 else: target_basename = f"{base_title}.{base_ext}"
            else: target_basename = f"{base_title}.{base_ext}"
            target_basename = self._clean_filename(target_basename)
        else: target_basename = self._clean_filename(current_basename)
        new_final_filepath_obj = expected_final_path_obj.with_name(target_basename)
        final_message = f"Download complete: {target_basename}"
        if new_final_filepath_obj != expected_final_path_obj:
            print(f"Attempting rename: '{current_basename}' -> '{target_basename}'")
            try:
                if expected_final_path_obj.exists(): expected_final_path_obj.rename(new_final_filepath_obj); print(f"Rename successful: '{new_final_filepath_obj}'"); self._cleaned_up_path = str(new_final_filepath_obj)
                else: print(f"File disappeared before rename: {expected_final_path_obj}"); final_message = f"Warning: Download ok, but file missing before rename ({current_basename})"; self._cleaned_up_path = None
            except OSError as e: print(f"Error during final rename for '{current_basename}': {e}"); final_message = f"Download complete (rename failed): {current_basename}"; self._cleaned_up_path = str(expected_final_path_obj)
        else: print("Filename already correct. No rename needed."); self._cleaned_up_path = str(expected_final_path_obj)
        # Status updated by hook "Finished: ..." message

    def run(self):
        """Executes the download process, handling errors and final callback."""
        download_error_occurred = False; self._cleaned_up_path = None
        try: self._download_core()
        except DownloadCancelled as e: self.status_callback(str(e)); print(e); download_error_occurred = True
        except Exception as e: self._log_unexpected_error(e, "in main run loop"); download_error_occurred = True
        finally: print("Downloader: Reached finally block, calling finished_callback."); self.finished_callback()

    def _log_unexpected_error(self, e, context=""):
        """Logs unexpected errors with traceback and updates status."""
        print(f"--- UNEXPECTED ERROR ({context}) ---"); traceback.print_exc(); print("------------------------------------")
        self.status_callback(f"Unexpected Error ({type(e).__name__})! Check logs for details."); print(f"Unexpected Error during download ({context}): {e}")