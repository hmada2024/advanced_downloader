# src/downloader.py
# -- ملف يحتوي على كلاس التحميل الرئيسي --
# Purpose: Contains the main Downloader class responsible for the download process.

import os
import yt_dlp
import sys
from pathlib import Path
# import re # <- لم يعد مطلوبًا هنا Not needed here anymore
import traceback
import time
import humanize
import contextlib
from .exceptions import DownloadCancelled # <-- استيراد نسبي للاستثناء Relative import for exception
from .logic_utils import clean_filename   # <-- استيراد دالة التنظيف من ملف الأدوات Import clean function from utils

class Downloader:
    """
    كلاس مسؤول عن عملية تحميل الفيديو/الصوت ومعالجته باستخدام yt-dlp.
    Class responsible for downloading and processing video/audio using yt-dlp.
    """
    def __init__(
        self,
        url,
        save_path,
        format_choice,
        quality_format_id,
        is_playlist,
        playlist_items,
        selected_items_count,
        total_playlist_count,
        ffmpeg_path,
        cancel_event,
        status_callback,
        progress_callback,
        finished_callback,
    ):
        """
        تهيئة المحمل.
        Initializes the downloader.
        Args:
            (نفس الوسائط كما في النسخة الأصلية) (Same arguments as original version)
            ...
            total_playlist_count (int): العدد الإجمالي للعناصر في القائمة الأصلية. Total items in the original playlist.
            ...
        """
        self.url = url
        self.save_path = save_path
        self.format_choice = format_choice
        self.quality_format_id = quality_format_id
        self.is_playlist = is_playlist
        self.playlist_items = playlist_items
        self.selected_items_count = selected_items_count
        self.total_playlist_count = total_playlist_count
        self.ffmpeg_path = ffmpeg_path
        self.cancel_event = cancel_event
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

        # متغيرات الحالة الداخلية Internal state variables
        self.last_downloaded_info = None # معلومات آخر ملف تم تحميله Info of the last downloaded file
        self.final_known_path = None # المسار الذي أبلغ عنه الهوك كمسار نهائي Path reported by hook as final
        self._current_processing_playlist_idx_display = 1 # الفهرس المطلق للعنصر الحالي (للعرض) Absolute index of current item (for display)
        self._last_hook_playlist_index = 0 # آخر فهرس مطلق تم رؤيته في الهوك Last absolute index seen in hook
        self._processed_selected_count = 0 # عدد العناصر المحددة التي تم الانتهاء من معالجتها Count of selected items finished processing
        self._cleaned_up_path = None # المسار بعد التنظيف النهائي (لمنع التنظيف المزدوج) Path after final cleanup (prevents double cleanup)

    def _check_cancel(self, stage=""):
        """
        يتحقق من طلب الإلغاء.
        Checks for cancellation request.
        """
        if self.cancel_event.is_set():
            raise DownloadCancelled(f"Download cancelled {stage}.")

    # ----- تم نقل دالة _clean_filename إلى logic_utils.py -----
    # ----- _clean_filename function moved to logic_utils.py -----

    def _my_hook(self, d):
        # sourcery skip: extract-method, hoist-similar-statement-from-if, hoist-statement-from-if
        """
        خطاف تقدم yt-dlp لمعالجة تحديثات الحالة والتقدم.
        yt-dlp progress hook to handle status and progress updates.
        """
        try:
            # التحقق من الإلغاء داخل الهوك Check for cancellation within the hook
            self._check_cancel("during progress hook")
        except DownloadCancelled as e:
            # إطلاق استثناء يتوافق مع ما يتوقعه yt-dlp Raise an exception compatible with yt-dlp
            raise yt_dlp.utils.DownloadCancelled(str(e)) from e

        status = d.get("status")
        info_dict = d.get("info_dict", {})
        hook_playlist_index = info_dict.get("playlist_index") # الفهرس المطلق (يبدأ من 1) Absolute index (1-based)

        # تحديث عداد الفهرس المطلق للعرض (عند الانتقال لعنصر جديد في القائمة)
        # Update absolute index counter for display (when moving to a new playlist item)
        if (
            self.is_playlist
            and hook_playlist_index is not None
            and hook_playlist_index > self._last_hook_playlist_index
        ):
            print(
                f"Hook detected transition to playlist index: {hook_playlist_index}. Updating display counter."
            )
            self._current_processing_playlist_idx_display = hook_playlist_index
            self._last_hook_playlist_index = hook_playlist_index

        # --- المعالجة بناءً على حالة الهوك Process based on hook status ---
        if status == "finished":
            if filepath := info_dict.get("filepath") or d.get("filename"):
                # تخزين آخر مسار تم الإبلاغ عنه والبيانات الوصفية Store the last reported path and metadata
                self.final_known_path = filepath
                self.last_downloaded_info = info_dict
                print(f"Hook 'finished': Path reported '{filepath}'.")

                base_filename = os.path.basename(filepath)
                # التحقق مما إذا كان هذا هو الملف النهائي (له امتداد شائع) Check if this is the final file (has a common extension)
                final_ext_present = any(
                    base_filename.lower().endswith(ext)
                    for ext in [".mp4", ".mp3", ".mkv", ".webm", ".opus", ".ogg"]
                )
                title = info_dict.get("title")
                # **تعديل: استخدام دالة التنظيف المستوردة** **Modification: Use imported clean function**
                display_name = clean_filename(title or base_filename)

                if final_ext_present:
                    status_msg = f"Finished: {display_name}"
                    # زيادة عداد العناصر المحددة المعالجة فقط عند الانتهاء من الملف النهائي
                    # Increment processed selected count only when the final file is done
                    self._processed_selected_count += 1
                    print(
                        f"Processed selected items count incremented to: {self._processed_selected_count}"
                    )
                else:
                    # إذا لم يكن ملفًا نهائيًا، فهي مرحلة معالجة وسيطة If not a final file, it's an intermediate processing stage
                    status_msg = f"Processing: {display_name}..."

                # تحديث رسالة الحالة (سطر واحد للانتهاء/المعالجة) Update status message (single line for finished/processing)
                self.status_callback(status_msg)
                self.progress_callback(1.0) # تعيين التقدم إلى 100% لهذه المرحلة Set progress to 100% for this stage
            else:
                # حالة نادرة: انتهى ولكن لا يوجد مسار Rare case: finished but no filepath
                print("Hook 'finished' but no filepath found in hook data.")
                self.status_callback("Processing finished (unknown file path).")
                self.progress_callback(1.0)

        elif status == "downloading":
            # أثناء عملية التحميل الفعلي While actually downloading
            downloaded_bytes = d.get("downloaded_bytes")
            if downloaded_bytes is not None:
                total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")

                # حساب نسبة التقدم Calculate progress percentage
                progress = 0.0
                percentage_str = "0.0%"
                if total_bytes and total_bytes > 0:
                    progress = max(0.0, min(1.0, downloaded_bytes / total_bytes))
                    percentage_str = f"{progress:.1%}"
                self.progress_callback(progress) # تحديث شريط التقدم Update progress bar

                # --- بناء رسالة الحالة التفصيلية متعددة الأسطر Build detailed multi-line status message ---
                status_lines = []

                # الأسطر المتعلقة بالقائمة (إذا كانت قائمة) Playlist-related lines (if playlist)
                if self.is_playlist:
                    current_absolute_index = self._current_processing_playlist_idx_display
                    total_absolute_str = (
                        f"out of {self.total_playlist_count} total"
                        if self.total_playlist_count > 0
                        else ""
                    )
                    status_lines.append(f"Video {current_absolute_index} {total_absolute_str}")

                    # حساب التقدم ضمن العناصر المحددة Calculate progress within selected items
                    index_in_selection = self._processed_selected_count + 1
                    index_in_selection = min(index_in_selection, self.selected_items_count) # لا يتجاوز العدد المحدد Don't exceed selected count
                    remaining_in_selection = max(0, self.selected_items_count - self._processed_selected_count) # لا يقل عن صفر Cannot be less than zero
                    status_lines.append(f"Selected: {index_in_selection} of {self.selected_items_count} ({remaining_in_selection} remaining)")
                else:
                    # رسالة بسيطة للفيديو المفرد Simple message for single video
                    status_lines.append("Downloading Video")

                # سطر التقدم والحجم Progress and size line
                downloaded_size_str = humanize.naturalsize(downloaded_bytes, binary=True)
                total_size_str = (humanize.naturalsize(total_bytes, binary=True) if total_bytes else "Unknown size")
                status_lines.append(f"Progress: {percentage_str} ({downloaded_size_str} / {total_size_str})")

                # سطر السرعة والوقت المتبقي Speed and ETA line
                speed = d.get("speed")
                speed_str = (f"{humanize.naturalsize(speed, binary=True, gnu=True)}/s" if speed else "Calculating...")
                eta = d.get("eta")
                eta_str = "Calculating..."
                with contextlib.suppress(TypeError, ValueError): # تجاهل أخطاء التحويل المحتملة Ignore potential conversion errors
                    if eta is not None and isinstance(eta, (int, float)) and eta >= 0:
                        eta_str = f"{int(round(eta))} seconds remaining" # عرض الثواني مباشرة Show seconds directly
                        # eta_str = humanize.naturaldelta(eta) + " remaining" # بديل Alternative
                status_lines.append(f"Speed: {speed_str} | ETA: {eta_str}")

                # تجميع الأسطر وتحديث الواجهة Combine lines and update UI
                status_msg = "\n".join(status_lines)
                self.status_callback(status_msg)
                # ------------------------------------
            else:
                # إذا لم يكن هناك بايتات محملة (مرحلة الاتصال مثلاً) If no downloaded bytes (e.g., connecting stage)
                self.status_callback(f"Status: {d.get('status', 'Connecting')}...")

        elif status == "error":
            # عند حدوث خطأ يبلغه الهوك When the hook reports an error
            self.status_callback("Error during download process reported by yt-dlp.")
            print(f"yt-dlp hook reported error: {d.get('error', 'Unknown yt-dlp error')}")

    def _build_format_string(self):
        """
        يبني سلسلة خيارات التنسيق والجودة لـ yt-dlp والمعالجات اللاحقة.
        Builds the format/quality option string for yt-dlp and postprocessors.
        Returns:
            tuple: (format_string, output_extension_hint, postprocessors_list)
        """
        format_choice_lower = self.format_choice.lower()
        output_ext = "mp4"  # الامتداد المتوقع افتراضيًا Default expected extension
        postprocessors = [] # قائمة المعالجات اللاحقة List of postprocessors
        final_format_string = None # السلسلة النهائية لـ yt-dlp Final string for yt-dlp

        # الحالة 1: تم اختيار جودة محددة (وليس قائمة تشغيل) Case 1: Specific quality selected (and not playlist)
        if not self.is_playlist and self.quality_format_id:
            final_format_string = self.quality_format_id
            print(f"Using specific quality format ID: {self.quality_format_id}")
            # تحقق مما إذا كان المستخدم يريد MP3 بالرغم من اختيار جودة فيديو Check if user wants MP3 despite video quality selection
            if "audio (mp3)" in format_choice_lower:
                print("Warning: MP3 format chosen despite specific quality ID selection. Will attempt audio extraction.")
                output_ext = "mp3"
                if self.ffmpeg_path:
                    postprocessors.append({
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192", # جودة MP3 Quality
                    })
                else:
                    # لا يمكن التحويل بدون FFmpeg Cannot convert without FFmpeg
                    print("Error: MP3 conversion requires FFmpeg, which was not found.")
                    output_ext = None # لا يمكن ضمان الامتداد Cannot guarantee extension

        # الحالة 2: تم اختيار MP3 بشكل عام Case 2: MP3 chosen generally
        elif "audio (mp3)" in format_choice_lower:
            final_format_string = "bestaudio/best" # اطلب أفضل صوت Request best audio
            output_ext = "mp3"
            if self.ffmpeg_path:
                postprocessors.append({
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                })
                print("Selecting best audio for MP3 conversion.")
            else:
                print("Warning: MP3 requested but FFmpeg not found. Downloading best audio format.")
                output_ext = None # سيبقى الامتداد الأصلي Original extension will remain

        # الحالة 3: قائمة تشغيل (استخدم حد 720p افتراضيًا) Case 3: Playlist (use 720p limit by default)
        elif self.is_playlist:
            # سلسلة معقدة تطلب أفضل فيديو MP4 حتى 720p مع أفضل صوت، مع بدائل
            # Complex string requesting best MP4 video up to 720p with best audio, with fallbacks
            final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
            output_ext = "mp4"
            print("Using default playlist format (max 720p MP4)")

        # الحالة 4: فيديو مفرد مع اختيار جودة عامة Case 4: Single video with general quality choice
        else:
            height_limit = None
            if "<= 720p" in format_choice_lower: height_limit = 720
            elif "<= 480p" in format_choice_lower: height_limit = 480
            elif "<= 360p" in format_choice_lower: height_limit = 360

            if height_limit:
                # بناء سلسلة التنسيق مع حد الارتفاع Build format string with height limit
                final_format_string = f"bestvideo[height<={height_limit}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height_limit}]+bestaudio/best[height<={height_limit}][ext=mp4]/best[height<={height_limit}]"
                print(f"Using general format: max {height_limit}p MP4")
            else: # الحالة الافتراضية (أفضل جودة MP4 <= 1080p+) Default case (Best Quality MP4 <= 1080p+)
                final_format_string = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"
                print("Using general format: best available MP4 (1080p+)")
            output_ext = "mp4"

        return final_format_string, output_ext, postprocessors

    def _download_core(self):
        """
        ينفذ عملية التحميل الأساسية وإعداد خيارات yt-dlp.
        Executes the core download process and sets up yt-dlp options.
        """
        # إعادة تعيين متغيرات الحالة لكل عملية تحميل Reset state variables for each download operation
        self.last_downloaded_info = None
        self.final_known_path = None
        self._current_processing_playlist_idx_display = 1
        self._last_hook_playlist_index = 0
        self._processed_selected_count = 0
        self._cleaned_up_path = None

        self._check_cancel("before starting download")

        # بناء نمط اسم الملف الناتج Build output filename template
        if self.is_playlist:
            # إضافة رقم القائمة للعناصر Playlist index for items
            outtmpl_pattern = os.path.join(
                self.save_path, "%(playlist_index)s. %(title)s.%(ext)s"
            )
        else:
            # عنوان الفيديو فقط للفيديو المفرد Just title for single video
            outtmpl_pattern = os.path.join(self.save_path, "%(title)s.%(ext)s")

        # الحصول على خيارات التنسيق والمعالجات Build format options and postprocessors
        final_format_string, output_ext_hint, core_postprocessors = self._build_format_string()

        # بناء قاموس خيارات yt-dlp Build yt-dlp options dictionary
        ydl_opts = {
            "progress_hooks": [self._my_hook],    # خطاف التقدم Progress hook
            "outtmpl": outtmpl_pattern,          # نمط اسم الملف Output template
            "nocheckcertificate": True,         # تجاهل أخطاء الشهادة Ignore certificate errors
            "ignoreerrors": self.is_playlist,    # تجاهل الأخطاء في القوائم؟ Ignore errors in playlists?
            "merge_output_format": "mp4",       # محاولة الدمج إلى MP4 إن أمكن Try merging to MP4 if possible
            "postprocessors": core_postprocessors, # معالجات الصوت (MP3) Audio postprocessors (MP3)
            "restrictfilenames": False,         # عدم تقييد أسماء الملفات (للحفاظ على المسافات) Don't restrict filenames (keep spaces)
        }

        # إضافة مسار FFmpeg إذا وجد Add FFmpeg path if found
        if self.ffmpeg_path:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_path
        elif core_postprocessors: # تحذير إذا كان مطلوبًا ولم يوجد Warning if needed but not found
            self.status_callback("Warning: FFmpeg needed for conversion but not found.")

        # خيارات خاصة بالقائمة Playlist specific options
        if self.is_playlist:
            ydl_opts["noplaylist"] = False # تأكيد أنها قائمة Confirm it's a playlist
        if self.playlist_items:
            ydl_opts["playlist_items"] = self.playlist_items # تحديد العناصر المطلوبة Specify items
        else:
            # إذا لم تكن قائمة أو لم يتم تحديد عناصر، قم بتعطيل معالجة القائمة
            # If not a playlist or no items selected, disable playlist processing
            ydl_opts["noplaylist"] = True

        # إضافة خيار التنسيق إذا تم تحديده Add format option if determined
        if final_format_string:
            ydl_opts["format"] = final_format_string
        elif "format" in ydl_opts: # التأكد من إزالته إذا لم يكن مطلوبًا Ensure removed if not needed
            del ydl_opts["format"]

        print("Final yt-dlp options:", ydl_opts) # طباعة الخيارات النهائية للدييباج Print final options for debugging
        self.status_callback("Starting download...")
        self.progress_callback(0) # بدء التقدم من الصفر Start progress at zero

        self._check_cancel("right before calling ydl.download()")

        download_successful = False
        try:
            # تشغيل التحميل باستخدام yt-dlp Run download using yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            download_successful = True # تم الانتهاء بدون خطأ Finished without error
            # تحقق من الإلغاء فورًا بعد انتهاء التحميل Check cancellation immediately after download finishes
            self._check_cancel("immediately after ydl.download() finished")

        except yt_dlp.utils.DownloadCancelled as e:
            # تم الإلغاء عبر الهوك أو check_cancel Raised by hook or check_cancel
            raise DownloadCancelled(str(e)) from e
        except yt_dlp.utils.DownloadError as dl_err:
            # خطأ أثناء التحميل أبلغه yt-dlp Error during download reported by yt-dlp
            error_message = str(dl_err).split("ERROR:")[-1].strip()
            print(f"Downloader yt-dlp DownloadError: {dl_err}")
            self.status_callback(f"Download Error: {error_message}")
            # download_successful يبقى False download_successful remains False
        except Exception as e:
            # أي خطأ آخر غير متوقع Any other unexpected error
            self._log_unexpected_error(e, "during yt-dlp download execution")
            # download_successful يبقى False download_successful remains False

        # تحقق من الإلغاء مرة أخرى بعد كتلة try/except Check cancellation again after try/except block
        self._check_cancel("after download block completion")

        # --- التنظيف النهائي فقط إذا نجح التحميل Final cleanup only if download succeeded ---
        if not download_successful:
            print("Download process reported errors or was unsuccessful. Skipping final cleanup.")
            return # الخروج من الدالة Exit the function

        # محاولة تنظيف اسم الملف النهائي Try cleaning up the final filename
        try:
            time.sleep(0.2) # انتظار قصير لضمان اكتمال عمليات الملف Short wait to ensure file operations complete
            self._cleanup_final_file()
        except Exception as e:
            self._log_unexpected_error(e, "during final file cleanup")
            self.status_callback("Warning: Download complete, but filename cleanup failed.")

    def _cleanup_final_file(self):
        """
        ينظف ويعيد تسمية الملف النهائي الذي تم الإبلاغ عنه بواسطة الهوك إذا لزم الأمر.
        Cleans and renames the final file reported by the hook if necessary.
        """
        # منع التنظيف المتكرر Prevent repeated cleanup
        if self._cleaned_up_path:
            print(f"Cleanup skipped: Already cleaned path '{self._cleaned_up_path}'")
            return

        print("Attempting final file cleanup...")

        # التحقق من وجود مسار نهائي معروف Check if a final path is known
        if not self.final_known_path:
            print("Cleanup skipped: No final file path was reported by hooks.")
            self.status_callback("Warning: Download finished, but final file path is unknown.")
            return

        expected_final_path_obj = Path(self.final_known_path)
        print(f"Cleanup: Checking final path '{expected_final_path_obj}'")

        # انتظار قصير آخر للتأكد من أن الملف موجود ومتاح Short extra wait to ensure file exists and is available
        time.sleep(0.4)

        # التحقق من وجود الملف Check if the file exists
        if not expected_final_path_obj.exists():
            print(f"Cleanup Error: Expected final file '{expected_final_path_obj}' not found after delay.")
            # محاولة تخمين المسار الصحيح بناءً على آخر معلومات Try guessing the correct path based on last info
            if self.last_downloaded_info:
                pl_idx = self.last_downloaded_info.get("playlist_index")
                pl_idx_str = f"{pl_idx}." if pl_idx is not None else ""
                # الحصول على الامتداد المتوقع من _build_format_string Get expected extension from _build_format_string
                expected_ext = self._build_format_string()[1] or "mp4" # fallback to mp4
                title = self.last_downloaded_info.get("title", "untitled")
                # **تعديل: استخدام دالة التنظيف المستوردة** **Modification: Use imported clean function**
                expected_name = f"{pl_idx_str}{title}.{expected_ext}"
                alt_path = expected_final_path_obj.parent / clean_filename(expected_name)

                print(f"Cleanup: Checking alternative path '{alt_path}'")
                if alt_path.exists():
                    print(f"Found file at alternative path: {alt_path}")
                    expected_final_path_obj = alt_path # استخدام المسار البديل Use the alternative path
                else:
                    print(f"Cleanup Error: Alternative path '{alt_path}' also not found.")
                    self.status_callback(f"Error: Processing completed but final file '{expected_final_path_obj.name}' is missing.")
                    return # الخروج إذا لم يتم العثور على الملف Exit if file not found
            else:
                # لا يمكن التخمين بدون معلومات Cannot guess without info
                print("Cleanup Error: File not found and no info to guess alternative.")
                self.status_callback(f"Error: Processing completed but final file '{expected_final_path_obj.name}' is missing.")
                return # الخروج Exit

        # الآن الملف موجود (إما الأصلي أو البديل) Now the file exists (either original or alternative)
        current_basename = expected_final_path_obj.name
        target_basename = current_basename # الاسم المستهدف هو الحالي افتراضيًا Target name is current by default

        # إعادة بناء الاسم المستهدف المثالي بناءً على المعلومات Reconstruct ideal target name based on info
        if self.last_downloaded_info:
            base_title = self.last_downloaded_info.get("title", "")
            base_ext = expected_final_path_obj.suffix.lstrip(".")
            if self.is_playlist:
                playlist_index = self.last_downloaded_info.get("playlist_index")
                # إضافة رقم القائمة إذا وجد Add playlist index if available
                target_basename = f"{playlist_index}. {base_title}.{base_ext}" if playlist_index is not None else f"{base_title}.{base_ext}"
            else:
                target_basename = f"{base_title}.{base_ext}"
            # **تعديل: استخدام دالة التنظيف المستوردة** **Modification: Use imported clean function**
            target_basename = clean_filename(target_basename)
        else:
            # إذا لم تكن هناك معلومات، فقط نظف الاسم الحالي If no info, just clean the current name
            # **تعديل: استخدام دالة التنظيف المستوردة** **Modification: Use imported clean function**
            target_basename = clean_filename(current_basename)

        # بناء المسار الكامل الجديد Build the new full filepath object
        new_final_filepath_obj = expected_final_path_obj.with_name(target_basename)
        final_message = f"Download complete: {target_basename}" # رسالة النجاح الافتراضية Default success message

        # إعادة التسمية فقط إذا كان الاسم المستهدف مختلفًا Rename only if target name is different
        if new_final_filepath_obj != expected_final_path_obj:
            print(f"Attempting rename: '{current_basename}' -> '{target_basename}'")
            try:
                # التأكد من وجود الملف قبل إعادة التسمية Ensure file exists before renaming
                if expected_final_path_obj.exists():
                    expected_final_path_obj.rename(new_final_filepath_obj)
                    print(f"Rename successful: '{new_final_filepath_obj}'")
                    self._cleaned_up_path = str(new_final_filepath_obj) # تسجيل المسار النظيف Mark cleaned path
                else:
                    # حالة نادرة: الملف اختفى قبل إعادة التسمية Rare case: file disappeared before rename
                    print(f"File disappeared before rename: {expected_final_path_obj}")
                    final_message = f"Warning: Download ok, but file missing before rename ({current_basename})"
                    self._cleaned_up_path = None # لم يتم التنظيف Not cleaned
            except OSError as e:
                # خطأ أثناء إعادة التسمية (مثل الملف قيد الاستخدام) Error during rename (e.g., file in use)
                print(f"Error during final rename for '{current_basename}': {e}")
                final_message = f"Download complete (rename failed): {current_basename}"
                self._cleaned_up_path = str(expected_final_path_obj) # اعتبر المسار القديم هو النظيف Consider old path as cleaned
        else:
            # الاسم كان صحيحًا بالفعل Name was already correct
            print("Filename already correct. No rename needed.")
            self._cleaned_up_path = str(expected_final_path_obj) # تسجيل المسار النظيف Mark cleaned path

        # ملاحظة: رسالة الحالة النهائية ("Finished: ...") يتم تحديثها بواسطة الهوك
        # Note: The final status message ("Finished: ...") is updated by the hook

    def run(self):
        """
        نقطة الدخول لتشغيل عملية التحميل في خيط منفصل.
        Entry point to run the download process in a separate thread.
        Handles exceptions and ensures the finished_callback is always called.
        """
        download_error_occurred = False
        self._cleaned_up_path = None # التأكد من إعادة تعيينه Ensure it's reset

        try:
            # تشغيل منطق التحميل الأساسي Run core download logic
            self._download_core()
        except DownloadCancelled as e:
            # التعامل مع الإلغاء Handle cancellation
            self.status_callback(str(e))
            print(e)
            download_error_occurred = True
        except Exception as e:
            # التعامل مع أي خطأ فادح غير متوقع Handle any fatal unexpected error
            self._log_unexpected_error(e, "in main run loop")
            download_error_occurred = True
        finally:
            # التأكد من استدعاء الكول باك النهائي دائمًا Ensure final callback is always called
            print("Downloader: Reached finally block, calling finished_callback.")
            self.finished_callback()

    def _log_unexpected_error(self, e, context=""):
        """
        يسجل الأخطاء غير المتوقعة مع تتبع الخطأ ويحدث الحالة.
        Logs unexpected errors with traceback and updates status.
        """
        print(f"--- UNEXPECTED ERROR ({context}) ---")
        traceback.print_exc() # طباعة تتبع الخطأ الكامل Print full traceback
        print("------------------------------------")
        # تحديث رسالة الحالة برسالة خطأ عامة Update status with a generic error message
        self.status_callback(f"Unexpected Error ({type(e).__name__})! Check logs for details.")
        print(f"Unexpected Error during download ({context}): {e}")