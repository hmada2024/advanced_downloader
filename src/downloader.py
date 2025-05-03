# src/downloader.py
# -- ملف يحتوي على كلاس التحميل الرئيسي --
# Purpose: Contains the main Downloader class responsible for the download process.

import os
import yt_dlp
import sys
from pathlib import Path # <-- التأكد من وجود هذا الاستيراد Ensure this import exists
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
        # لم نعد بحاجة إلى final_known_path أو last_downloaded_info أو _cleaned_up_path لغرض التنظيف
        # We no longer need final_known_path, last_downloaded_info or _cleaned_up_path for cleanup purposes
        self._current_processing_playlist_idx_display = 1 # الفهرس المطلق للعنصر الحالي (للعرض) Absolute index of current item (for display)
        self._last_hook_playlist_index = 0 # آخر فهرس مطلق تم رؤيته في الهوك Last absolute index seen in hook
        self._processed_selected_count = 0 # عدد العناصر المحددة التي تم الانتهاء من معالجتها Count of selected items finished processing

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
        خطاف تقدم yt-dlp لمعالجة تحديثات الحالة والتقدم (قبل المعالجات اللاحقة).
        yt-dlp progress hook to handle status and progress updates (before postprocessors).
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
            # هذا الهوك الآن يُستخدم بشكل أساسي لتحديث الحالة إلى "Processing..." أو "Finished: ..." قبل الدمج
            # This hook is now primarily used to update status to "Processing..." or "Finished: ..." before merging
            filepath = info_dict.get("filepath") or d.get("filename")
            if filepath:
                # --- لا نخزن final_known_path أو last_downloaded_info هنا لغرض التنظيف ---
                # --- We don't store final_known_path or last_downloaded_info here for cleanup ---
                print(f"Hook 'finished' (pre-postprocessing): Path reported '{filepath}'.")

                base_filename = os.path.basename(filepath)
                # التحقق مما إذا كان هذا هو الملف النهائي المتوقع (له امتداد شائع) Check if this is the expected final file (has a common extension)
                # ملاحظة: هذا قد لا يكون دقيقًا إذا كان الامتداد المؤقت هو نفسه النهائي (نادر) Note: This might be inaccurate if temp ext matches final (rare)
                final_ext_present = any(
                    base_filename.lower().endswith(ext)
                    for ext in [".mp4", ".mp3", ".mkv", ".webm", ".opus", ".ogg"]
                )
                title = info_dict.get("title")
                display_name = clean_filename(title or base_filename)

                if final_ext_present:
                    status_msg = f"Finished: {display_name}" # <- هذه الرسالة قد تكون مؤقتة حتى يتم الدمج This message might be temporary until merging
                    # زيادة عداد العناصر المحددة المعالجة فقط عند الانتهاء من الملف النهائي
                    # Increment processed selected count only when the final file is done
                    # !! هذا الافتراض قد لا يكون دقيقًا 100% إذا كان الدمج يأخذ وقتًا طويلاً !!
                    # !! This assumption might not be 100% accurate if merging takes long !!
                    # سنبقيه الآن، ولكن يجب أن نكون على علم به We'll keep it for now, but be aware
                    self._processed_selected_count += 1
                    print(
                        f"Processed selected items count incremented in pre-hook to: {self._processed_selected_count}"
                    )
                else:
                    # إذا لم يكن ملفًا نهائيًا، فهي مرحلة معالجة وسيطة If not a final file, it's an intermediate processing stage
                    status_msg = f"Processing: {display_name}..."

                self.status_callback(status_msg)
                self.progress_callback(1.0) # التقدم 100% لهذه المرحلة Progress 100% for this stage
            else:
                print("Hook 'finished' (pre-postprocessing) but no filepath found.")
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
                    # استخدام نفس العداد _processed_selected_count الذي يتم زيادته في status='finished'
                    # Use the same _processed_selected_count incremented in status='finished'
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
                status_lines.append(f"Speed: {speed_str} | ETA: {eta_str}")

                # تجميع الأسطر وتحديث الواجهة Combine lines and update UI
                status_msg = "\n".join(status_lines)
                self.status_callback(status_msg)
                # ------------------------------------
            else:
                self.status_callback(f"Status: {d.get('status', 'Connecting')}...")

        elif status == "error":
            self.status_callback("Error during download process reported by yt-dlp.")
            print(f"yt-dlp hook reported error: {d.get('error', 'Unknown yt-dlp error')}")


    # +++ دالة خطاف ما بعد المعالجة الجديدة +++ New postprocessor hook function +++
    def _postprocessor_hook(self, d):
        """
        Hook يُستدعى بعد انتهاء المعالجات اللاحقة (مثل الدمج أو تحويل الصوت).
        Hook called after postprocessors (like Merger or FFmpegExtractAudio) finish.
        مسؤول عن التحقق من الملف النهائي وإعادة تسميته إذا لزم الأمر.
        Responsible for checking the final file and renaming if needed.
        """
        print(f"Postprocessor Hook called with status: {d.get('status')}, postprocessor: {d.get('postprocessor')}") # للدييباج For debugging

        # العمل فقط عند انتهاء المعالج اللاحق بنجاح Act only when the postprocessor finishes successfully
        if d['status'] == 'finished':
            info_dict = d.get('info_dict', {})
            # المسار النهائي الفعلي يجب أن يكون موجودًا في info_dict الآن The actual final path should be in info_dict now
            final_filepath = info_dict.get('filepath')

            # التحقق من وجود المسار وأنه ملف فعلي Check if path exists and is a file
            if not final_filepath or not Path(final_filepath).is_file():
                print(f"Postprocessor Error: Final file path '{final_filepath}' not found or missing after postprocessing.")
                # اختياري: إبلاغ المستخدم عن مشكلة في المعالجة اللاحقة Optional: Inform user about postprocessing issue
                # title_for_error = info_dict.get('title', 'Unknown video')
                # self.status_callback(f"Warning: Postprocessing finished for '{title_for_error}' but final file is missing.")
                return # لا يمكن فعل شيء آخر Cannot do anything else

            print(f"Postprocessor Hook: Final file confirmed at '{final_filepath}'. Proceeding with rename check.")
            expected_final_path_obj = Path(final_filepath)
            current_basename = expected_final_path_obj.name
            target_basename = current_basename # الاسم المستهدف افتراضيًا

            # إعادة بناء الاسم المستهدف المثالي (نفس المنطق من cleanup_final_file القديم)
            # Reconstruct the ideal target name (same logic as old cleanup_final_file)
            base_title = info_dict.get("title", "")
            # الحصول على الامتداد الصحيح من المسار الفعلي Get correct extension from actual path
            base_ext = expected_final_path_obj.suffix.lstrip(".")

            # التحقق مما إذا كان جزءًا من قائمة تشغيل (باستخدام info_dict الحالي) Check if part of playlist (using current info_dict)
            playlist_index = info_dict.get("playlist_index")
            if playlist_index is not None:
                # *** بناء الاسم الصحيح مع المسافة *** Correct name construction WITH space
                target_basename = f"{playlist_index}. {base_title}.{base_ext}"
            else: # فيديو مفرد Single video
                target_basename = f"{base_title}.{base_ext}"

            # تنظيف الاسم المستهدف Clean the target name
            target_basename = clean_filename(target_basename)

            # إعادة التسمية فقط إذا كان الاسم مختلفًا Rename only if the name differs
            if target_basename != current_basename:
                new_final_filepath_obj = expected_final_path_obj.with_name(target_basename)
                print(f"Postprocessor: Attempting rename: '{current_basename}' -> '{target_basename}'")
                try:
                    # إعادة تسمية الملف Rename the file
                    expected_final_path_obj.rename(new_final_filepath_obj)
                    print(f"Postprocessor: Rename successful: '{new_final_filepath_obj}'")
                    # اختياري: تحديث رسالة الحالة لتعكس الاسم الجديد Optional: Update status msg to reflect new name
                    # self.status_callback(f"Finished & Renamed: {target_basename}")
                except OSError as e:
                    # خطأ أثناء إعادة التسمية Error during rename
                    print(f"Postprocessor Error during rename for '{current_basename}': {e}")
                    # اختياري: إبلاغ المستخدم بفشل إعادة التسمية Optional: Inform user about rename failure
                    # self.status_callback(f"Finished (Rename Failed): {current_basename}")
            else:
                # الاسم كان صحيحًا بالفعل Name was already correct
                print(f"Postprocessor: Filename '{current_basename}' already correct. No rename needed.")

        elif d['status'] == 'started':
            # اختياري: طباعة رسالة عند بدء المعالج اللاحق Optional: Print message when postprocessor starts
            print(f"Postprocessor Hook: '{d.get('postprocessor')}' started.")
        # تجاهل الحالات الأخرى مثل 'progress' أو 'error' من المعالج اللاحق
        # Ignore other statuses like 'progress' or 'error' from the postprocessor


    def _build_format_string(self):
        """
        يبني سلسلة خيارات التنسيق والجودة لـ yt-dlp والمعالجات اللاحقة.
        Builds the format/quality option string for yt-dlp and postprocessors.
        Returns:
            tuple: (format_string, output_extension_hint, postprocessors_list)
        """
        # --- هذا المنطق يبقى كما هو --- This logic remains the same ---
        format_choice_lower = self.format_choice.lower()
        output_ext = "mp4"
        postprocessors = []
        final_format_string = None
        if not self.is_playlist and self.quality_format_id:
            final_format_string = self.quality_format_id
            print(f"Using specific quality format ID: {self.quality_format_id}")
            if "audio (mp3)" in format_choice_lower:
                print("Warning: MP3 format chosen despite specific quality ID selection. Will attempt audio extraction.")
                output_ext = "mp3"
                if self.ffmpeg_path:
                    postprocessors.append({
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    })
                else:
                    print("Error: MP3 conversion requires FFmpeg, which was not found.")
                    output_ext = None
        elif "audio (mp3)" in format_choice_lower:
            final_format_string = "bestaudio/best"
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
                output_ext = None
        elif self.is_playlist:
            final_format_string = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720][ext=mp4]/best[height<=720]"
            output_ext = "mp4"
            print("Using default playlist format (max 720p MP4)")
        else:
            height_limit = None
            if "<= 720p" in format_choice_lower: height_limit = 720
            elif "<= 480p" in format_choice_lower: height_limit = 480
            elif "<= 360p" in format_choice_lower: height_limit = 360

            if height_limit:
                final_format_string = f"bestvideo[height<={height_limit}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height_limit}]+bestaudio/best[height<={height_limit}][ext=mp4]/best[height<={height_limit}]"
                print(f"Using general format: max {height_limit}p MP4")
            else:
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
        self._current_processing_playlist_idx_display = 1
        self._last_hook_playlist_index = 0
        self._processed_selected_count = 0
        # --- لا حاجة لـ last_downloaded_info, final_known_path, _cleaned_up_path ---
        # --- No need for last_downloaded_info, final_known_path, _cleaned_up_path ---

        self._check_cancel("before starting download")

        # بناء نمط اسم الملف الناتج Build output filename template
        if self.is_playlist:
            outtmpl_pattern = os.path.join(self.save_path, "%(playlist_index)s. %(title)s.%(ext)s")
        else:
            outtmpl_pattern = os.path.join(self.save_path, "%(title)s.%(ext)s")

        # الحصول على خيارات التنسيق والمعالجات Build format options and postprocessors
        final_format_string, output_ext_hint, core_postprocessors = self._build_format_string()

        # بناء قاموس خيارات yt-dlp Build yt-dlp options dictionary
        ydl_opts = {
            "progress_hooks": [self._my_hook],    # خطاف التقدم (قبل المعالجة اللاحقة) Progress hook (before postprocessing)
            "outtmpl": outtmpl_pattern,          # نمط اسم الملف Output template
            "nocheckcertificate": True,         # تجاهل أخطاء الشهادة Ignore certificate errors
            "ignoreerrors": self.is_playlist,    # تجاهل الأخطاء في القوائم؟ Ignore errors in playlists?
            "merge_output_format": "mp4",       # محاولة الدمج إلى MP4 إن أمكن Try merging to MP4 if possible
            "postprocessors": core_postprocessors, # معالجات مثل FFmpegExtractAudio Postprocessors like FFmpegExtractAudio
            "restrictfilenames": False,         # عدم تقييد أسماء الملفات Don't restrict filenames
            # +++ إضافة خطاف ما بعد المعالجة +++ Add postprocessor hook +++
            'postprocessor_hooks': [self._postprocessor_hook],
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
            ydl_opts["noplaylist"] = True # تعطيل معالجة القائمة Disable playlist processing

        # إضافة خيار التنسيق إذا تم تحديده Add format option if determined
        if final_format_string:
            ydl_opts["format"] = final_format_string
        elif "format" in ydl_opts:
            del ydl_opts["format"]

        print("Final yt-dlp options:", ydl_opts)
        self.status_callback("Starting download...")
        self.progress_callback(0)

        self._check_cancel("right before calling ydl.download()")

        # --- تم تبسيط كتلة try/except --- Simplified try/except block ---
        try:
            # تشغيل التحميل باستخدام yt-dlp Run download using yt-dlp
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            # تم الانتهاء بدون خطأ من yt-dlp نفسه Finished without error from yt-dlp itself
            # تحقق من الإلغاء فورًا Check for cancellation immediately
            self._check_cancel("immediately after ydl.download() finished")

        except yt_dlp.utils.DownloadCancelled as e:
            # تم الإلغاء عبر الهوك أو check_cancel Raised by hook or check_cancel
            raise DownloadCancelled(str(e)) from e
        except yt_dlp.utils.DownloadError as dl_err:
            # خطأ أثناء التحميل أبلغه yt-dlp Error during download reported by yt-dlp
            error_message = str(dl_err).split("ERROR:")[-1].strip()
            print(f"Downloader yt-dlp DownloadError: {dl_err}")
            self.status_callback(f"Download Error: {error_message}")
            # سيتم التقاط هذا الخطأ في run() وسيتم استدعاء finished_callback
            # This error will be caught in run() and finished_callback will be called
        except Exception as e:
            # أي خطأ آخر غير متوقع Any other unexpected error
            self._log_unexpected_error(e, "during yt-dlp download execution")
            # سيتم التقاط هذا الخطأ في run() وسيتم استدعاء finished_callback
            # This error will be caught in run() and finished_callback will be called

        # --- لا يوجد تنظيف نهائي هنا --- No final cleanup here ---
        # سيتم التعامل مع إعادة التسمية في _postprocessor_hook
        # Renaming will be handled in _postprocessor_hook

    # --- تم حذف دالة _cleanup_final_file --- _cleanup_final_file function removed ---

    def run(self):
        """
        نقطة الدخول لتشغيل عملية التحميل في خيط منفصل.
        Entry point to run the download process in a separate thread.
        Handles exceptions and ensures the finished_callback is always called.
        """
        # download_error_occurred لم يعد له استخدام كبير هنا download_error_occurred not very useful here anymore
        # self._cleaned_up_path = None # تم حذفه Removed

        try:
            # تشغيل منطق التحميل الأساسي Run core download logic
            self._download_core()
            # إذا وصل الكود إلى هنا دون استثناءات من _download_core
            # If code reaches here without exceptions from _download_core
            # يمكننا افتراض أن yt-dlp أتم عمله (أو أبلغ عن أخطائه بنفسه)
            # We can assume yt-dlp finished its job (or reported its own errors)
            # سيتم استدعاء finished_callback في finally
            # finished_callback will be called in finally

        except DownloadCancelled as e:
            # التعامل مع الإلغاء Handle cancellation
            self.status_callback(str(e))
            print(e)
            # يعتبر خطأ لأغراض الواجهة Consider an error for UI purposes
        except Exception as e:
            # التعامل مع أي خطأ فادح غير متوقع Handle any fatal unexpected error caught here
            self._log_unexpected_error(e, "in main run loop")
            # يعتبر خطأ لأغراض الواجهة Consider an error for UI purposes
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
        traceback.print_exc()
        print("------------------------------------")
        self.status_callback(f"Unexpected Error ({type(e).__name__})! Check logs for details.")
        print(f"Unexpected Error during download ({context}): {e}")