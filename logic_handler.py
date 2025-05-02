# -- ملف يحتوي على الكلاس المنسق لعمليات المنطق --
# Purpose: Contains the main coordinator class for logic operations.

import threading
# استيراد الكلاسات والوظائف من ملف العمليات الفعلي
# Import classes and functions from the operations file
from logic_operations import InfoFetcher, Downloader, find_ffmpeg
# استيراد الاستثناء المخصص
# Import the custom exception
from exceptions import DownloadCancelled

class LogicHandler:
    """
    ينسق عمليات جلب المعلومات والتحميل، ويدير الخيوط والإلغاء.
    Coordinates info fetching and downloading, manages threads and cancellation.
    """
    def __init__(self, status_callback, progress_callback, finished_callback, info_success_callback, info_error_callback):
        """
        تهيئة المنسق.
        Initializes the coordinator.

        Args:
            (callbacks): دوال الكول باك للتواصل مع الواجهة. Callbacks to communicate with the UI.
        """
        # تخزين الكول باكات Store callbacks
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.info_success_callback = info_success_callback
        self.info_error_callback = info_error_callback

        # البحث عن مسار FFmpeg مرة واحدة عند التهيئة Find FFmpeg path once during initialization
        self.ffmpeg_path = find_ffmpeg()
        # أدوات إدارة الخيوط والإلغاء Threading and cancellation tools
        self.cancel_event = threading.Event()
        self.current_thread = None

    def start_info_fetch(self, url):
        """
        تبدأ عملية جلب المعلومات عن طريق إنشاء وتشغيل InfoFetcher في خيط جديد.
        Starts the info fetching process by creating and running an InfoFetcher in a new thread.
        """
        if not url:
            self.status_callback("Error: Please enter a URL.")
            self.info_error_callback("URL is empty.")
            self.finished_callback() # يجب استدعاؤها حتى لو لم تبدأ المهمة لتعيد الواجهة لحالتها
            return
        # منع تشغيل عملية جديدة إذا كانت هناك واحدة نشطة بالفعل Prevent starting if another is active
        if self.current_thread and self.current_thread.is_alive():
             self.status_callback("Error: Another operation is already in progress.")
             return # لا تستدعي finished_callback هنا

        self.cancel_event.clear() # إعادة تعيين إشارة الإلغاء Reset cancellation flag

        # إنشاء نسخة من جالب المعلومات Create an instance of InfoFetcher
        fetcher_instance = InfoFetcher(
            url=url,
            cancel_event=self.cancel_event,
            success_callback=self.info_success_callback,
            error_callback=self.info_error_callback,
            status_callback=self.status_callback,
            progress_callback=self.progress_callback, # تمريرها وإن لم تستخدم كثيرًا هنا Pass it even if not heavily used here
            finished_callback=self.finished_callback
        )

        # إنشاء وتشغيل الخيط Create and start the thread
        self.current_thread = threading.Thread(target=fetcher_instance.run, daemon=True)
        self.current_thread.start()

    def start_download(self, url, save_path, format_choice, quality_format_id, is_playlist, playlist_items):
        """
        تبدأ عملية التحميل عن طريق إنشاء وتشغيل Downloader في خيط جديد.
        Starts the download process by creating and running a Downloader in a new thread.
        """
        if not url or not save_path:
            self.status_callback("Error: URL and Save Path are required.")
            self.finished_callback() # يجب استدعاؤها لإعادة الواجهة للحالة الصحيحة Must be called to reset UI
            return
        # منع تشغيل عملية جديدة إذا كانت هناك واحدة نشطة Prevent starting if another is active
        if self.current_thread and self.current_thread.is_alive():
             self.status_callback("Error: Another operation is already in progress.")
             return # لا تستدعي finished_callback هنا

        self.cancel_event.clear() # إعادة تعيين إشارة الإلغاء Reset cancellation flag

        # إنشاء نسخة من المحمل Create an instance of Downloader
        downloader_instance = Downloader(
            url=url,
            save_path=save_path,
            format_choice=format_choice,
            quality_format_id=quality_format_id,
            is_playlist=is_playlist,
            playlist_items=playlist_items,
            ffmpeg_path=self.ffmpeg_path, # استخدام المسار الذي تم العثور عليه Use the found path
            cancel_event=self.cancel_event,
            status_callback=self.status_callback,
            progress_callback=self.progress_callback,
            finished_callback=self.finished_callback
        )

        # إنشاء وتشغيل الخيط Create and start the thread
        self.current_thread = threading.Thread(target=downloader_instance.run, daemon=True)
        self.current_thread.start()

    def cancel_operation(self):
        """
        ترسل إشارة إلغاء للخيط النشط حاليًا.
        Sends a cancellation signal to the currently active thread.
        """
        if self.current_thread and self.current_thread.is_alive():
            self.status_callback("Cancellation requested...")
            self.cancel_event.set() # تفعيل إشارة الإلغاء Activate the cancellation flag
        else:
            self.status_callback("No operation running to cancel.")