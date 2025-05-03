# src/downloader.py
# -- ملف يحتوي على كلاس التحميل الرئيسي --
# Purpose: Contains the main Downloader class responsible for the download process.

import os
import yt_dlp
import sys
from pathlib import Path
import traceback
import time
import humanize
import contextlib
import re  # لاستخراج الدقة من خيار الجودة To extract resolution from quality choice

# الاستيرادات من الحزمة الحالية Imports from current package
from .exceptions import DownloadCancelled
from .logic_utils import clean_filename


class Downloader:
    """
    كلاس مسؤول عن عملية تحميل الفيديو/الصوت ومعالجته باستخدام yt-dlp.
    Class responsible for downloading and processing video/audio using yt-dlp.
    """

    # --- تعديل: إزالة quality_format_id ---
    def __init__(
        self,
        url,
        save_path,
        format_choice,  # الخيار العام من القائمة المنسدلة العلوية General choice from top dropdown
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
        self.url = url
        self.save_path = save_path
        self.format_choice = format_choice  # تخزين الخيار العام Store general choice
        self.is_playlist = is_playlist
        self.playlist_items = playlist_items
        self.selected_items_count = selected_items_count
        self.total_playlist_count = total_playlist_count
        self.ffmpeg_path = ffmpeg_path
        self.cancel_event = cancel_event
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback

        # متغيرات داخلية لتتبع حالة تقدم القائمة Internal variables for tracking playlist progress status
        self._current_processing_playlist_idx_display = (
            1  # فهرس العنصر المطلق للعرض Absolute item index for display
        )
        self._last_hook_playlist_index = (
            0  # آخر فهرس تم الإبلاغ عنه من yt-dlp Last index reported by yt-dlp
        )
        self._processed_selected_count = 0  # عداد العناصر التي تمت معالجتها من التحديد Counter for processed selected items

    def _check_cancel(self, stage=""):
        """يتحقق من طلب الإلغاء ويرفع استثناءً إذا تم طلبه."""
        """Checks for cancellation request and raises if requested."""
        if self.cancel_event.is_set():
            raise DownloadCancelled(f"Download cancelled {stage}.")

    def _my_hook(self, d):
        """
        خطاف التقدم لـ yt-dlp، يُستدعى بشكل دوري أثناء التحميل والمعالجة.
        Progress hook for yt-dlp, called periodically during download and processing.
        """
        # التحقق من الإلغاء أولاً Check for cancellation first
        try:
            self._check_cancel("during progress hook")
        except DownloadCancelled as e:
            # yt-dlp يتوقع نوع خطأ محدد للإلغاء yt-dlp expects a specific error type for cancellation
            raise yt_dlp.utils.DownloadCancelled(str(e)) from e

        status = d.get("status")
        info_dict = d.get(
            "info_dict", {}
        )  # قد لا يكون متاحًا دائمًا May not always be available
        hook_playlist_index = info_dict.get(
            "playlist_index"
        )  # فهرس العنصر الحالي في القائمة (إذا كانت قائمة) Current item index in playlist (if playlist)

        # تحديث فهرس العرض للقائمة عند بدء عنصر جديد Update display index for playlist when a new item starts
        if (
            self.is_playlist
            and hook_playlist_index is not None
            and hook_playlist_index > self._last_hook_playlist_index
        ):
            self._current_processing_playlist_idx_display = hook_playlist_index
            self._last_hook_playlist_index = hook_playlist_index
            # ملاحظة: لا نزيد عداد العناصر المعالجة هنا، فقط عند انتهاء المعالجة النهائية
            # Note: We don't increment the processed count here, only on final processing finish

        if status == "finished":
            # هذه الحالة غالبًا ما تعني انتهاء التحميل الأولي قبل المعالجة
            # This status often means initial download finished before postprocessing
            if filepath := info_dict.get("filepath") or d.get("filename"):
                # استدعاء دالة مساعدة لتحديث الحالة بناءً على الملف Call helper to update status based on file
                self._update_status_on_finish_or_process(
                    filepath, info_dict, is_final=False
                )
            else:
                self.status_callback("Processing...")  # رسالة عامة General message
            self.progress_callback(
                1.0
            )  # اكتمل التقدم لهذه المرحلة Progress complete for this stage

        elif status == "downloading":
            # حساب وعرض تفاصيل التقدم Calculate and display progress details
            downloaded_bytes = d.get("downloaded_bytes")
            if downloaded_bytes is not None:
                # استدعاء دالة مساعدة لتنسيق وعرض الحالة Call helper to format and display status
                self._format_and_display_download_status(d, downloaded_bytes)
            else:
                # حالة غير متوقعة أثناء التحميل Unexpected state during download
                self.status_callback(f"Status: {d.get('status', 'Connecting')}...")

        elif status == "error":
            # الإبلاغ عن خطأ من yt-dlp Report error from yt-dlp
            self.status_callback("Error during download/processing reported by yt-dlp.")
            print(
                f"yt-dlp hook reported error: {d.get('error', 'Unknown yt-dlp error')}"
            )
            # لا نرفع استثناءً هنا، نعتمد على آلية yt-dlp للإبلاغ عن الخطأ النهائي
            # We don't raise here, rely on yt-dlp's mechanism for final error reporting

    def _format_and_display_download_status(self, d, downloaded_bytes):
        """تنسيق وعرض رسالة الحالة أثناء التحميل."""
        """Formats and displays the status message during download."""
        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate")
        progress = 0.0
        percentage_str = "0.0%"
        if total_bytes and total_bytes > 0:
            progress = max(0.0, min(1.0, downloaded_bytes / total_bytes))
            percentage_str = f"{progress:.1%}"

        self.progress_callback(progress)  # تحديث شريط التقدم Update progress bar

        status_lines = (
            []
        )  # قائمة لتجميع أسطر رسالة الحالة List to gather status message lines

        # السطر الأول: معلومات العنصر (إذا كانت قائمة) Line 1: Item info (if playlist)
        if self.is_playlist:
            self._extracted_from__format_and_display_download_status_17(status_lines)
        else:
            status_lines.append(
                "Downloading Video"
            )  # رسالة بسيطة للفيديو المفرد Simple message for single video

        # السطر الثاني: معلومات التقدم والحجم Line 2: Progress and size info
        downloaded_size_str = humanize.naturalsize(downloaded_bytes, binary=True)
        total_size_str = (
            humanize.naturalsize(total_bytes, binary=True)
            if total_bytes
            else "Unknown size"
        )
        status_lines.append(
            f"Progress: {percentage_str} ({downloaded_size_str} / {total_size_str})"
        )

        # السطر الثالث: معلومات السرعة والوقت المتبقي Line 3: Speed and ETA info
        speed = d.get("speed")
        speed_str = (
            f"{humanize.naturalsize(speed, binary=True, gnu=True)}/s"
            if speed
            else "Calculating..."
        )
        eta = d.get("eta")
        eta_str = "Calculating..."
        with contextlib.suppress(
            TypeError, ValueError
        ):  # تجنب الأخطاء إذا كانت eta غير رقمية Ignore errors if eta is non-numeric
            if eta is not None and isinstance(eta, (int, float)) and eta >= 0:
                eta_str = f"{int(round(eta))} seconds remaining"
        status_lines.append(f"Speed: {speed_str} | ETA: {eta_str}")

        # تجميع الأسطر في رسالة واحدة وإرسالها للواجهة Combine lines into one message and send to UI
        status_msg = "\n".join(status_lines)
        self.status_callback(status_msg)

    # TODO Rename this here and in `_format_and_display_download_status`
    def _extracted_from__format_and_display_download_status_17(self, status_lines):
        current_absolute_index = self._current_processing_playlist_idx_display
        total_absolute_str = (
            f"out of {self.total_playlist_count} total"
            if self.total_playlist_count > 0
            else ""
        )
        status_lines.append(f"Video {current_absolute_index} {total_absolute_str}")

        # حساب ترتيب العنصر الحالي ضمن العناصر المحددة Calculate current item order within selected items
        index_in_selection = self._processed_selected_count + 1
        # التأكد من عدم تجاوز العدد الإجمالي المختار Ensure not exceeding total selected count
        index_in_selection = min(index_in_selection, self.selected_items_count)
        remaining_in_selection = max(
            0, self.selected_items_count - self._processed_selected_count
        )
        status_lines.append(
            f"Selected: {index_in_selection} of {self.selected_items_count} ({remaining_in_selection} remaining)"
        )

    def _update_status_on_finish_or_process(self, filepath, info_dict, is_final=False):
        """تحديث رسالة الحالة عند انتهاء تحميل ملف أو معالجته النهائية."""
        """Updates status message when a file finishes downloading or final processing."""
        base_filename = os.path.basename(filepath)
        # التحقق مما إذا كان الامتداد هو امتداد نهائي شائع Check if extension is a common final one
        final_ext_present = any(
            base_filename.lower().endswith(ext)
            for ext in [".mp4", ".mp3", ".mkv", ".webm", ".opus", ".ogg"]
        )

        title = info_dict.get("title")
        # تنظيف الاسم للعرض Clean the name for display
        display_name = clean_filename(title or base_filename)

        if is_final and final_ext_present:
            # إذا كانت هذه هي المعالجة النهائية والامتداد صحيح If this is the final processing and extension is correct
            status_msg = f"Finished: {display_name}"
            # زيادة عداد العناصر المكتملة فقط هنا Increment completed items counter only here
            self._processed_selected_count += 1
        else:
            # إذا كانت مرحلة وسيطة أو امتداد غير نهائي If intermediate stage or non-final extension
            status_msg = f"Processing: {display_name}..."

        self.status_callback(status_msg)

    def _postprocessor_hook(self, d):
        """
        خطاف ما بعد المعالجة لـ yt-dlp، يُستدعى عند بدء وانتهاء عمليات المعالجة (مثل الدمج، تحويل الصوت).
        Postprocessor hook for yt-dlp, called when postprocessing operations start and finish (e.g., merging, audio conversion).
        """
        status = d.get("status")
        postprocessor_name = d.get("postprocessor")
        print(f"Postprocessor Hook: Status='{status}', PP='{postprocessor_name}'")

        if status == "finished":
            info_dict = d.get("info_dict", {})
            final_filepath = info_dict.get(
                "filepath"
            )  # المسار النهائي بعد المعالجة Final path after processing

            if not final_filepath or not Path(final_filepath).is_file():
                print(
                    f"Postprocessor Error: Final file path '{final_filepath}' not found or missing after postprocessing '{postprocessor_name}'."
                )
                # قد نرغب في الإبلاغ عن خطأ هنا للواجهة؟ Maybe report an error to the UI here?
                # self.status_callback(f"Error: Postprocessing failed for {postprocessor_name}")
                return  # لا يمكن المتابعة بدون ملف Can't proceed without the file

            print(
                f"Postprocessor Hook: Final file confirmed at '{final_filepath}'. Proceeding with rename/cleanup."
            )
            # تحديث الحالة بأن المعالجة النهائية تمت Update status that final processing is done
            self._update_status_on_finish_or_process(
                final_filepath, info_dict, is_final=True
            )

            # --- منطق إعادة التسمية النهائي --- Final Renaming Logic ---
            expected_final_path_obj = Path(final_filepath)
            current_basename = expected_final_path_obj.name
            target_basename = current_basename  # الاسم المستهدف افتراضيًا هو الحالي Target name defaults to current

            # بناء الاسم المستهدف بناءً على المعلومات المتاحة Build target name based on available info
            base_title = info_dict.get(
                "title", "Untitled"
            )  # استخدام عنوان الفيديو Use video title
            base_ext = expected_final_path_obj.suffix.lstrip(
                "."
            )  # الحصول على الامتداد الحالي Get current extension
            playlist_index = info_dict.get(
                "playlist_index"
            )  # الحصول على فهرس القائمة إن وجد Get playlist index if available

            if self.is_playlist and playlist_index is not None:
                # إضافة رقم تسلسلي للقوائم Add sequence number for playlists
                target_basename = f"{playlist_index}. {base_title}.{base_ext}"
            else:
                # استخدام العنوان والامتداد فقط للفيديو المفرد Use title and extension only for single video
                target_basename = f"{base_title}.{base_ext}"

            # تنظيف الاسم المستهدف Clean the target name
            target_basename = clean_filename(target_basename)

            # إعادة التسمية فقط إذا كان الاسم المستهدف مختلفًا عن الحالي Rename only if target differs from current
            if target_basename != current_basename:
                new_final_filepath_obj = expected_final_path_obj.with_name(
                    target_basename
                )
                print(
                    f"Postprocessor: Attempting rename: '{current_basename}' -> '{target_basename}'"
                )
                try:
                    # تنفيذ إعادة التسمية Perform rename
                    expected_final_path_obj.rename(new_final_filepath_obj)
                    print(
                        f"Postprocessor: Rename successful: '{new_final_filepath_obj}'"
                    )
                except OSError as e:
                    # الإبلاغ عن خطأ في حالة فشل إعادة التسمية Report error if rename fails
                    print(
                        f"Postprocessor Error during rename for '{current_basename}': {e}"
                    )
                    self.status_callback(
                        f"Warning: Could not rename '{current_basename}' due to OS error."
                    )
            else:
                print(
                    f"Postprocessor: Filename '{current_basename}' already correct. No rename needed."
                )

        elif status == "started":
            # طباعة رسالة عند بدء المعالج Print message when processor starts
            print(f"Postprocessor Hook: '{postprocessor_name}' started.")

    def _build_format_string(self):
        """
        يبني سلسلة الصيغة المعقدة لـ yt-dlp بناءً على اختيار المستخدم العام للجودة.
        Builds the complex format string for yt-dlp based on the user's general quality choice.
        Returns:
            tuple: (final_format_string, output_ext, postprocessors_list)
        """
        # --- هذا المنطق يعتمد فقط على self.format_choice الآن ---
        # --- This logic now depends only on self.format_choice ---
        output_ext = "mp4"  # الامتداد الافتراضي Default extension
        postprocessors = []  # قائمة المعالجات اللاحقة Postprocessors list
        final_format_string = None  # سلسلة الصيغة النهائية Final format string

        print(f"BuildFormat: Received format choice: '{self.format_choice}'")

        if self.format_choice == "Download Audio Only (MP3)":
            # حالة تحميل الصوت فقط Case: Download Audio Only
            # اطلب أفضل صوت بشكل عام Ask for best audio overall
            final_format_string = "bestaudio/best"
            output_ext = "mp3"  # الامتداد المطلوب mp3 Required extension mp3
            if self.ffmpeg_path:
                # إذا كان FFmpeg متاحًا، أضف معالج لتحويل الصوت إلى MP3
                # If FFmpeg available, add postprocessor to convert audio to MP3
                postprocessors.append(
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",  # جودة MP3 (يمكن تعديلها) MP3 quality (adjustable)
                    }
                )
                # --- إضافة التأكيد على حذف الفيديو المؤقت (مهم للصوت فقط) ---
                # --- Add confirmation to delete temporary video (important for audio only) ---
                # لا نحتاج key: 'KeepVideo' هنا، سيتم تعيينه في ydl_opts
                # We don't need key: 'KeepVideo' here, it will be set in ydl_opts
                print(
                    "BuildFormat: Selecting best audio for MP3 conversion (FFmpeg found)."
                )
            else:
                # إذا لم يتم العثور على FFmpeg، حمل أفضل صوت متاح ولكن حذر المستخدم
                # If FFmpeg not found, download best available audio but warn user
                print(
                    "BuildFormat Warning: MP3 requested but FFmpeg not found. Downloading best audio format available."
                )
                output_ext = None  # اسمح لـ yt-dlp بتحديد الامتداد Let yt-dlp determine extension
            print(
                f"BuildFormat: Audio mode. Format: '{final_format_string}', Target Ext: {output_ext}"
            )

        else:
            # حالة تحميل الفيديو (مع الصوت) Case: Download Video (with audio)
            height_limit = None
            # محاولة استخراج حد الدقة من النص Try to extract height limit from text
            if match := re.search(r"\b(\d{3,4})p\b", self.format_choice):
                height_limit = int(match[1])
                print(f"BuildFormat: Found height limit: {height_limit}p")
            else:
                # إذا فشل الاستخراج (نص غير متوقع)، استخدم قيمة افتراضية وحذر
                # If extraction fails (unexpected text), use a default and warn
                print(
                    f"BuildFormat Warning: Could not parse height from format choice '{self.format_choice}'. Falling back to default 720p."
                )
                height_limit = 720

            # بناء سلسلة الصيغة لطلب أفضل فيديو ضمن الحد + أفضل صوت، مع بدائل
            # Build format string asking for best video within limit + best audio, with fallbacks
            final_format_string = (
                f"bestvideo[height<={height_limit}][ext=mp4]+bestaudio[ext=m4a]/"  # أفضل فيديو MP4 + صوت M4A
                f"bestvideo[height<={height_limit}]+bestaudio/"  # أفضل فيديو (أي امتداد) + أفضل صوت (أي امتداد)
                f"best[height<={height_limit}][ext=mp4]/"  # أفضل ملف مدمج MP4 ضمن الحد
                f"best[height<={height_limit}]"  # أفضل ملف مدمج (أي امتداد) ضمن الحد
            )
            output_ext = (
                "mp4"  # الهدف دائمًا هو MP4 للفيديو Target is always MP4 for video
            )
            # لا حاجة لمعالجات لاحقة هنا (الدمج يتم تلقائيًا بواسطة الصيغة)
            # No specific postprocessors needed here (merge happens automatically via format string)
            postprocessors = []
            print(
                f"BuildFormat: Video mode. Limit: {height_limit}p, Format: '{final_format_string}', Target Ext: {output_ext}"
            )

        return final_format_string, output_ext, postprocessors

    def _download_core(self):
        """
        ينفذ عملية التحميل الأساسية باستخدام yt-dlp.
        Executes the core download process using yt-dlp.
        """
        # إعادة تعيين عدادات الحالة الداخلية Reset internal status counters
        self._current_processing_playlist_idx_display = 1
        self._last_hook_playlist_index = 0
        self._processed_selected_count = 0

        self._check_cancel("before starting download")

        # بناء نمط اسم الملف الناتج Build output filename template
        if self.is_playlist:
            # استخدام الفهرس والعنوان للقوائم Use index and title for playlists
            # ملاحظة: سيتم تنظيف الاسم وإعادة تسميته بواسطة خطاف ما بعد المعالجة
            # Note: Name will be cleaned and potentially renamed by postprocessor hook
            outtmpl_pattern = os.path.join(
                self.save_path, "%(playlist_index)s. %(title)s.%(ext)s"
            )
        else:
            # استخدام العنوان فقط للفيديو المفرد Use title only for single video
            outtmpl_pattern = os.path.join(self.save_path, "%(title)s.%(ext)s")

        # الحصول على سلسلة الصيغة والامتداد والمعالجات بناءً على اختيار المستخدم
        # Get format string, extension, and postprocessors based on user choice
        final_format_string, output_ext_hint, core_postprocessors = (
            self._build_format_string()
        )

        # إعداد خيارات yt-dlp الأساسية Setup basic yt-dlp options
        ydl_opts = {
            "progress_hooks": [self._my_hook],  # خطاف التقدم Progress hook
            "postprocessor_hooks": [
                self._postprocessor_hook
            ],  # خطاف ما بعد المعالجة Postprocessor hook
            "outtmpl": outtmpl_pattern,  # نمط اسم الملف Output template
            "nocheckcertificate": True,  # تجاهل التحقق من الشهادة Ignore certificate check
            "ignoreerrors": self.is_playlist,  # تجاهل الأخطاء في القوائم Ignore errors in playlists
            "merge_output_format": "mp4",  # دمج إلى MP4 إن أمكن Merge to MP4 if possible
            "postprocessors": core_postprocessors,  # المعالجات المحددة (مثل تحويل MP3) Specific postprocessors (like MP3 convert)
            "restrictfilenames": False,  # عدم تقييد أسماء الملفات بشكل مفرط Don't excessively restrict filenames
            "keepvideo": False,  # *** مهم: حذف الملفات المؤقتة بعد المعالجة *** Important: Delete intermediate files after processing
            # 'writethumbnail': True, # <-- يمكن تفعيل هذا إذا أردت تحميل الصورة المصغرة Also download thumbnail?
            # 'skip_download': True, # <-- للدييباج فقط: لا تقم بالتحميل الفعلي For debugging only: don't actually download
        }

        # إضافة مسار FFmpeg إذا تم العثور عليه Add FFmpeg path if found
        if self.ffmpeg_path:
            ydl_opts["ffmpeg_location"] = self.ffmpeg_path
        elif (
            core_postprocessors
        ):  # إذا كانت هناك حاجة لـ FFmpeg ولم يتم العثور عليه If FFmpeg needed but not found
            self.status_callback(
                "Warning: FFmpeg needed for conversion but not found. Process might fail."
            )

        # تحديد عناصر القائمة للتحميل (إذا كانت قائمة) Specify playlist items to download (if playlist)
        if self.is_playlist and self.playlist_items:
            ydl_opts["playlist_items"] = self.playlist_items

        # تعيين سلسلة الصيغة إذا تم تحديدها Set format string if determined
        if final_format_string:
            ydl_opts["format"] = final_format_string
        # --- إزالة التحقق من quality_format_id ---
        # elif self.quality_format_id: <-- Block removed
        # ydl_opts['format'] = self.quality_format_id <-- Block removed
        elif "format" in ydl_opts:
            # التأكد من إزالة أي صيغة افتراضية قديمة إذا لم يتم تحديد شيء
            # Ensure any old default format is removed if nothing specific was chosen
            del ydl_opts["format"]

        print(
            "Final yt-dlp options:", ydl_opts
        )  # طباعة الخيارات النهائية للتحقق Print final options for verification
        self.status_callback("Starting download...")
        self.progress_callback(0)  # بدء التقدم من الصفر Start progress at zero

        self._check_cancel("right before calling ydl.download()")

        # تنفيذ التحميل داخل كتلة try...except Execute download within try...except block
        try:
            # استخدام مدير السياق لـ yt-dlp Use context manager for yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # بدء التحميل Start the download
                ydl.download([self.url])

            # التحقق من الإلغاء مباشرة بعد الانتهاء Check for cancellation immediately after finish
            self._check_cancel("immediately after ydl.download() finished")

        except yt_dlp.utils.DownloadCancelled as e:
            # التعامل مع الإلغاء الذي تم رفعه من الخطافات أو _check_cancel
            # Handle cancellation raised from hooks or _check_cancel
            raise DownloadCancelled(
                str(e)
            ) from e  # إعادة رفعه كاستثناء مخصص Re-raise as our custom exception
        except yt_dlp.utils.DownloadError as dl_err:
            # التعامل مع أخطاء التحميل المحددة من yt-dlp Handle specific download errors from yt-dlp
            # محاولة استخراج رسالة الخطأ الرئيسية Try to extract the main error message
            error_message = str(dl_err).split("ERROR:")[-1].strip()
            print(f"Downloader yt-dlp DownloadError: {dl_err}")
            # إرسال رسالة الخطأ للواجهة Send error message to UI
            self.status_callback(f"Download Error: {error_message}")
            # لا نرفع استثناءً هنا، انتهت العملية بخطأ Don't raise here, operation finished with error
        except Exception as e:
            # التعامل مع أي أخطاء أخرى غير متوقعة Handle any other unexpected errors
            self._log_unexpected_error(e, "during yt-dlp download execution")
            # لا نرفع استثناءً هنا، انتهت العملية بخطأ Don't raise here, operation finished with error

    def run(self):
        """
        نقطة الدخول الرئيسية لتشغيل عملية التحميل.
        Main entry point to run the download process.
        Handles exceptions and ensures the finished_callback is always called.
        """
        try:
            # تشغيل المنطق الأساسي للتحميل Run the core download logic
            self._download_core()
        except DownloadCancelled as e:
            # التعامل مع الإلغاء الذي تم رفعه Handle cancellation raised
            self.status_callback(str(e))
            print(e)
        except Exception as e:
            # التعامل مع أي خطأ فادح غير متوقع قد يحدث خارج _download_core
            # Handle any fatal unexpected error outside _download_core
            self._log_unexpected_error(e, "in main run loop")
        finally:
            # التأكد من استدعاء الكول باك النهائي دائمًا Ensure the final callback is always called
            print("Downloader: Reached finally block, calling finished_callback.")
            self.finished_callback()

    def _log_unexpected_error(self, e, context=""):
        """يسجل الأخطاء غير المتوقعة."""
        """Logs unexpected errors."""
        print(f"--- UNEXPECTED ERROR ({context}) ---")
        traceback.print_exc()  # طباعة تتبع الخطأ الكامل Print full traceback
        print("------------------------------------")
        # إرسال رسالة خطأ عامة للواجهة Send general error message to UI
        self.status_callback(
            f"Unexpected Error ({type(e).__name__})! Check logs for details."
        )
        print(f"Unexpected Error during download ({context}): {e}")
