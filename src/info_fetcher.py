# src/info_fetcher.py
# -- ملف يحتوي على كلاس جلب المعلومات --
# Purpose: Contains the InfoFetcher class responsible for fetching metadata.

import yt_dlp
import traceback
from .exceptions import DownloadCancelled # <-- استيراد نسبي للاستثناء المخصص Relative import for custom exception

class InfoFetcher:
    """
    كلاس مسؤول عن عملية جلب معلومات الفيديو/قائمة التشغيل باستخدام yt-dlp.
    Class responsible for fetching video/playlist information using yt-dlp.
    """
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
        """
        تهيئة جالب المعلومات.
        Initializes the info fetcher.

        Args:
            url (str): رابط الفيديو أو قائمة التشغيل. Video or playlist URL.
            cancel_event (threading.Event): حدث للإشارة إلى طلب الإلغاء. Event to signal cancellation request.
            success_callback (callable): دالة تُستدعى عند النجاح مع قاموس المعلومات. Callback on success with info dict.
            error_callback (callable): دالة تُستدعى عند الخطأ مع رسالة الخطأ. Callback on error with error message.
            status_callback (callable): دالة لتحديث رسالة الحالة. Callback to update status message.
            progress_callback (callable): دالة لتحديث شريط التقدم (0.0-1.0). Callback to update progress bar (0.0-1.0).
            finished_callback (callable): دالة تُستدعى دائمًا عند انتهاء العملية. Callback always called when operation finishes.
        """
        self.url = url
        self.cancel_event = cancel_event
        self.success_callback = success_callback
        self.error_callback = error_callback
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

    def _check_cancel(self, stage=""):
        """
        يتحقق مما إذا كان قد تم طلب الإلغاء ويطلق استثناءً إذا كان الأمر كذلك.
        Checks if cancellation has been requested and raises an exception if so.
        """
        if self.cancel_event.is_set():
            raise DownloadCancelled(f"Info fetch cancelled {stage}.")

    def _fetch_info_core(self):
        """
        ينفذ عملية جلب المعلومات الأساسية باستخدام yt-dlp.
        Executes the core information fetching process using yt-dlp.
        """
        self.status_callback("Fetching information...")
        self.progress_callback(0) # يمكن استخدام 0 كبداية Progress starts at 0
        self._check_cancel("before starting fetch")

        # خيارات yt-dlp لجلب المعلومات فقط
        # yt-dlp options for fetching info only
        ydl_opts = {
            "quiet": True,              # منع طباعة مخرجات yt-dlp القياسية Suppress standard yt-dlp output
            "nocheckcertificate": True, # تجاهل أخطاء شهادة SSL Ignore SSL certificate errors
            "extract_flat": "in_playlist", # جلب معلومات القائمة بسرعة دون تحليل كل فيديو Fetch playlist info quickly without parsing each video
            "playlistend": 500,         # حد أقصى لعدد العناصر في القائمة (للحماية من القوائم الضخمة) Limit playlist items (protection)
            "ignoreerrors": True,       # محاولة المتابعة حتى لو فشل جلب بعض عناصر القائمة Try to continue even if some items fail
            "forcejson": True,          # إجبار الإخراج كـ JSON (لضمان الحصول على قاموس) Force JSON output (ensures dictionary)
            "skip_download": True,      # الأهم: عدم تحميل أي شيء Absolutely crucial: do not download anything
        }

        info_dict = None
        try:
            # استخدام مدير السياق لـ yt-dlp Use context manager for yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                self._check_cancel("before calling extract_info")
                # استخراج المعلومات دون تحميل Extract info without downloading
                info_dict = ydl.extract_info(self.url, download=False)
                self._check_cancel("after calling extract_info")

        except yt_dlp.utils.DownloadError as e:
            # التعامل مع أخطاء yt-dlp الشائعة Handle common yt-dlp errors
            error_message = str(e)
            partial_info = None
            # تنظيف رسالة الخطأ Clean up the error message
            if "ERROR:" in error_message:
                error_message = error_message.split("ERROR:")[-1].strip()

            # التحقق مما إذا كان الخطأ يحتوي على بيانات جزئية Check if error contains partial data
            if getattr(e, "partial", False):
                partial_info = getattr(e, "data", None)

            if partial_info:
                # إذا كان هناك بيانات جزئية، أرسلها للنجاح (قد تكون قائمة تشغيل غير مكتملة) If partial data exists, send it as success (might be incomplete playlist)
                print(f"InfoFetcher yt-dlp DownloadError with partial data: {e}")
                self.success_callback(partial_info)
            else:
                # إذا لا يوجد بيانات جزئية، أبلغ عن الخطأ If no partial data, report the error
                print(f"InfoFetcher yt-dlp DownloadError: {e}")
                self.error_callback(error_message)
            return # الخروج من الدالة بعد معالجة الخطأ Exit function after handling error

        except DownloadCancelled:
            # إذا تم الإلغاء، أعد إطلاق الاستثناء ليتم التقاطه في run() If cancelled, re-raise for run() to catch
            raise
        except Exception as e:
            # التعامل مع أي أخطاء أخرى غير متوقعة Handle any other unexpected errors
            print(f"InfoFetcher Unexpected Error: {e}")
            traceback.print_exc() # طباعة تتبع الخطأ الكامل Print full traceback
            self.error_callback(f"An unexpected error occurred: {type(e).__name__}")
            return

        # بعد محاولة الجلب After the fetch attempt
        if info_dict:
            # معالجة خاصة للقوائم: تأكد من إزالة الإدخالات الفارغة (قد تحدث مع ignoreerrors) Special handling for playlists: remove null entries (can happen with ignoreerrors)
            if "entries" in info_dict and isinstance(info_dict["entries"], list):
                valid_entries = [entry for entry in info_dict["entries"] if entry]
                # حالة خاصة لقوائم يوتيوب الفارغة أو الخاصة (تظهر كـ YoutubeTab) Special case for empty/private YouTube playlists (appear as YoutubeTab)
                if not valid_entries and info_dict.get("extractor_key") == "YoutubeTab":
                    print("InfoFetcher: YouTube playlist seems empty or private.")
                    self.error_callback(
                        "Playlist is empty, private, or could not be accessed."
                    )
                    return
                info_dict["entries"] = valid_entries # تحديث القائمة بالإدخالات الصالحة Update list with valid entries

            # استدعاء كول باك النجاح Call success callback
            self.status_callback("Information fetched successfully.")
            self.progress_callback(1.0) # اكتمل التقدم Progress complete
            self.success_callback(info_dict)
        else:
            # إذا لم يتم إرجاع أي قاموس (رابط غير صالح مثلاً) If no dictionary returned (e.g., invalid URL)
            print(
                "InfoFetcher: No information dictionary returned (URL might be invalid)."
            )
            self.error_callback(
                "Could not retrieve information (URL might be invalid or video unavailable)."
            )

    def run(self):
        """
        نقطة الدخول لتشغيل عملية جلب المعلومات في خيط منفصل.
        Entry point to run the info fetching process in a separate thread.
        Handles exceptions and ensures the finished_callback is always called.
        """
        try:
            # تشغيل المنطق الأساسي Run the core logic
            self._fetch_info_core()
        except DownloadCancelled as e:
            # التعامل مع الإلغاء Handle cancellation
            self.status_callback(str(e))
            print(e)
        except Exception as e:
            # التعامل مع أي خطأ فادح غير متوقع قد يحدث خارج _fetch_info_core Handle any fatal unexpected error outside _fetch_info_core
            print(f"InfoFetcher FATAL UNEXPECTED Error in run: {e}")
            traceback.print_exc()
            self.error_callback(
                f"A critical unexpected error occurred: {type(e).__name__}"
            )
        finally:
            # التأكد من استدعاء الكول باك النهائي دائمًا Ensure the final callback is always called
            print("InfoFetcher: Reached finally block, calling finished_callback.")
            self.finished_callback()