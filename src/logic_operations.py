# -- ملف يحتوي على الكلاسات المسؤولة عن التفاعل المباشر مع yt-dlp --
# Purpose: Contains classes that perform the actual work of interacting with yt-dlp.

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
            # الحصول على مسار المجلد الذي يحتوي على logic_operations.py ثم الصعود مرتين
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
            "playlistend": 500,
            "ignoreerrors": True,
            "forcejson": True,
            "skip_download": True,
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
            if getattr(e, "partial", False):
                partial_info = getattr(e, "data", None)
            if partial_info:
                print(f"InfoFetcher yt-dlp DownloadError with partial data: {e}")
                self.success_callback(partial_info)  # Try to use partial data
            else:
                print(f"InfoFetcher yt-dlp DownloadError: {e}")
                self.error_callback(error_message)
            return  # Stop processing on error
        except DownloadCancelled:
            raise  # Propagate cancellation
        except Exception as e:
            print(f"InfoFetcher Unexpected Error: {e}")
            traceback.print_exc()
            self.error_callback(f"An unexpected error occurred: {type(e).__name__}")
            return  # Stop processing on error
        if info_dict:
            # Clean up potential null entries from ignoreerrors
            if "entries" in info_dict and isinstance(info_dict["entries"], list):
                valid_entries = [entry for entry in info_dict["entries"] if entry]
                # Handle case where playlist is empty or private
                if (
                    not valid_entries and info_dict.get("extractor_key") == "YoutubeTab"
                ):  # Check specific extractor if needed
                    print("InfoFetcher: YouTube playlist seems empty or private.")
                    self.error_callback(
                        "Playlist is empty, private, or could not be accessed."
                    )
                    return
                info_dict["entries"] = valid_entries  # Update with only valid entries

            self.status_callback("Information fetched successfully.")
            self.success_callback(info_dict)
        else:
            # This might happen if the URL is completely invalid
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
        except Exception as e:  # Catch any unexpected errors from _fetch_info_core
            print(f"InfoFetcher FATAL UNEXPECTED Error in run: {e}")
            traceback.print_exc()
            # Ensure error callback is called if not already
            self.error_callback(
                f"A critical unexpected error occurred: {type(e).__name__}"
            )
        finally:
            # This block ALWAYS runs, regardless of success, error, or cancellation
            print("InfoFetcher: Reached finally block, calling finished_callback.")
            self.finished_callback()  # Notify UI that the fetch operation has concluded


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
        # Counter for the *currently processing* playlist item index (1-based for display)
        self._current_processing_playlist_idx_display = 1  # Start at 1 for display
        self._last_hook_playlist_index = 0  # Track last index seen from hook
        self._cleaned_up_path = None

    def _check_cancel(self, stage=""):
        if self.cancel_event.is_set():
            raise DownloadCancelled(f"Download cancelled {stage}.")

    def _clean_filename(self, filename):
        if not filename:
            return filename
        # Remove potentially problematic characters for Windows filenames
        cleaned = re.sub(r'[\\/*?:"<>|]', "", filename)
        # Replace colons usually used in timestamps or titles
        cleaned = cleaned.replace(":", " -")
        # Replace multiple whitespace characters with a single space
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        # Remove trailing dots or spaces which can cause issues on Windows
        cleaned = cleaned.rstrip(". ")
        # Ensure filename is not empty after cleaning
        if not cleaned:
            return "downloaded_file"
        return cleaned

    def _my_hook(self, d):
        """Hook for download progress, managing state and counters accurately."""
        try:
            self._check_cancel("during progress hook")
        except DownloadCancelled as e:
            # Re-raise as an exception yt-dlp understands to stop the download cleanly
            raise yt_dlp.utils.DownloadCancelled(str(e))

        status = d.get("status")
        info_dict = d.get("info_dict", {})
        hook_playlist_index = info_dict.get(
            "playlist_index"
        )  # Index from yt-dlp (1-based)

        # --- Update internal counter based on hook's playlist_index ---
        if self.is_playlist and hook_playlist_index is not None:
            if hook_playlist_index > self._last_hook_playlist_index:
                print(
                    f"Hook detected transition to playlist index: {hook_playlist_index}. Updating display counter."
                )
                # Update the display counter only when yt-dlp reports moving to the next item
                self._current_processing_playlist_idx_display = hook_playlist_index
                self._last_hook_playlist_index = hook_playlist_index
            # If hook index is same or less, don't change display counter (still processing same item)

        # --- Process based on status ---
        if status == "finished":
            filepath = info_dict.get("filepath") or d.get("filename")
            if filepath:
                self.final_known_path = (
                    filepath  # Store the reported path (might be temp or final)
                )
                self.last_downloaded_info = info_dict  # Store associated info
                print(f"Hook 'finished': Path reported '{filepath}'.")

                base_filename = os.path.basename(filepath)
                # Check if it's likely the final merged/converted file
                final_ext_present = any(
                    base_filename.lower().endswith(ext)
                    for ext in [".mp4", ".mp3", ".mkv", ".webm", ".opus", ".ogg"]
                )
                title = info_dict.get("title")
                display_name = self._clean_filename(title if title else base_filename)

                if final_ext_present:
                    # This signifies the *completion* of processing for the current item
                    status_msg = f"Finished: {display_name}"
                    # The display counter should already be correct from the 'downloading' phase update
                else:
                    # This is likely an intermediate file (e.g., video part before merge)
                    status_msg = f"Processing: {display_name}..."

                self.status_callback(status_msg)
                self.progress_callback(
                    1.0
                )  # Progress is 100% for this *specific file/stage*
            else:
                # Should ideally not happen if status is 'finished'
                print("Hook 'finished' but no filepath found in hook data.")
                self.status_callback("Processing finished (unknown file path).")
                self.progress_callback(1.0)

        elif status == "downloading":
            total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded_bytes = d.get("downloaded_bytes")

            if downloaded_bytes is not None:
                # Calculate progress
                progress = 0.0
                percent_str = "N/A"
                if total_bytes and total_bytes > 0:
                    progress = max(0.0, min(1.0, downloaded_bytes / total_bytes))
                    percent_str = f"{progress:.1%}"  # Format as percentage
                self.progress_callback(progress)  # Update progress bar

                # Format sizes
                downloaded_size_str = humanize.naturalsize(
                    downloaded_bytes, binary=True
                )
                total_size_str = (
                    humanize.naturalsize(total_bytes, binary=True)
                    if total_bytes
                    else "Unknown size"
                )

                # Format speed
                speed = d.get("speed")
                speed_str = "Calculating..."
                if speed:
                    speed_str = (
                        humanize.naturalsize(speed, binary=True, gnu=True) + "/s"
                    )  # e.g., "1.2 MiB/s"

                # Format ETA
                eta = d.get("eta")
                eta_str = "Calculating..."
                try:
                    # Only show eta if it's a valid number (seconds)
                    if eta is not None and isinstance(eta, (int, float)) and eta >= 0:
                        eta_str = humanize.naturaldelta(eta) + " remaining"
                except (TypeError, ValueError):
                    pass  # Keep "Calculating..." on error

                # Construct status message prefix for playlists
                status_prefix = ""
                if self.is_playlist and self.playlist_items_count > 0:
                    # Use the updated display counter
                    status_prefix = f"Item {self._current_processing_playlist_idx_display}/{self.playlist_items_count} - "

                # Assemble the full status message
                status_msg = f"{status_prefix}{percent_str} ({downloaded_size_str} / {total_size_str}) - Speed: {speed_str} - {eta_str}"
                self.status_callback(status_msg)

            else:
                # Fallback status if byte counts aren't available (e.g., connecting)
                self.status_callback(f"Status: {d.get('status', 'Connecting')}...")

        elif status == "error":
            # Report errors encountered during the download process by yt-dlp
            self.status_callback("Error during download process reported by yt-dlp.")
            print(
                f"yt-dlp hook reported error: {d.get('error', 'Unknown yt-dlp error')}"
            )
            # Consider if you want to raise an exception here to stop immediately

    def _build_format_string(self):
        """Builds the format selection string and determines output extension."""
        format_choice_lower = self.format_choice.lower()
        output_ext = "mp4"  # Default to mp4
        postprocessors = []
        final_format_string = None

        # Priority 1: Specific quality ID selected for a single video
        if not self.is_playlist and self.quality_format_id:
            final_format_string = self.quality_format_id
            print(f"Using specific quality format ID: {self.quality_format_id}")
            # Attempting to guess extension from format ID is complex. Let yt-dlp handle it usually.
            # However, if user explicitly wants MP3, override extension and add postprocessor.
            if "audio (mp3)" in format_choice_lower:
                print(
                    "Warning: MP3 format chosen despite specific quality ID selection. Will attempt audio extraction."
                )
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
                    print("Error: MP3 conversion requires FFmpeg, which was not found.")
                    # Decide how to handle this: fail, warn, or let yt-dlp try without conversion?
                    # For now, let it proceed, yt-dlp might download best audio in another format.
                    output_ext = None  # Let yt-dlp decide extension

        # Priority 2: General format choice (or playlist)
        else:
            if "audio (mp3)" in format_choice_lower:
                final_format_string = "bestaudio/best"  # Select best audio available
                output_ext = "mp3"
                if self.ffmpeg_path:
                    postprocessors.append(
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    )
                    print("Selecting best audio for MP3 conversion.")
                else:
                    print(
                        "Warning: MP3 requested but FFmpeg not found. Downloading best audio format."
                    )
                    output_ext = None  # Let yt-dlp decide extension
            elif self.is_playlist:
                # Default for playlists: Max 720p video, best audio, merged into MP4
                final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
                output_ext = "mp4"
                print("Using default playlist format (max 720p MP4)")
            else:
                # Single video using general format dropdown
                height_limit = None
                if "<= 720p" in format_choice_lower:
                    height_limit = 720
                elif "<= 480p" in format_choice_lower:
                    height_limit = 480
                elif "<= 360p" in format_choice_lower:
                    height_limit = 360

                if height_limit:
                    final_format_string = f"bestvideo[height<={height_limit}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height_limit}]+bestaudio/best[height<={height_limit}][ext=mp4]/best[height<={height_limit}]"
                    print(f"Using general format: max {height_limit}p MP4")
                else:  # Default "Best Quality MP4 (<= 1080p+)"
                    final_format_string = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
                    print("Using general format: best available MP4 (1080p+)")
                output_ext = "mp4"

        return final_format_string, output_ext, postprocessors

    def _download_core(self):
        """Sets up yt-dlp options and initiates the download."""
        # Reset state variables for this download attempt
        self.last_downloaded_info = None
        self.final_known_path = None
        self._current_processing_playlist_idx_display = 1  # Reset display counter
        self._last_hook_playlist_index = 0  # Reset hook index tracker
        self._cleaned_up_path = None
        self._check_cancel("before starting download")

        # Build output path template
        # Using os.path.join for cross-platform compatibility
        # Filename pattern includes index (if playlist) and title. Extension added by yt-dlp.
        if self.is_playlist:
            outtmpl_pattern = os.path.join(
                self.save_path, "%(playlist_index)s. %(title)s.%(ext)s"
            )
        else:
            outtmpl_pattern = os.path.join(self.save_path, "%(title)s.%(ext)s")

        # Get format selection string, output extension hint, and postprocessors
        final_format_string, output_ext_hint, core_postprocessors = (
            self._build_format_string()
        )

        # --- yt-dlp Options ---
        ydl_opts = {
            "progress_hooks": [self._my_hook],
            "outtmpl": outtmpl_pattern,  # Template for output filename
            "nocheckcertificate": True,  # Ignore SSL certificate errors
            "ignoreerrors": self.is_playlist,  # Continue download if one item in playlist fails
            "merge_output_format": "mp4",  # Prefer MP4 container when merging formats
            "postprocessors": core_postprocessors,  # Audio conversion if requested
            "restrictfilenames": False,  # Allow spaces and wider range of characters in filenames
            # 'postprocessor_args': {             # Arguments for FFmpeg postprocessing (e.g., faster merge)
            #      'ffmpeg': ['-vcodec', 'copy', '-acodec', 'copy'] # If codecs are compatible
            # },
            # 'writethumbnail': True,             # Download thumbnail image alongside video (optional)
            # 'writeinfojson': True,            # Create .info.json file with metadata (optional)
            # 'socket_timeout': 30,             # Network timeout in seconds (optional)
        }

        # Add FFmpeg location if found
        if self.ffmpeg_path:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_path
        elif core_postprocessors:  # Warn if FFmpeg is needed but missing
            self.status_callback("Warning: FFmpeg needed for conversion but not found.")

        # Playlist specific options
        if self.is_playlist:
            ydl_opts["noplaylist"] = False  # Process as a playlist
            if self.playlist_items:
                ydl_opts["playlist_items"] = (
                    self.playlist_items
                )  # Download specific items
        else:
            ydl_opts["noplaylist"] = True  # Process as a single URL

        # Add the format selection string if one was determined
        if final_format_string:
            ydl_opts["format"] = final_format_string
        # Ensure 'format' key is removed if no specific format is needed (let yt-dlp choose default best)
        elif "format" in ydl_opts:
            del ydl_opts["format"]

        # Print final options for debugging (optional)
        print("Final yt-dlp options:", ydl_opts)

        # --- Start Download ---
        self.status_callback("Starting download...")
        self.progress_callback(0)
        self._check_cancel("right before calling ydl.download()")

        download_successful = False
        try:
            # Use yt-dlp's context manager
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])  # Pass URL as a list
            # If no exceptions were raised by yt-dlp, consider it successful so far
            download_successful = True
            self._check_cancel(
                "immediately after ydl.download() finished"
            )  # Check cancellation again

        except yt_dlp.utils.DownloadCancelled as e:
            # Handle cancellation requested via the hook
            raise DownloadCancelled(str(e))  # Re-raise our custom exception
        except yt_dlp.utils.DownloadError as dl_err:
            # Handle specific download errors from yt-dlp
            error_message = str(dl_err).split("ERROR:")[-1].strip()
            print(f"Downloader yt-dlp DownloadError: {dl_err}")
            self.status_callback(f"Download Error: {error_message}")
            # Keep download_successful as False
        except Exception as e:
            # Handle any other unexpected errors during download
            self._log_unexpected_error(e, "during yt-dlp download execution")
            # Keep download_successful as False

        # Final cancellation check after the download block
        self._check_cancel("after download block completion")

        # --- Post-Download Cleanup ---
        if not download_successful:
            print(
                "Download process reported errors or was unsuccessful. Skipping final cleanup."
            )
            return  # Exit if download failed or was cancelled before completion

        # If download seemed successful, attempt final filename cleanup
        try:
            time.sleep(0.2)  # Small delay to allow file handles to close
            self._cleanup_final_file()
        except Exception as e:
            self._log_unexpected_error(e, "during final file cleanup")
            # Inform user, but download itself might be okay
            self.status_callback(
                "Warning: Download complete, but filename cleanup failed."
            )

    def _cleanup_final_file(self):
        """Cleans the filename of the final downloaded file based on stored info."""
        if self._cleaned_up_path:  # Avoid cleaning the same path multiple times
            print(f"Cleanup skipped: Already cleaned path '{self._cleaned_up_path}'")
            return

        print("Attempting final file cleanup...")
        if not self.final_known_path:
            print("Cleanup skipped: No final file path was reported by hooks.")
            # This might indicate an issue where the 'finished' hook didn't run correctly
            self.status_callback(
                "Warning: Download finished, but final file path is unknown."
            )
            return

        expected_final_path_obj = Path(self.final_known_path)
        print(f"Cleanup: Checking final path '{expected_final_path_obj}'")

        # Add a slightly longer delay and check existence carefully
        time.sleep(0.4)  # Increased delay
        if not expected_final_path_obj.exists():
            print(
                f"Cleanup Error: Expected final file '{expected_final_path_obj}' not found after delay."
            )
            # Try to guess the filename based on last known info_dict as a fallback
            if self.last_downloaded_info:
                pl_idx = self.last_downloaded_info.get("playlist_index")
                pl_idx_str = (
                    f"{pl_idx}." if pl_idx is not None else ""
                )  # Add dot only if index exists
                # Use expected extension based on format or default to mp4
                expected_ext = self._build_format_string()[1] or "mp4"
                expected_name = f"{pl_idx_str}{self.last_downloaded_info.get('title', 'untitled')}.{expected_ext}"
                alt_path = expected_final_path_obj.parent / self._clean_filename(
                    expected_name
                )
                print(f"Cleanup: Checking alternative path '{alt_path}'")
                if alt_path.exists():
                    print(f"Found file at alternative path: {alt_path}")
                    expected_final_path_obj = alt_path  # Use the alternative path
                else:
                    print(
                        f"Cleanup Error: Alternative path '{alt_path}' also not found."
                    )
                    self.status_callback(
                        f"Error: Processing completed but final file '{expected_final_path_obj.name}' is missing."
                    )
                    return
            else:
                # No info to guess alternative path
                print(
                    f"Cleanup Error: File not found and no info to guess alternative."
                )
                self.status_callback(
                    f"Error: Processing completed but final file '{expected_final_path_obj.name}' is missing."
                )
                return

        # --- Determine Target Filename ---
        current_basename = expected_final_path_obj.name
        target_basename = current_basename  # Default to current name
        if self.last_downloaded_info:
            base_title = self.last_downloaded_info.get("title", "")
            # Get extension from the actual file object as it exists
            base_ext = expected_final_path_obj.suffix.lstrip(".")
            if self.is_playlist:
                playlist_index = self.last_downloaded_info.get("playlist_index")
                # Use the reliable index from info_dict if available
                if playlist_index is not None:
                    target_basename = f"{playlist_index}. {base_title}.{base_ext}"
                else:  # Fallback if index is missing for some reason
                    target_basename = f"{base_title}.{base_ext}"
            else:  # Single video
                target_basename = f"{base_title}.{base_ext}"
            # Clean the potentially constructed target name
            target_basename = self._clean_filename(target_basename)
        else:
            # If no info, just clean the current name reported by the hook
            target_basename = self._clean_filename(current_basename)

        # --- Perform Rename (if necessary) ---
        new_final_filepath_obj = expected_final_path_obj.with_name(target_basename)
        final_message = f"Download complete: {target_basename}"  # Success message assumes rename works or isn't needed

        if new_final_filepath_obj != expected_final_path_obj:
            print(f"Attempting rename: '{current_basename}' -> '{target_basename}'")
            try:
                # Final check for existence before renaming
                if expected_final_path_obj.exists():
                    expected_final_path_obj.rename(new_final_filepath_obj)
                    print(f"Rename successful: '{new_final_filepath_obj}'")
                    self._cleaned_up_path = str(
                        new_final_filepath_obj
                    )  # Store cleaned path
                else:
                    # File might have been deleted externally between check and rename
                    print(f"File disappeared before rename: {expected_final_path_obj}")
                    final_message = f"Warning: Download ok, but file missing before rename ({current_basename})"
                    self._cleaned_up_path = None  # Rename failed
            except OSError as e:
                # Handle potential OS errors during rename (e.g., permissions, file in use)
                print(f"Error during final rename for '{current_basename}': {e}")
                final_message = f"Download complete (rename failed): {current_basename}"
                # Assume the original path is the final one, even if unclean
                self._cleaned_up_path = str(expected_final_path_obj)
        else:
            # No rename needed, filename was already clean/correct
            print("Filename already correct. No rename needed.")
            self._cleaned_up_path = str(expected_final_path_obj)  # Store the path

        # Note: The status bar is updated by the 'finished' hook message ("Finished: ...")
        # We don't need to call self.status_callback(final_message) here usually.

    def run(self):
        """Executes the download process, handling errors and final callback."""
        download_error_occurred = False
        self._cleaned_up_path = None  # Reset cleaned path tracker

        try:
            self._download_core()
        except DownloadCancelled as e:
            self.status_callback(str(e))
            print(e)
            download_error_occurred = (
                True  # Treat cancellation as non-successful completion
            )
        except Exception as e:
            # Catch any other unexpected error from _download_core or _cleanup_final_file
            self._log_unexpected_error(e, "in main run loop")
            download_error_occurred = True
        finally:
            # Ensure finished_callback is always called
            print("Downloader: Reached finally block, calling finished_callback.")
            self.finished_callback()
            # Final status message is typically set by the hook or error handlers

    def _log_unexpected_error(self, e, context=""):
        """Logs unexpected errors with traceback and updates status."""
        print(f"--- UNEXPECTED ERROR ({context}) ---")
        traceback.print_exc()
        print("------------------------------------")
        # Provide a user-friendly error message, avoid showing raw exception details directly
        self.status_callback(
            f"Unexpected Error ({type(e).__name__})! Check logs for details."
        )
        print(f"Unexpected Error during download ({context}): {e}")
