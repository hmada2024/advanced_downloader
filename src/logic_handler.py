# -- ملف يحتوي على الكلاس المنسق لعمليات المنطق --
import threading
from logic_operations import InfoFetcher, Downloader, find_ffmpeg
from exceptions import DownloadCancelled

class LogicHandler:
    """
    ينسق عمليات جلب المعلومات والتحميل، ويدير الخيوط والإلغاء.
    """
    def __init__(self, status_callback, progress_callback, finished_callback, info_success_callback, info_error_callback):
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.info_success_callback = info_success_callback
        self.info_error_callback = info_error_callback
        self.ffmpeg_path = find_ffmpeg()
        self.cancel_event = threading.Event()
        self.current_thread = None

    def start_info_fetch(self, url):
        """Starts the info fetching process."""
        if not url:
            self.status_callback("Error: Please enter a URL.")
            self.info_error_callback("URL is empty.")
            self.finished_callback()
            return
        if self.current_thread and self.current_thread.is_alive():
             self.status_callback("Error: Another operation is already in progress.")
             return

        self.cancel_event.clear()
        fetcher_instance = InfoFetcher(
            url=url, cancel_event=self.cancel_event,
            success_callback=self.info_success_callback, error_callback=self.info_error_callback,
            status_callback=self.status_callback, progress_callback=self.progress_callback,
            finished_callback=self.finished_callback
        )
        self.current_thread = threading.Thread(target=fetcher_instance.run, daemon=True)
        self.current_thread.start()

    # -- START Phase 2 Change: Add playlist_items_count parameter --
    def start_download(self, url, save_path, format_choice, quality_format_id,
                       is_playlist, playlist_items, playlist_items_count):
    # -- END Phase 2 Change --
        """Starts the download process."""
        if not url or not save_path:
            self.status_callback("Error: URL and Save Path are required.")
            self.finished_callback()
            return
        if self.current_thread and self.current_thread.is_alive():
             self.status_callback("Error: Another operation is already in progress.")
             return

        self.cancel_event.clear()
        downloader_instance = Downloader(
            url=url, save_path=save_path, format_choice=format_choice, # تمرير الخيار الجديد Pass new choice
            quality_format_id=quality_format_id, is_playlist=is_playlist,
            playlist_items=playlist_items,
            # -- START Phase 2 Change: Pass count to Downloader --
            playlist_items_count=playlist_items_count,
            # -- END Phase 2 Change --
            ffmpeg_path=self.ffmpeg_path, cancel_event=self.cancel_event,
            status_callback=self.status_callback, progress_callback=self.progress_callback,
            finished_callback=self.finished_callback
        )
        self.current_thread = threading.Thread(target=downloader_instance.run, daemon=True)
        self.current_thread.start()

    def cancel_operation(self):
        """Sends a cancellation signal."""
        if self.current_thread and self.current_thread.is_alive():
            self.status_callback("Cancellation requested...")
            self.cancel_event.set()
        else:
            self.status_callback("No operation running to cancel.")