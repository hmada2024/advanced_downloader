import os
import yt_dlp
import threading
import sys
from pathlib import Path

class DownloaderLogic:
    def __init__(self, status_callback, progress_callback, finished_callback):
        """
        Initialize the downloader logic.
        Args:
            status_callback: Function to call to update the status label in the UI.
            progress_callback: Function to call to update the progress bar in the UI.
            finished_callback: Function to call when download completes or fails.
        """
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.ffmpeg_path = self._find_ffmpeg()

    def _find_ffmpeg(self):
        """Tries to find the ffmpeg executable."""
        # Prefer bundled ffmpeg
        bundled_path = Path(sys.argv[0]).parent / "ffmpeg_bin" / "ffmpeg.exe"
        if bundled_path.is_file():
            print(f"Found bundled ffmpeg: {bundled_path}")
            return str(bundled_path)

        # Fallback to checking PATH (less ideal for portable app)
        # For simplicity in this example, we primarily rely on the bundled one.
        # You could add shutil.which("ffmpeg") here as a fallback.
        print("Warning: Bundled ffmpeg not found. yt-dlp might rely on system PATH.")
        return None # Or potentially search PATH if needed


    def _my_hook(self, d):
        """Progress hook for yt-dlp."""
        if d['status'] == 'downloading':
            total_bytes = d.get('total_bytes') or d.get('total_bytes_estimate')
            downloaded_bytes = d.get('downloaded_bytes')
            if total_bytes and downloaded_bytes:
                progress = downloaded_bytes / total_bytes
                speed = d.get('_speed_str', 'N/A')
                eta = d.get('_eta_str', 'N/A')
                # Update UI thread-safely via callbacks
                self.progress_callback(progress)
                self.status_callback(f"Downloading: {d['_percent_str']} ({downloaded_bytes}/{total_bytes}) at {speed}, ETA: {eta}")
        elif d['status'] == 'finished':

            self.progress_callback(1.0) # Mark as complete before potential post-processing wait
        elif d['status'] == 'error':
            self.status_callback(f"Error during download hook.")
            print(f"yt-dlp hook error: {d}") # Log the error for debugging

    def _execute_download(self, url, save_path, format_choice, is_playlist):
        """Executes the download in a separate thread."""
        try:
            ydl_opts = {
                'noplaylist': not is_playlist,
                'progress_hooks': [self._my_hook],
                'outtmpl': os.path.join(save_path, '%(title)s.%(ext)s'), # Standard template
                'nocheckcertificate': True, # Sometimes needed for certain sites
                'ignoreerrors': is_playlist, # Continue downloading playlist items even if one fails
            }

            # Add ffmpeg location if found
            if self.ffmpeg_path:
                ydl_opts['ffmpeg_location'] = self.ffmpeg_path
            else:
                 self.status_callback("Warning: FFmpeg not found. Some formats/conversions might fail.")


            if format_choice == 'Audio (mp3)':
                ydl_opts['format'] = 'bestaudio/best'
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192', # Standard MP3 quality
                }]
                # Ensure the output template reflects the final extension
                ydl_opts['outtmpl'] = os.path.join(save_path, '%(title)s.mp3')
            elif format_choice == 'Video (mp4, Best)':
                # Common format, merges best video and audio available into mp4
                ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
                # Postprocessor to ensure MP4 container if merging occurs or if source isn't mp4
                ydl_opts['postprocessors'] = [{
                    'key': 'FFmpegVideoConvertor',
                    'preferedformat': 'mp4',
                }]
                 # Ensure the output template reflects the final extension
                ydl_opts['outtmpl'] = os.path.join(save_path, '%(title)s.mp4')
            # Add more format options here if needed (e.g., specific resolutions)
            else: # Default to best available if somehow choice is invalid
                 ydl_opts['format'] = 'best'


            self.status_callback("Starting download...")
            self.progress_callback(0) # Reset progress bar

            # Run yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            self.status_callback("Download and processing complete!")

        except yt_dlp.utils.DownloadError as e:
            # Handle specific download errors (e.g., URL not found, private video)
            error_message = str(e).split('ERROR:')[-1].strip() # Try to get a cleaner message
            self.status_callback(f"Error: {error_message}")
            print(f"yt-dlp DownloadError: {e}") # Log full error
        except Exception as e:
            # Handle other potential errors during setup or execution
            self.status_callback(f"An unexpected error occurred: {type(e).__name__}")
            print(f"Unexpected Error: {e}") # Log full error
        finally:
            # Always call the finished callback to re-enable UI elements etc.
            self.finished_callback()


    def start_download(self, url, save_path, format_choice, is_playlist):
        """Starts the download process in a new thread."""
        if not url:
            self.status_callback("Error: Please enter a URL.")
            self.finished_callback() # Call finished to reset UI state if needed
            return
        if not save_path or not os.path.isdir(save_path):
             self.status_callback("Error: Please select a valid save directory.")
             self.finished_callback()
             return

        # Run the actual download logic in a separate thread
        download_thread = threading.Thread(
            target=self._execute_download,
            args=(url, save_path, format_choice, is_playlist),
            daemon=True # Allows program to exit even if thread is running (optional)
        )
        download_thread.start()