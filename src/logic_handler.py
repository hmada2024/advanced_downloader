# -- ملف يحتوي على الكلاس المنسق لعمليات المنطق --
import threading

# استخدام الاستيراد النسبي للملفات داخل نفس الحزمة
from .logic_operations import (
    InfoFetcher,
    Downloader,
    find_ffmpeg,
)  # <-- تم التعديل: استخدام .
from .exceptions import DownloadCancelled  # <-- تم التعديل: استخدام .


class LogicHandler:
    """
    ينسق عمليات جلب المعلومات والتحميل، ويدير الخيوط والإلغاء.
    Coordinates info fetching and download operations, manages threads and cancellation.
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
        Initializes the Logic Handler.

        Args:
            status_callback: دالة لتحديث رسالة الحالة في الواجهة. Callback to update UI status message.
            progress_callback: دالة لتحديث شريط التقدم في الواجهة. Callback to update UI progress bar.
            finished_callback: دالة تُستدعى عند انتهاء أي مهمة (نجاح، فشل، إلغاء). Callback invoked when any task finishes.
            info_success_callback: دالة تُستدعى عند نجاح جلب المعلومات. Callback for successful info fetch.
            info_error_callback: دالة تُستدعى عند فشل جلب المعلومات. Callback for failed info fetch.
        """
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
        self.info_success_callback = info_success_callback
        self.info_error_callback = info_error_callback
        self.ffmpeg_path = find_ffmpeg()  # البحث عن ffmpeg عند التهيئة
        self.cancel_event = threading.Event()  # حدث لإشارة الإلغاء
        self.current_thread = None  # لتتبع الخيط النشط

    def _is_operation_running(self):
        """يتحقق مما إذا كانت هناك عملية جارية بالفعل."""
        """Checks if an operation is already running."""
        if self.current_thread and self.current_thread.is_alive():
            self.status_callback("Error: Another operation is already in progress.")
            # استدعاء finished_callback هنا قد يكون مربكًا، الأفضل فقط إعلام المستخدم
            # self.finished_callback()
            return True
        return False

    def start_info_fetch(self, url):
        """يبدأ عملية جلب المعلومات في خيط منفصل."""
        """Starts the info fetching process in a separate thread."""
        if not url:
            # استخدام info_error_callback لمعالجة الخطأ في الواجهة بشكل متسق
            self.info_error_callback("URL cannot be empty.")
            # استدعاء finished_callback لإعادة تعيين حالة الواجهة إذا لزم الأمر
            self.finished_callback()
            return
        if self._is_operation_running():
            return  # منع بدء عملية جديدة إذا كانت هناك واحدة قيد التشغيل

        print("LogicHandler: Starting info fetch...")
        self.cancel_event.clear()  # مسح علامة الإلغاء السابقة
        fetcher_instance = InfoFetcher(
            url=url,
            cancel_event=self.cancel_event,
            success_callback=self.info_success_callback,  # تمرير الكول باك للنجاح
            error_callback=self.info_error_callback,  # تمرير الكول باك للخطأ
            status_callback=self.status_callback,
            progress_callback=self.progress_callback,  # قد لا يستخدم في الجلب، لكن نمرره
            finished_callback=self.finished_callback,  # يٌستدعى دائمًا في النهاية
        )
        # إنشاء وتشغيل الخيط
        self.current_thread = threading.Thread(target=fetcher_instance.run, daemon=True)
        self.current_thread.start()

    def start_download(
        self,
        url,
        save_path,
        format_choice,
        quality_format_id,
        is_playlist,
        playlist_items,
        playlist_items_count,
    ):
        """يبدأ عملية التحميل في خيط منفصل."""
        """Starts the download process in a separate thread."""
        if not url or not save_path:
            self.status_callback("Error: URL and Save Path are required.")
            self.finished_callback()  # إنهاء العملية وإعادة الواجهة
            return
        if self._is_operation_running():
            return

        print(
            f"LogicHandler: Starting download... Playlist: {is_playlist}, Count: {playlist_items_count}"
        )
        self.cancel_event.clear()  # مسح علامة الإلغاء
        downloader_instance = Downloader(
            url=url,
            save_path=save_path,
            format_choice=format_choice,
            quality_format_id=quality_format_id,
            is_playlist=is_playlist,
            playlist_items=playlist_items,
            playlist_items_count=playlist_items_count,
            ffmpeg_path=self.ffmpeg_path,
            cancel_event=self.cancel_event,
            status_callback=self.status_callback,
            progress_callback=self.progress_callback,
            finished_callback=self.finished_callback,
        )
        # إنشاء وتشغيل الخيط
        self.current_thread = threading.Thread(
            target=downloader_instance.run, daemon=True
        )
        self.current_thread.start()

    def cancel_operation(self):
        """يرسل إشارة الإلغاء للعملية الجارية."""
        """Sends a cancellation signal to the running operation."""
        if self.current_thread and self.current_thread.is_alive():
            print("LogicHandler: Cancellation requested.")
            self.status_callback("Cancellation requested...")  # تحديث فوري للحالة
            self.cancel_event.set()  # تعيين حدث الإلغاء
            # لا تستدعي finished_callback هنا، دع الخيط ينتهي بشكل طبيعي
        else:
            print("LogicHandler: No operation running to cancel.")
            self.status_callback("No operation running to cancel.")
