# -- ملف يحتوي على الكلاس المنسق لعمليات المنطق --
import threading
from .logic_operations import InfoFetcher, Downloader, find_ffmpeg
from .exceptions import DownloadCancelled


class LogicHandler:
    def __init__(
        self,
        status_callback,
        progress_callback,
        finished_callback,
        info_success_callback,
        info_error_callback,
    ):
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.info_success_callback = info_success_callback
        self.info_error_callback = info_error_callback
        self.ffmpeg_path = find_ffmpeg()
        self.cancel_event = threading.Event()
        self.current_thread = None

    def _is_operation_running(self):
        if self.current_thread and self.current_thread.is_alive():
            self.status_callback("Error: Another operation is already in progress.")
            return True
        return False

    def start_info_fetch(self, url):
        if not url:
            self.info_error_callback("URL cannot be empty.")
            self.finished_callback()
            return
        if self._is_operation_running():
            return
        print("LogicHandler: Starting info fetch...")
        self.cancel_event.clear()
        fetcher_instance = InfoFetcher(
            url=url,
            cancel_event=self.cancel_event,
            success_callback=self.info_success_callback,
            error_callback=self.info_error_callback,
            status_callback=self.status_callback,
            progress_callback=self.progress_callback,
            finished_callback=self.finished_callback,
        )
        self.current_thread = threading.Thread(target=fetcher_instance.run, daemon=True)
        self.current_thread.start()

    # --- تعديل: إضافة total_playlist_count ---
    def start_download(
        self,
        url,
        save_path,
        format_choice,
        quality_format_id,
        is_playlist,
        playlist_items,
        selected_items_count,
        total_playlist_count,
    ):
        # --------------------------------------
        """Starts the download process in a separate thread."""
        if not url or not save_path:
            self.status_callback("Error: URL and Save Path are required.")
            self.finished_callback()
            return
        if self._is_operation_running():
            return

        print(
            f"LogicHandler: Starting download... Playlist: {is_playlist}, Selected: {selected_items_count}, Total: {total_playlist_count}"
        )
        self.cancel_event.clear()
        downloader_instance = Downloader(
            url=url,
            save_path=save_path,
            format_choice=format_choice,
            quality_format_id=quality_format_id,
            is_playlist=is_playlist,
            playlist_items=playlist_items,
            # --- تعديل: تمرير كلا العددين ---
            selected_items_count=selected_items_count,  # العدد المختار
            total_playlist_count=total_playlist_count,  # العدد الكلي
            # -----------------------------
            ffmpeg_path=self.ffmpeg_path,
            cancel_event=self.cancel_event,
            status_callback=self.status_callback,
            progress_callback=self.progress_callback,
            finished_callback=self.finished_callback,
        )
        self.current_thread = threading.Thread(
            target=downloader_instance.run, daemon=True
        )
        self.current_thread.start()

    def cancel_operation(self):
        if self.current_thread and self.current_thread.is_alive():
            print("LogicHandler: Cancellation requested.")
            self.status_callback("Cancellation requested...")
            self.cancel_event.set()
        else:
            print("LogicHandler: No operation running to cancel.")
            self.status_callback("No operation running to cancel.")
