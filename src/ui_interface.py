# -- ملف كلاس الواجهة الرسومية الرئيسي للتطبيق والمنسق بين المكونات --
# Purpose: Main application UI window class and coordinator between components.

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os

# استيراد مكونات الواجهة المنفصلة (باستخدام الاستيراد النسبي)
# Import separate UI components (using relative imports)
from .ui_components.top_input_frame import TopInputFrame
from .ui_components.options_control_frame import OptionsControlFrame
from .ui_components.path_selection_frame import PathSelectionFrame
from .ui_components.bottom_controls_frame import BottomControlsFrame
from .ui_components.quality_selector import QualitySelector
from .ui_components.playlist_selector import PlaylistSelector


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
        self._last_toggled_playlist_mode = False  # لتتبع آخر حالة للمفتاح

        # --- إعداد النافذة ---
        self.title("Advanced Downloader")
        self.geometry("850x750")
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
        # ملاحظة: QualitySelector يوضع في الصف 5، و PlaylistSelector في الصف 6

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
    def _enable_main_controls(
        self, enable_playlist_switch=True
    ):  # إضافة خيار للتحكم بالمفتاح
        """Enables the main UI controls."""
        self.top_frame_widget.enable_fetch()
        self.options_frame_widget.format_combobox.configure(
            state="normal"
        )  # تمكين الكومبوبوكس دائمًا
        # تمكين أو تعطيل مفتاح القائمة بناءً على المعامل
        switch_state = "normal" if enable_playlist_switch else "disabled"
        self.options_frame_widget.playlist_switch.configure(state=switch_state)
        self.path_frame_widget.enable()

    def _enter_idle_state(self):
        """Reset UI to initial idle state."""
        self._enable_main_controls(
            enable_playlist_switch=True
        )  # تمكين المفتاح في الحالة الأولية
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
        self._last_toggled_playlist_mode = False  # إعادة تعيين الحالة المتتبعة

    def _enter_fetching_state(self):
        """Set UI state during info fetching."""
        self.top_frame_widget.disable_fetch(button_text="Fetching...")
        self.options_frame_widget.disable()  # تعطيل كل الخيارات أثناء الجلب
        self.path_frame_widget.disable()
        self.bottom_controls_widget.disable_download()
        self.bottom_controls_widget.show_cancel_button()
        self.status_label.configure(text="Fetching information...", text_color="orange")
        self.progress_bar.set(0)

    def _enter_info_fetched_state(self):
        """Set UI state after info is fetched. Determines view based on fetched_info and switch state."""
        if not self.fetched_info:
            print("Error: _enter_info_fetched_state called without fetched_info.")
            self._enter_idle_state()  # العودة للحالة الأولية إذا لم تكن هناك معلومات
            self.update_status("Error: Failed to process fetched information.")
            return

        is_actually_playlist = isinstance(self.fetched_info.get("entries"), list)
        # --- تعديل منطق المفتاح ---
        # تمكين عناصر التحكم الرئيسية، مع تحديد حالة المفتاح
        self._enable_main_controls(enable_playlist_switch=is_actually_playlist)

        # تحديد ما إذا كان يجب عرض واجهة القائمة بناءً على حالة المفتاح *و* نوع المعلومات
        should_show_playlist_view = (
            self.options_frame_widget.get_playlist_mode() and is_actually_playlist
        )

        print(
            f"UI_Interface: Entering info fetched state. Actual playlist: {is_actually_playlist}, Switch ON: {self.options_frame_widget.get_playlist_mode()}, Show Playlist View: {should_show_playlist_view}"
        )

        self.bottom_controls_widget.hide_cancel_button()

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

        if should_show_playlist_view:
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
        else:  # عرض واجهة الفيديو المفرد (إما لأنها فيديو مفرد أو لأن المفتاح مغلق)
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
            # إذا كانت المعلومات قائمة فعلًا ولكن المفتاح مغلق، تأكد من أن المفتاح ممكن التغيير
            if is_actually_playlist:
                self.options_frame_widget.playlist_switch.configure(state="normal")

        self.update_idletasks()  # تحديث الواجهة فورًا لإظهار التغييرات

    def _enter_downloading_state(self):
        """Set UI state during download."""
        self.top_frame_widget.disable_fetch()
        self.options_frame_widget.disable()  # تعطيل كل الخيارات أثناء التحميل
        self.path_frame_widget.disable()
        self.quality_selector_widget.disable()
        self.playlist_selector_widget.disable()
        self.bottom_controls_widget.disable_download(button_text="Downloading...")
        self.bottom_controls_widget.show_cancel_button()

    # --- معالجات الأحداث ---
    def browse_path_logic(self):
        """Handles the 'Browse' button click."""
        directory = filedialog.askdirectory(title="Select Download Folder")
        if directory:
            self.path_frame_widget.set_path(directory)
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
        # --- تعديل: لا تقم بإعادة التعيين الكامل هنا، فقط استعد للجلب ---
        # self._enter_idle_state() # <--- إزالة هذه السطر
        self.fetched_info = None  # مسح المعلومات القديمة
        # إخفاء المناطق الديناميكية قبل البدء
        self.quality_selector_widget.grid_remove()
        self.playlist_selector_widget.grid_remove()
        self.dynamic_area_label.configure(text="")
        # -----------------------------------------------------------
        self.top_frame_widget.set_url(url)
        self.current_operation = "fetch"
        # تذكر حالة المفتاح قبل تعطيله
        self._last_toggled_playlist_mode = self.options_frame_widget.get_playlist_mode()
        self._enter_fetching_state()
        if self.logic:
            self.logic.start_info_fetch(url)

    def toggle_playlist_mode(self):
        """Handles the playlist switch toggle."""
        # هذا يُستدعى عندما يغير المستخدم المفتاح *يدويًا*
        print("UI_Interface: Playlist switch toggled manually.")
        self._last_toggled_playlist_mode = (
            self.options_frame_widget.get_playlist_mode()
        )  # تحديث الحالة المتتبعة
        if self.fetched_info:
            # إذا كانت هناك معلومات مجوبة، أعد رسم الواجهة بناءً على الحالة الجديدة للمفتاح
            self._enter_info_fetched_state()
        # لا تفعل شيئًا إذا لم تكن هناك معلومات مجوبة بعد

    def start_download_ui(self):
        """Handles the 'Download' button click."""
        # (الكود هنا لم يتغير بشكل جوهري، يعتمد على الحالة الحالية للواجهة)
        url = self.top_frame_widget.get_url()
        save_path = self.path_frame_widget.get_path()
        format_choice = self.options_frame_widget.get_format_choice()
        is_playlist_mode_on = self.options_frame_widget.get_playlist_mode()

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

        quality_format_id = None
        playlist_items_string = None
        playlist_items_count = 0
        is_actually_playlist = isinstance(self.fetched_info.get("entries"), list)

        # التحقق من الوضع وتجهيز الخيارات
        if is_playlist_mode_on and is_actually_playlist:
            playlist_items_string = (
                self.playlist_selector_widget.get_selected_items_string()
            )
            if not playlist_items_string:
                messagebox.showwarning(
                    "Selection Error", "No playlist items selected for download."
                )
                return
            playlist_items_count = len(playlist_items_string.split(","))
            quality_format_id = None
            print(
                f"UI: Starting playlist download. Count: {playlist_items_count}, Items: {playlist_items_string}"
            )
        elif not is_playlist_mode_on and self.fetched_info:  # وضع الفيديو المفرد
            # تأكد من أن المعلومات ليست قائمة أو أن المستخدم اختار عرضها كمفرد
            if is_actually_playlist and not messagebox.askyesno(
                "Confirm Single Download",
                "This is a playlist, but playlist mode is off.\nDo you want to download only the first video?",
            ):
                return  # ألغى المستخدم
            quality_format_id = self.quality_selector_widget.get_selected_id()
            playlist_items_count = 1
            print(
                f"UI: Starting single video download. Format ID: {quality_format_id}, General: {format_choice}"
            )
        else:  # حالة غير متوقعة
            # إذا كانت المعلومات قائمة والمفتاح معطل، لا يجب أن نصل هنا عادةً
            # إذا كانت المعلومات مفردة والمفتاح يعمل، هذا خطأ في مكان آخر
            messagebox.showerror(
                "Logic Error",
                "Mismatch between UI state and fetched info during download.",
            )
            return

        self.current_operation = "download"
        self._enter_downloading_state()
        if self.logic:
            self.logic.start_download(
                url=url,
                save_path=save_path,
                format_choice=format_choice,
                quality_format_id=quality_format_id,
                # تمرير القيمة الفعلية للمنطق
                is_playlist=is_playlist_mode_on and is_actually_playlist,
                playlist_items=playlist_items_string,
                playlist_items_count=playlist_items_count,
            )

    def cancel_operation_ui(self):
        """Handles the 'Cancel' button click."""
        print("UI_Interface: Cancel button pressed.")
        if self.current_operation:
            self.update_status("Cancellation requested...")
            if self.logic:
                self.logic.cancel_operation()
        else:
            print("UI_Interface: No operation to cancel.")

    # --- دوال الكول باك (Callback Methods) ---
    # (update_status, update_progress لم تتغير)
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
                or "finished:" in msg_lower
            ):
                color = "green"  # تعديل بسيط
            elif (
                "downloading" in msg_lower
                or "processing" in msg_lower
                or "fetching" in msg_lower
                or "starting" in msg_lower
            ):
                color = "blue"
            self.status_label.configure(text=message, text_color=color)

        self.after(1, _update)

    def update_progress(self, value):
        """Updates the progress bar."""
        value = max(0.0, min(1.0, value))
        self.after(1, lambda: self.progress_bar.set(value))

    def on_info_success(self, info_dict):
        """Callback executed when info fetching is successful."""

        def _update():
            self.fetched_info = info_dict
            if not info_dict:
                self.on_info_error("Received empty or invalid info.")
                return

            is_actually_playlist = isinstance(info_dict.get("entries"), list)

            # --- تعديل منطق المفتاح ---
            # استعادة حالة المفتاح التي كانت قبل الجلب إذا كانت المعلومات قائمة
            if is_actually_playlist:
                print(
                    f"Info success: It's a playlist. Restoring switch state to: {self._last_toggled_playlist_mode}"
                )
                self.options_frame_widget.set_playlist_mode(
                    self._last_toggled_playlist_mode
                )
            else:
                # إذا لم تكن قائمة، تأكد من أن المفتاح مغلق
                print("Info success: It's not a playlist. Ensuring switch is OFF.")
                self.options_frame_widget.set_playlist_mode(False)

            # تحديث الواجهة بناءً على المعلومات والحالة الجديدة للمفتاح
            self._enter_info_fetched_state()

            # تعيين رسالة نجاح نهائية
            status_msg = "Info fetched successfully. Ready to download."
            if self.options_frame_widget.get_playlist_mode() and is_actually_playlist:
                status_msg = "Playlist info fetched. Select items and download."
            self.update_status(status_msg)

        self.after(0, _update)

    def on_info_error(self, error_message):
        """Callback executed when info fetching fails."""

        def _update():
            print(f"UI_Interface: Info error callback received: {error_message}")
            messagebox.showerror(
                "Information Fetch Error",
                f"Could not fetch information:\n{error_message}",
            )
            # --- تعديل: العودة للخمول مع تمكين عناصر التحكم الرئيسية ---
            self._enter_idle_state()
            # الحالة ستظهر الخطأ قبل استدعاء finished_callback غالبًا

        self.after(0, _update)

    def on_task_finished(self):
        """Callback executed when any background task finishes or is cancelled."""

        def _process_finish():
            operation_type = self.current_operation
            final_status_text = self.status_label.cget("text")
            final_status_color = self.status_label.cget("text_color")

            print(
                f"UI_Interface: Task finished notification (Type: '{operation_type}'). Final status: '{final_status_text}' (Color: {final_status_color})"
            )

            was_cancelled = "cancel" in final_status_text.lower()
            was_error = (
                final_status_color == "red" or "error" in final_status_text.lower()
            )

            if was_cancelled:
                print(
                    "UI: Operation was cancelled. Restoring previous state if info exists."
                )
                if self.fetched_info:
                    # استعادة الواجهة بناءً على المعلومات الموجودة وحالة المفتاح الحالية
                    self._enter_info_fetched_state()
                    self.update_status("Operation Cancelled.")
                else:
                    self._enter_idle_state()
                    self.update_status("Info Fetch Cancelled.")

            elif was_error:
                print("UI: Operation failed. Restoring previous state if info exists.")
                # الخطأ يجب أن يكون قد عُرض بالفعل
                if self.fetched_info:
                    self._enter_info_fetched_state()
                else:
                    self._enter_idle_state()

            elif operation_type == "fetch" and not was_error and not was_cancelled:
                print(
                    "UI: Info fetch finished successfully (handled by on_info_success). State already updated."
                )
                pass  # تم التعامل معه بالفعل

            elif operation_type == "download" and not was_error and not was_cancelled:
                print("UI: Download finished successfully. Resetting to idle state.")
                messagebox.showinfo(
                    "Download Complete",
                    f"Download finished successfully!\nFile(s) saved in:\n{self.path_frame_widget.get_path()}",
                )
                self._enter_idle_state()

            else:
                print(
                    f"UI: Task finished with unknown state or type. Resetting. (Op: {operation_type}, Status: {final_status_text})"
                )
                self._enter_idle_state()

            self.current_operation = None

        self.after(50, _process_finish)
