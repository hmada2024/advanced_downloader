# src/logic_handler.py
# -- ملف يحتوي على الكلاس المنسق لعمليات المنطق --
# Purpose: Contains the coordinating class for logic operations.

import threading
# --- تعديل الاستيرادات --- Modify Imports ---
from .info_fetcher import InfoFetcher         # <-- استيراد من الملف الجديد Import from new file
from .downloader import Downloader             # <-- استيراد من الملف الجديد Import from new file
from .logic_utils import find_ffmpeg         # <-- استيراد من الملف الجديد Import from new file
from .exceptions import DownloadCancelled    # الاستثناء يبقى كما هو Exception remains the same
# ------------------------------------------

class LogicHandler:
    """
    ينسق بين الواجهة الرسومية وعمليات الخلفية (جلب المعلومات والتحميل).
    Coordinates between the GUI and background operations (info fetching and downloading).
    يدير الخيوط وطلبات الإلغاء.
    Manages threads and cancellation requests.
    """
    def __init__(
        self,
        status_callback,
        progress_callback,
        finished_callback,
        info_success_callback,
        info_error_callback,
    ):
        """
        تهيئة منسق المنطق.
        Initializes the logic handler.

        Args:
            status_callback (callable): لتحديث رسالة الحالة في الواجهة. To update status message in UI.
            progress_callback (callable): لتحديث شريط التقدم. To update progress bar.
            finished_callback (callable): للإعلام بانتهاء المهمة (نجاح، فشل، إلغاء). To notify task completion (success, fail, cancel).
            info_success_callback (callable): للإعلام بنجاح جلب المعلومات مع البيانات. To notify info fetch success with data.
            info_error_callback (callable): للإعلام بفشل جلب المعلومات مع رسالة خطأ. To notify info fetch failure with error message.
        """
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.info_success_callback = info_success_callback
        self.info_error_callback = info_error_callback

        # البحث عن FFmpeg عند التهيئة Find FFmpeg on initialization
        self.ffmpeg_path = find_ffmpeg()
        if not self.ffmpeg_path:
             print("LogicHandler Warning: FFmpeg not found. Some operations like MP3 conversion might fail.")
             # Optional: You could even pass a warning up to the UI status here
             # self.status_callback("Warning: FFmpeg not found. MP3 conversion might fail.")

        # حدث لإدارة الإلغاء بين الخيوط Event to manage cancellation across threads
        self.cancel_event = threading.Event()
        # لتتبع الخيط النشط حاليًا To keep track of the currently active thread
        self.current_thread = None

    def _is_operation_running(self):
        """
        يتحقق مما إذا كانت هناك عملية (خيط) نشطة حاليًا.
        Checks if an operation (thread) is currently active.

        Returns:
            bool: True إذا كان هناك خيط نشط، وإلا False. True if a thread is active, False otherwise.
        """
        if self.current_thread and self.current_thread.is_alive():
            # إبلاغ المستخدم إذا حاول بدء عملية جديدة أثناء وجود أخرى نشطة
            # Inform user if they try to start a new operation while another is active
            self.status_callback("Error: Another operation is already in progress.")
            return True
        return False

    def start_info_fetch(self, url):
        """
        يبدأ عملية جلب المعلومات في خيط منفصل.
        Starts the information fetching process in a separate thread.
        """
        # تحقق مبدئي من المدخلات Check inputs first
        if not url:
            self.info_error_callback("URL cannot be empty.")
            # استدعاء finished مهم لإعادة الواجهة لحالتها الطبيعية حتى بعد الخطأ المبدئي
            # Calling finished is important to reset the UI even after an initial error
            self.finished_callback()
            return
        # منع تشغيل عمليتين في نفس الوقت Prevent running two operations concurrently
        if self._is_operation_running():
            return

        print("LogicHandler: Starting info fetch...")
        self.cancel_event.clear() # إعادة تعيين حدث الإلغاء Reset cancellation event

        # إنشاء كائن InfoFetcher مع الكول باكات اللازمة Create InfoFetcher instance with necessary callbacks
        fetcher_instance = InfoFetcher(
            url=url,
            cancel_event=self.cancel_event,
            success_callback=self.info_success_callback,
            error_callback=self.info_error_callback,
            status_callback=self.status_callback,
            progress_callback=self.progress_callback, # يستخدم لتعيين 0% و 100% Used to set 0% and 100%
            finished_callback=self.finished_callback,
        )
        # إنشاء وتشغيل الخيط Create and start the thread
        self.current_thread = threading.Thread(target=fetcher_instance.run, daemon=True)
        self.current_thread.start()

    # --- تعديل: إزالة quality_format_id ---
    def start_download(
        self,
        url,
        save_path,
        format_choice,
        # quality_format_id, <-- Parameter removed
        is_playlist,
        playlist_items,
        selected_items_count,
        total_playlist_count,
    ):
        """
        يبدأ عملية التحميل في خيط منفصل.
        Starts the download process in a separate thread.
        """
        # التحقق من المدخلات الأساسية Check basic inputs
        if not url or not save_path:
            self.status_callback("Error: URL and Save Path are required.")
            self.finished_callback() # إعادة الواجهة Reset UI
            return
        # منع تشغيل عمليتين في نفس الوقت Prevent concurrent operations
        if self._is_operation_running():
            return

        print(f"LogicHandler: Starting download... Playlist: {is_playlist}, Selected: {selected_items_count}, Total: {total_playlist_count}, Format Choice: '{format_choice}'")
        self.cancel_event.clear() # إعادة تعيين حدث الإلغاء Reset cancellation event

        # إنشاء كائن Downloader
        # --- تعديل: إزالة تمرير quality_format_id ---
        downloader_instance = Downloader(
            url=url,
            save_path=save_path,
            format_choice=format_choice,             # تمرير الخيار العام Pass general choice
            # quality_format_id=quality_format_id,  <-- Argument removed
            is_playlist=is_playlist,
            playlist_items=playlist_items,
            selected_items_count=selected_items_count, # تمرير العدد المختار Pass selected count
            total_playlist_count=total_playlist_count, # تمرير العدد الكلي Pass total count
            ffmpeg_path=self.ffmpeg_path,             # تمرير مسار ffmpeg Pass ffmpeg path
            cancel_event=self.cancel_event,            # تمرير حدث الإلغاء Pass cancellation event
            status_callback=self.status_callback,       # تمرير كول باكات الواجهة Pass UI callbacks
            progress_callback=self.progress_callback,
            finished_callback=self.finished_callback,
        )
        # إنشاء وتشغيل الخيط Create and start the thread
        self.current_thread = threading.Thread(target=downloader_instance.run, daemon=True)
        self.current_thread.start()

    def cancel_operation(self):
        """
        يطلب إلغاء العملية النشطة حاليًا (إذا وجدت).
        Requests cancellation of the currently active operation (if any).
        """
        if self.current_thread and self.current_thread.is_alive():
            print("LogicHandler: Cancellation requested.")
            self.status_callback("Cancellation requested...")
            # تعيين حدث الإلغاء، الكود داخل الخيط سيتحقق منه Set the cancellation event, code within the thread will check it
            self.cancel_event.set()
        else:
            print("LogicHandler: No operation running to cancel.")
            # لا تقم بتحديث الحالة إذا لم يكن هناك شيء لإلغائه
            # self.status_callback("No operation running to cancel.") # يمكن إلغاء التعليق إذا أردت