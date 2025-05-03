# -- ملف كلاس الواجهة الرسومية الرئيسي للتطبيق والمنسق بين المكونات --
# Purpose: Main application UI window class and coordinator between components.

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os

# استيراد مكونات الواجهة المنفصلة (باستخدام الاستيراد النسبي)
# Import separate UI components (using relative imports)
from .ui_components.top_input_frame import TopInputFrame  # <-- تم التعديل: استخدام .
from .ui_components.options_control_frame import (
    OptionsControlFrame,
)  # <-- تم التعديل: استخدام .
from .ui_components.path_selection_frame import (
    PathSelectionFrame,
)  # <-- تم التعديل: استخدام .
from .ui_components.bottom_controls_frame import (
    BottomControlsFrame,
)  # <-- تم التعديل: استخدام .
from .ui_components.quality_selector import QualitySelector  # <-- تم التعديل: استخدام .
from .ui_components.playlist_selector import (
    PlaylistSelector,
)  # <-- تم التعديل: استخدام .


# الكلاس الرئيسي للواجهة، يرث من ctk.CTk (النافذة الرئيسية)
class UserInterface(ctk.CTk):
    def __init__(self, logic_handler):
        """
        تهيئة الواجهة الرسومية الرئيسية.
        """
        super().__init__()

        self.logic = logic_handler
        self.fetched_info = None
        self.current_operation = None

        # --- إعداد النافذة ---
        self.title("Advanced Downloader")
        self.geometry("850x750")  # الحجم من المرحلة الأولى
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- إعداد تخطيط الشبكة ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(6, weight=1)  # الصف الذي يحتوي على القائمة/الجودة يتمدد

        # --- إنشاء وتنسيق مكونات الواجهة ---
        self.top_frame_widget = TopInputFrame(self, fetch_command=self.fetch_video_info)
        self.top_frame_widget.grid(
            row=0, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="ew"
        )

        self.options_frame_widget = OptionsControlFrame(
            self, toggle_playlist_command=self.toggle_playlist_mode
        )
        self.options_frame_widget.grid(
            row=1, column=0, columnspan=3, padx=15, pady=5, sticky="ew"
        )

        self.path_frame_widget = PathSelectionFrame(
            self, browse_callback=self.browse_path_logic
        )
        self.path_frame_widget.grid(
            row=2, column=0, columnspan=3, padx=15, pady=5, sticky="ew"
        )

        self.dynamic_area_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(weight="bold")
        )
        self.dynamic_area_label.grid(
            row=3, column=0, columnspan=3, padx=20, pady=(10, 0), sticky="w"
        )

        # مكونات المنطقة الديناميكية (توضع في الشبكة لاحقًا)
        self.quality_selector_widget = QualitySelector(self)
        self.playlist_selector_widget = PlaylistSelector(self)
        # ملاحظة: QualitySelector الآن يوضع في الصف 5، و PlaylistSelector في الصف 6
        # Note: QualitySelector now placed in row 5, PlaylistSelector in row 6

        # وضع عناصر التحكم السفلية وشريط التقدم والحالة في الصفوف الأخيرة
        self.bottom_controls_widget = BottomControlsFrame(
            self,
            download_command=self.start_download_ui,
            cancel_command=self.cancel_operation_ui,
        )
        self.bottom_controls_widget.grid(
            row=7, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="ew"
        )

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(
            row=8, column=0, columnspan=3, padx=20, pady=(0, 5), sticky="ew"
        )
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(
            self, text="Enter URL and click Fetch Info.", text_color="gray"
        )
        self.status_label.grid(
            row=9, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="ew"
        )

        # --- الحالة الأولية ---
        self._enter_idle_state()

    # --- دوال إدارة الحالة ---
    def _enable_main_controls(self):
        self.top_frame_widget.enable_fetch()
        self.options_frame_widget.enable()
        self.path_frame_widget.enable()
        # تمكين مفتاح القائمة إذا كانت المعلومات قائمة فعلًا
        if self.fetched_info and isinstance(self.fetched_info.get("entries"), list):
            self.options_frame_widget.enable()
        elif not self.fetched_info:  # في حالة الخمول بدون معلومات
            self.options_frame_widget.enable()  # تمكينها بشكل عام
        # تعطيل المفتاح إذا لم تكن المعلومات قائمة
        elif self.fetched_info and not isinstance(
            self.fetched_info.get("entries"), list
        ):
            # self.options_frame_widget.format_combobox.configure(state="normal") # الكومبوبوكس يبقى ممكن
            self.options_frame_widget.playlist_switch.configure(state="disabled")

    def _enter_idle_state(self):
        """Reset UI to initial idle state."""
        self._enable_main_controls()
        self.bottom_controls_widget.disable_download(button_text="Download")
        self.bottom_controls_widget.hide_cancel_button()
        self.dynamic_area_label.configure(text="")
        # إخفاء وإعادة تعيين المكونات الديناميكية
        self.quality_selector_widget.grid_remove()
        self.quality_selector_widget.reset()
        self.playlist_selector_widget.grid_remove()
        self.playlist_selector_widget.reset()
        self.fetched_info = None  # مسح المعلومات المجوبة
        self.status_label.configure(
            text="Enter URL and click Fetch Info.", text_color="gray"
        )
        self.progress_bar.set(0)
        self.current_operation = None
        self.options_frame_widget.set_playlist_mode(False)  # إعادة تعيين مفتاح القائمة

    def _enter_fetching_state(self):
        """Set UI state during info fetching."""
        self.top_frame_widget.disable_fetch(button_text="Fetching...")
        self.options_frame_widget.disable()
        self.path_frame_widget.disable()
        self.bottom_controls_widget.disable_download()  # يبقى معطلًا
        self.bottom_controls_widget.show_cancel_button()  # إظهار زر الإلغاء
        self.status_label.configure(text="Fetching information...", text_color="orange")
        self.progress_bar.set(0)

    def _enter_info_fetched_state(self, is_playlist_mode):
        """Set UI state after info is fetched."""
        print(
            f"UI_Interface: Entering info fetched state. Playlist mode requested/set: {is_playlist_mode}"
        )
        self._enable_main_controls()  # تمكين الأزرار العلوية والخيارات
        self.bottom_controls_widget.hide_cancel_button()  # إخفاء زر الإلغاء

        # تمكين زر التحميل إذا كان المسار محددًا
        if self.path_frame_widget.get_path() and os.path.isdir(
            self.path_frame_widget.get_path()
        ):
            self.bottom_controls_widget.enable_download(
                button_text="Download Selection"
            )
        else:
            self.bottom_controls_widget.disable_download(
                button_text="Select Save Location"
            )

        # التحقق من نوع المعلومات المجوبة فعليًا
        is_actually_playlist = (
            isinstance(self.fetched_info.get("entries"), list)
            if self.fetched_info
            else False
        )

        if is_playlist_mode and is_actually_playlist:
            # عرض محدد القائمة
            playlist_title = self.fetched_info.get("title", "Untitled Playlist")
            self.dynamic_area_label.configure(text=f"Playlist: {playlist_title}")
            self.quality_selector_widget.grid_remove()  # إخفاء محدد الجودة
            self.playlist_selector_widget.populate_items(
                self.fetched_info.get("entries")
            )
            self.playlist_selector_widget.enable()  # تمكين محدد القائمة
            self.playlist_selector_widget.grid(
                row=6, column=0, columnspan=3, padx=20, pady=10, sticky="nsew"
            )
            print("UI_Interface: Playlist frame gridded.")
        elif (
            self.fetched_info
        ):  # إذا كانت المعلومات فيديو مفرد (أو تم تعطيل وضع القائمة)
            # عرض محدد الجودة
            video_title = self.fetched_info.get("title", "Untitled Video")
            self.dynamic_area_label.configure(text=f"Video: {video_title}")
            self.playlist_selector_widget.grid_remove()  # إخفاء محدد القائمة
            self.quality_selector_widget.populate_options(
                self.fetched_info.get("formats", [])
            )
            self.quality_selector_widget.enable()  # تمكين محدد الجودة
            self.quality_selector_widget.grid(
                row=5, column=0, columnspan=3, padx=15, pady=5, sticky="ew"
            )
            print("UI_Interface: Quality frame gridded.")
        else:
            # حالة خطأ أو لا توجد معلومات
            self.dynamic_area_label.configure(
                text="Error: Invalid information received."
            )
            self.quality_selector_widget.grid_remove()
            self.playlist_selector_widget.grid_remove()

        self.update_idletasks()  # تحديث الواجهة فورًا لإظهار التغييرات

    def _enter_downloading_state(self):
        """Set UI state during download."""
        self.top_frame_widget.disable_fetch()  # تعطيل الإدخال العلوي
        self.options_frame_widget.disable()  # تعطيل الخيارات
        self.path_frame_widget.disable()  # تعطيل اختيار المسار
        self.quality_selector_widget.disable()  # تعطيل محدد الجودة (إذا كان ظاهرًا)
        self.playlist_selector_widget.disable()  # تعطيل محدد القائمة (إذا كان ظاهرًا)
        self.bottom_controls_widget.disable_download(
            button_text="Downloading..."
        )  # تعطيل زر التحميل
        self.bottom_controls_widget.show_cancel_button()  # إظهار زر الإلغاء

    # --- معالجات الأحداث ---
    def browse_path_logic(self):
        """Handles the 'Browse' button click."""
        # فتح مربع حوار اختيار المجلد
        directory = filedialog.askdirectory(title="Select Download Folder")
        if directory:  # إذا اختار المستخدم مجلدًا
            self.path_frame_widget.set_path(directory)
            # التحقق مما إذا كان يجب تمكين زر التحميل الآن
            if (
                self.fetched_info
                and self.bottom_controls_widget.download_button.cget("state")
                == "disabled"
            ):
                self.bottom_controls_widget.enable_download(
                    button_text="Download Selection"
                )

    def fetch_video_info(self):
        """Handles the 'Fetch Info' button click."""
        url = self.top_frame_widget.get_url()
        if not url:
            messagebox.showerror("Input Error", "Please enter a URL.")
            return
        self._enter_idle_state()  # إعادة الواجهة للحالة الأولية قبل البدء
        self.top_frame_widget.set_url(url)  # التأكد من بقاء الرابط في الحقل
        self.current_operation = "fetch"  # تحديد العملية الحالية
        self._enter_fetching_state()  # تغيير حالة الواجهة إلى وضع الجلب
        if self.logic:
            self.logic.start_info_fetch(url)  # استدعاء المنطق لبدء الجلب

    def toggle_playlist_mode(self):
        """Handles the playlist switch toggle."""
        # هذا يُستدعى عندما يغير المستخدم المفتاح
        if self.fetched_info:  # يجب أن تكون هناك معلومات مجوبة للتأثير
            is_playlist_mode_requested = self.options_frame_widget.get_playlist_mode()
            is_actually_playlist = isinstance(self.fetched_info.get("entries"), list)

            # إذا طلب وضع القائمة والمعلومات ليست قائمة، نمنعه ونعيده لوضع المفرد
            if is_playlist_mode_requested and not is_actually_playlist:
                print(
                    "UI_Interface: Cannot enter playlist mode: Fetched info is not a playlist."
                )
                messagebox.showwarning(
                    "Mode Error", "The fetched URL does not seem to be a playlist."
                )
                self.options_frame_widget.set_playlist_mode(
                    False
                )  # إعادة المفتاح لوضع إيقاف
                self._enter_info_fetched_state(False)  # تحديث الواجهة لوضع المفرد
            else:
                # إذا كان الطلب متوافقًا مع المعلومات (أو كان طلب وضع مفرد)، حدث الواجهة
                self._enter_info_fetched_state(is_playlist_mode_requested)
        else:
            # إذا لم تكن هناك معلومات، فقط غير حالة المفتاح (السلوك الافتراضي)
            pass  # CustomTkinter يعالج تغيير المتغير المرتبط تلقائيًا

    def start_download_ui(self):
        """Handles the 'Download' button click."""
        url = self.top_frame_widget.get_url()
        save_path = self.path_frame_widget.get_path()
        format_choice = self.options_frame_widget.get_format_choice()
        is_playlist_mode_on = self.options_frame_widget.get_playlist_mode()

        # التحقق من المدخلات الأساسية
        if not url:
            messagebox.showerror("Error", "URL is missing.")
            return
        if not save_path:
            messagebox.showerror("Error", "Save location is missing.")
            return
        if not os.path.isdir(save_path):
            messagebox.showerror("Error", "Save location is not a valid directory.")
            return
        if not self.fetched_info:
            messagebox.showerror("Error", "Fetch info first.")
            return

        # تهيئة متغيرات التحميل
        quality_format_id = None
        playlist_items_string = None
        playlist_items_count = 0
        is_actually_playlist = isinstance(self.fetched_info.get("entries"), list)

        # التحقق من وضع القائمة وتجهيز الخيارات
        if is_playlist_mode_on and is_actually_playlist:
            playlist_items_string = (
                self.playlist_selector_widget.get_selected_items_string()
            )
            if not playlist_items_string:
                messagebox.showwarning(
                    "Selection Error", "No playlist items selected for download."
                )
                return
            # حساب عدد العناصر المحددة
            playlist_items_count = len(playlist_items_string.split(","))
            quality_format_id = None  # لا نستخدم جودة الفيديو المفرد للقوائم
            print(
                f"UI: Starting playlist download. Count: {playlist_items_count}, Items: {playlist_items_string}"
            )
        elif not is_playlist_mode_on and self.fetched_info:  # وضع الفيديو المفرد
            quality_format_id = self.quality_selector_widget.get_selected_id()
            playlist_items_count = 1  # فيديو واحد
            print(
                f"UI: Starting single video download. Format ID: {quality_format_id}, General: {format_choice}"
            )
        else:  # حالة غير متوقعة (مثل طلب قائمة لكن المعلومات مفرد)
            messagebox.showerror(
                "Logic Error", "Mismatch between playlist mode and fetched info."
            )
            return

        # تغيير حالة الواجهة وبدء التحميل في المنطق
        self.current_operation = "download"
        self._enter_downloading_state()
        if self.logic:
            self.logic.start_download(
                url=url,
                save_path=save_path,
                format_choice=format_choice,
                quality_format_id=quality_format_id,
                is_playlist=is_playlist_mode_on
                and is_actually_playlist,  # القيمة الفعلية التي تمرر للمنطق
                playlist_items=playlist_items_string,
                playlist_items_count=playlist_items_count,
            )

    def cancel_operation_ui(self):
        """Handles the 'Cancel' button click."""
        print("UI_Interface: Cancel button pressed.")
        if self.current_operation:  # التحقق من أن هناك عملية جارية
            self.update_status("Cancellation requested...")  # تحديث الحالة فورًا
            if self.logic:
                self.logic.cancel_operation()  # إرسال طلب الإلغاء للمنطق
        else:
            print("UI_Interface: No operation to cancel.")

    # --- دوال الكول باك (Callback Methods) ---
    # تستدعى من LogicHandler لتحديث الواجهة

    def update_status(self, message):
        """Updates the status label text and color."""

        def _update():
            color = "gray"
            msg_lower = message.lower()
            if "error" in msg_lower:
                color = "red"
            elif "warning" in msg_lower:
                color = "orange"
            elif "cancel" in msg_lower:
                color = "orange"
            elif (
                "complete" in msg_lower
                or "finished downloading" in msg_lower
                or "success" in msg_lower
                or "finished for:" in msg_lower
            ):
                color = "green"
            elif (
                "downloading" in msg_lower
                or "processing" in msg_lower
                or "fetching" in msg_lower
                or "starting" in msg_lower
            ):
                color = "blue"
            self.status_label.configure(text=message, text_color=color)

        # استخدام after لتجنب مشاكل الخيوط وضمان التحديث في الخيط الرئيسي للواجهة
        self.after(1, _update)

    def update_progress(self, value):
        """Updates the progress bar."""
        # التأكد من أن القيمة بين 0 و 1
        value = max(0.0, min(1.0, value))
        # استخدام after لتحديث آمن من الخيط
        self.after(1, lambda: self.progress_bar.set(value))

    def on_info_success(self, info_dict):
        """Callback executed when info fetching is successful."""

        def _update():
            self.fetched_info = info_dict  # تخزين المعلومات المجوبة
            if not info_dict:
                self.on_info_error("Received empty or invalid info.")
                return

            # تحديد الوضع النهائي (مفرد أو قائمة) بناءً على المعلومات والمفتاح
            is_playlist_mode_requested = self.options_frame_widget.get_playlist_mode()
            is_actually_playlist = isinstance(info_dict.get("entries"), list)

            final_playlist_mode = False
            if is_playlist_mode_requested and is_actually_playlist:
                final_playlist_mode = True
            elif is_playlist_mode_requested and not is_actually_playlist:
                # كان يطلب قائمة لكنها ليست كذلك، نعيده للمفرد
                self.options_frame_widget.set_playlist_mode(False)
                final_playlist_mode = False
                # لا داعي لرسالة تحذير هنا، _enter_info_fetched_state سيعرض واجهة المفرد
            else:  # طلب مفرد
                final_playlist_mode = False

            # تحديث حالة الواجهة بناءً على الوضع النهائي
            self._enter_info_fetched_state(final_playlist_mode)
            # تعيين رسالة نجاح نهائية
            status_msg = "Info fetched successfully. Ready to download."
            if final_playlist_mode:
                status_msg = "Playlist info fetched. Select items and download."
            self.update_status(status_msg)  # استخدم دالة التحديث لتغيير اللون أيضًا

        self.after(0, _update)  # استخدام 0 للتحديث بأسرع وقت ممكن في دورة الأحداث

    def on_info_error(self, error_message):
        """Callback executed when info fetching fails."""

        def _update():
            print(f"UI_Interface: Info error callback received: {error_message}")
            # عرض رسالة الخطأ للمستخدم
            messagebox.showerror(
                "Information Fetch Error",
                f"Could not fetch information:\n{error_message}",
            )
            # إعادة الواجهة لحالة الخمول
            self._enter_idle_state()

        self.after(0, _update)

    def on_task_finished(self):
        """Callback executed when any background task (fetch/download) finishes or is cancelled."""

        def _process_finish():
            operation_type = self.current_operation
            final_status_text = self.status_label.cget(
                "text"
            )  # النص الحالي في شريط الحالة
            final_status_color = self.status_label.cget("text_color")  # اللون الحالي

            print(
                f"UI_Interface: Task finished notification (Type: '{operation_type}'). Final status: '{final_status_text}' (Color: {final_status_color})"
            )

            # التحقق مما إذا كانت العملية قد أُلغيت أو فشلت (بناءً على لون الحالة أو النص)
            was_cancelled = "cancel" in final_status_text.lower()
            was_error = (
                final_status_color == "red" or "error" in final_status_text.lower()
            )

            if was_cancelled:
                print("UI: Operation was cancelled. Restoring previous state.")
                if self.fetched_info:
                    # إذا كانت هناك معلومات، استعد الحالة بناءً عليها
                    is_playlist_mode = self.options_frame_widget.get_playlist_mode()
                    is_actually_playlist = isinstance(
                        self.fetched_info.get("entries"), list
                    )
                    final_playlist_mode = is_playlist_mode and is_actually_playlist
                    self._enter_info_fetched_state(final_playlist_mode)
                    self.update_status("Operation Cancelled.")  # تحديث نهائي للحالة
                else:
                    # إذا لم تكن هناك معلومات (مثل إلغاء الجلب)، عد للخمول
                    self._enter_idle_state()
                    self.update_status("Info Fetch Cancelled.")  # تحديث نهائي للحالة

            elif was_error:
                print("UI: Operation failed. Restoring previous state if possible.")
                # عادةً ما يكون قد تم عرض الخطأ بالفعل في on_info_error أو تم تسجيله في المنطق
                if self.fetched_info:
                    is_playlist_mode = self.options_frame_widget.get_playlist_mode()
                    is_actually_playlist = isinstance(
                        self.fetched_info.get("entries"), list
                    )
                    final_playlist_mode = is_playlist_mode and is_actually_playlist
                    self._enter_info_fetched_state(final_playlist_mode)
                    # الحالة يجب أن تكون بالفعل تظهر رسالة خطأ
                else:
                    self._enter_idle_state()
                    # الحالة يجب أن تكون بالفعل تظهر رسالة خطأ

            elif operation_type == "fetch" and not was_error and not was_cancelled:
                # نجاح الجلب تم التعامل معه في on_info_success، لا نفعل شيئًا هنا
                print(
                    "UI: Info fetch finished successfully (handled by on_info_success)."
                )
                pass

            elif operation_type == "download" and not was_error and not was_cancelled:
                # اكتمل التحميل بنجاح
                print("UI: Download finished successfully. Resetting to idle state.")
                messagebox.showinfo(
                    "Download Complete", "Download finished successfully!"
                )  # رسالة إضافية
                self._enter_idle_state()  # العودة للحالة الأولية بعد التحميل الناجح

            else:  # حالات أخرى غير متوقعة أو عملية غير معروفة
                print(
                    f"UI: Task finished with unknown state or type. Resetting to idle. (Op: {operation_type}, Status: {final_status_text})"
                )
                self._enter_idle_state()

            # إعادة تعيين العملية الحالية في النهاية دائمًا
            self.current_operation = None

        # استخدام after لضمان معالجة الرسالة النهائية للحالة قبل تحديد الخطوات التالية
        self.after(50, _process_finish)  # تأخير بسيط للتأكد من تحديث الحالة
