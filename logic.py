import os
import yt_dlp
import threading
import sys
import time
from pathlib import Path

# Define custom exception for cancellation
class DownloadCancelled(Exception):
    pass

class DownloaderLogic:
    def __init__(self, status_callback, progress_callback, finished_callback, info_success_callback, info_error_callback):
        """
        Initialize the downloader logic.
        Args:
            status_callback: Function to update status label.
            progress_callback: Function to update progress bar.
            finished_callback: Function called when download/info task finishes/fails/cancels.
            info_success_callback: Function called when video info is successfully fetched.
            info_error_callback: Function called when fetching info fails.
        """
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.info_success_callback = info_success_callback
        self.info_error_callback = info_error_callback

        self.ffmpeg_path = self._find_ffmpeg()
        self.cancel_event = threading.Event()
        self.current_thread = None # To keep track of the running thread

    def _find_ffmpeg(self):
        bundled_path = Path(sys.argv[0]).parent / "ffmpeg_bin" / "ffmpeg.exe"
        if bundled_path.is_file():
            print(f"Found bundled ffmpeg: {bundled_path}")
            return str(bundled_path)
        print("Warning: Bundled ffmpeg not found. yt-dlp might rely on system PATH or fail some operations.")
        return None

    def _my_hook(self, d):
        """Progress hook for yt-dlp, checks for cancellation."""
        # Check for cancellation signal frequently
        if self.cancel_event.is_set():
            raise DownloadCancelled("Download cancelled by user.")

        if d['status'] == 'downloading':
            # Extract progress info safely using .get()
            filename = d.get('filename', 'N/A')
            total_bytes_str = d.get('_total_bytes_str', 'N/A')
            downloaded_bytes = d.get('downloaded_bytes')
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            speed_str = d.get('_speed_str', 'N/A')
            eta_str = d.get('_eta_str', 'N/A')
            percent_str = d.get('_percent_str', 'N/A').strip()

            if total_bytes and downloaded_bytes:
                progress = downloaded_bytes / total_bytes
                self.progress_callback(progress)
                # More detailed status
                status_msg = f"Downloading: {percent_str} ({d.get('_downloaded_bytes_str', 'N/A')}/{total_bytes_str}) at {speed_str}, ETA: {eta_str}"
                self.status_callback(status_msg)
            else: # Handle cases where progress is less clear (e.g., some live streams)
                 self.status_callback(f"Status: {d['status']} - {filename}")

        elif d['status'] == 'finished':
            filename = d.get('filename', 'N/A')
            total_bytes_str = d.get('_total_bytes_str', 'N/A')
            self.status_callback(f"Finished downloading '{os.path.basename(filename)}' ({total_bytes_str}). Post-processing...")
            self.progress_callback(1.0)
        elif d['status'] == 'error':
            self.status_callback("Error during download process.")
            print(f"yt-dlp hook error: {d}")
        # Add more statuses if needed (e.g., 'processing', 'warning')

    def _execute_info_fetch(self, url):
        """Fetches video/playlist information without downloading."""
        try:
            self.status_callback("Fetching information...")
            self.progress_callback(0) # Reset progress
            ydl_opts = {
                'quiet': True, # Suppress yt-dlp console output during info fetch
                'nocheckcertificate': True,
                'extract_flat': 'in_playlist', # Faster for playlists, gets basic entry info
                 # 'dump_single_json': True, # Alternative way to get info
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                 # Check for cancellation before network request
                if self.cancel_event.is_set():
                    raise DownloadCancelled("Info fetch cancelled.")
                info_dict = ydl.extract_info(url, download=False)

             # Check again after potentially long network request
            if self.cancel_event.is_set():
                 raise DownloadCancelled("Info fetch cancelled.")

            self.status_callback("Information fetched successfully.")
            self.info_success_callback(info_dict) # Send results to UI

        except DownloadCancelled as e:
             self.status_callback(str(e))
             print(str(e))
        except yt_dlp.utils.DownloadError as e:
            error_message = str(e).split('ERROR:')[-1].strip()
            self.status_callback(f"Info Error: {error_message}")
            self.info_error_callback(error_message)
            print(f"yt-dlp DownloadError during info fetch: {e}")
        except Exception as e:
            self.status_callback(f"An unexpected error occurred during info fetch: {type(e).__name__}")
            self.info_error_callback(f"Unexpected error: {e}")
            print(f"Unexpected Error during info fetch: {e}")
        finally:
            self.finished_callback() # Signal UI that the task is done (success or fail)
            self.current_thread = None

    def start_info_fetch(self, url):
        """Starts the information fetching process in a new thread."""
        if not url:
            self.status_callback("Error: Please enter a URL.")
            self.info_error_callback("URL is empty.")
            self.finished_callback()
            return

        if self.current_thread and self.current_thread.is_alive():
             self.status_callback("Error: Another operation is already in progress.")
             return

        self.cancel_event.clear() # Reset cancellation flag for the new operation
        self.current_thread = threading.Thread(
            target=self._execute_info_fetch,
            args=(url,),
            daemon=True
        )
        self.current_thread.start()


    def _execute_download(self, url, save_path, format_choice, quality_format_id, is_playlist, playlist_items):
        """Executes the download in a separate thread."""
        try:
            ydl_opts = {
                'progress_hooks': [self._my_hook],
                'outtmpl': os.path.join(save_path, '%(title)s [%(id)s].%(ext)s'), # Include ID for uniqueness
                'nocheckcertificate': True,
                'ignoreerrors': is_playlist, # Continue playlist download on error
                # Keep cookies persistent if needed for logins (advanced)
                # 'cookiefile': 'cookies.txt',
                # 'writedesktopconf': False, # Avoid creating .desktop files on Linux
            }

            # --- Set FFmpeg Path ---
            if self.ffmpeg_path:
                ydl_opts['ffmpeg_location'] = self.ffmpeg_path
            else:
                 # Warn only if format requiring ffmpeg is likely selected
                 if format_choice == 'Audio (mp3)' or quality_format_id: # Assuming specific quality might need merge
                     self.status_callback("Warning: FFmpeg not found. MP3 conversion or format merging might fail.")

            # --- Handle Playlist Options ---
            if is_playlist:
                ydl_opts['noplaylist'] = False
                if playlist_items: # If specific items were selected
                    ydl_opts['playlist_items'] = playlist_items
                else: # Download all items in playlist
                    pass # Default behavior
            else:
                 ydl_opts['noplaylist'] = True


            # --- Format Selection Logic ---
            postprocessors = []
            if quality_format_id:
                # User selected a specific format ID after fetching info
                ydl_opts['format'] = quality_format_id
                # We might still need MP3 conversion if audio was selected specifically
                if format_choice == 'Audio (mp3)':
                     # Check if the selected format is audio-only already
                     # This requires parsing format_id or having more info, complex.
                     # Safer approach: always add postprocessor if MP3 is the target.
                     postprocessors.append({
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                     })
                     ydl_opts['outtmpl'] = os.path.join(save_path, '%(title)s [%(id)s].mp3') # Ensure MP3 extension
            else:
                # User selected a generic format before fetching info or didn't fetch
                if format_choice == 'Audio (mp3)':
                    ydl_opts['format'] = 'bestaudio/best'
                    postprocessors.append({
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    })
                    ydl_opts['outtmpl'] = os.path.join(save_path, '%(title)s [%(id)s].mp3')
                elif format_choice == 'Video (mp4, Best)':
                    # Standard best quality MP4, requires ffmpeg for merging usually
                    ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best'
                     # Ensure MP4 container, especially after merging
                    postprocessors.append({
                         'key': 'FFmpegVideoConvertor',
                         'preferedformat': 'mp4',
                    })
                    ydl_opts['outtmpl'] = os.path.join(save_path, '%(title)s [%(id)s].mp4')
                else: # Fallback, should ideally not happen with ComboBox
                    ydl_opts['format'] = 'best'

            if postprocessors:
                ydl_opts['postprocessors'] = postprocessors

            self.status_callback("Starting download...")
            self.progress_callback(0)

            # --- Run yt-dlp Download ---
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                 # Check for cancellation before download call
                if self.cancel_event.is_set():
                    raise DownloadCancelled("Download cancelled before starting.")
                ydl.download([url])

            # Check for cancellation immediately after download finishes (before final message)
            if self.cancel_event.is_set():
                 raise DownloadCancelled("Download cancelled.")

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
            self.finished_callback() # Signal UI task is done
            self.current_thread = None


    def start_download(self, url, save_path, format_choice, quality_format_id, is_playlist, playlist_items):
        """Starts the download process in a new thread."""
        if not url or not save_path:
            self.status_callback("Error: URL and Save Path are required.")
            self.finished_callback()
            return

        if self.current_thread and self.current_thread.is_alive():
             self.status_callback("Error: Another operation is already in progress.")
             return

        self.cancel_event.clear() # Reset cancellation flag

        self.current_thread = threading.Thread(
            target=self._execute_download,
            args=(url, save_path, format_choice, quality_format_id, is_playlist, playlist_items),
            daemon=True
        )
        self.current_thread.start()

    def cancel_operation(self):
        """Signals the currently running operation (info fetch or download) to cancel."""
        if self.current_thread and self.current_thread.is_alive():
            self.status_callback("Cancellation requested...")
            self.cancel_event.set()
            # Note: The thread might take a moment to actually stop,
            # especially if it's in the middle of a blocking operation.
            # We don't forcefully kill the thread, we let it exit gracefully.
        else:
            self.status_callback("No operation running to cancel.")