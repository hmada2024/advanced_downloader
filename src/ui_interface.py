# -- ملف كلاس الواجهة الرسومية الرئيسي للتطبيق والمنسق بين المكونات --
# Purpose: Main application UI window class and coordinator between components.

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os

# استيراد مكونات الواجهة المنفصلة (باستخدام الاستيراد النسبي)
from .ui_components.top_input_frame import TopInputFrame
from .ui_components.options_control_frame import OptionsControlFrame
from .ui_components.path_selection_frame import PathSelectionFrame
from .ui_components.bottom_controls_frame import BottomControlsFrame
# --- تم إزالة استيراد QualitySelector ---
# from .ui_components.quality_selector import QualitySelector
from .ui_components.playlist_selector import PlaylistSelector


# الكلاس الرئيسي للواجهة، يرث من ctk.CTk (النافذة الرئيسية)
class UserInterface(ctk.CTk):
    def __init__(self, logic_handler):
        super().__init__()
        self.logic = logic_handler
        self.fetched_info = None
        self.current_operation = None
        self._last_toggled_playlist_mode = True # Start with playlist mode ON by default visually

        # --- إعدادات النافذة الأساسية ---
        self.title("Advanced Downloader")
        # زيادة الأبعاد الافتراضية قليلاً لاستيعاب رسائل الحالة الطويلة
        self.geometry("850x750") # Adjusted geometry
        ctk.set_appearance_mode("System") # أو "Dark", "Light"
        ctk.set_default_color_theme("blue") # أو "green", "dark-blue"

        # --- إعداد الشبكة الرئيسية للنافذة ---
        self.grid_columnconfigure(0, weight=1) # عمود وحيد يأخذ كل العرض Single column takes all width
        self.grid_rowconfigure(4, weight=1) # الصف الديناميكي (القائمة أو لا شيء) يتمدد Dynamic row expands

        # --- إنشاء مكونات الواجهة الفرعية ---
        self.top_frame_widget = TopInputFrame(self, fetch_command=self.fetch_video_info)
        self.top_frame_widget.grid(row=0, column=0, padx=15, pady=(15, 5), sticky="ew")

        self.options_frame_widget = OptionsControlFrame(
            self, toggle_playlist_command=self.toggle_playlist_mode
        )
        self.options_frame_widget.grid(row=1, column=0, padx=15, pady=5, sticky="ew")

        self.path_frame_widget = PathSelectionFrame(
            self, browse_callback=self.browse_path_logic
        )
        self.path_frame_widget.grid(row=2, column=0, padx=15, pady=5, sticky="ew")

        # --- عنوان للمنطقة الديناميكية ---
        self.dynamic_area_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(weight="bold")
        )
        self.dynamic_area_label.grid(row=3, column=0, padx=20, pady=(10, 0), sticky="w")

        # --- إزالة إنشاء QualitySelector ---
        # self.quality_selector_widget = QualitySelector(self)

        # --- إنشاء إطار اختيار قائمة التشغيل (سيتم إظهاره/إخفاؤه) ---
        self.playlist_selector_widget = PlaylistSelector(self)
        # Note: Don't grid it here, grid it dynamically in _enter_info_fetched_state

        # --- إنشاء إطار الأزرار السفلية ---
        self.bottom_controls_widget = BottomControlsFrame(
            self,
            download_command=self.start_download_ui,
            cancel_command=self.cancel_operation_ui,
        )
        # تغيير الصف ليأتي بعد المنطقة الديناميكية وشريط التقدم والحالة
        self.bottom_controls_widget.grid(row=6, column=0, padx=15, pady=(5, 5), sticky="ew") # Row updated

        # --- إنشاء شريط التقدم ---
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=7, column=0, padx=20, pady=(0, 5), sticky="ew") # Row updated
        self.progress_bar.set(0)

        # --- تسمية لعرض رسائل الحالة (مُحسّنة للعرض متعدد الأسطر) ---
        self.status_label = ctk.CTkLabel(
            self,
            text="Enter URL and click Fetch Info.",
            text_color="gray",
            font=ctk.CTkFont(size=13),
            justify="left", # محاذاة لليسار افتراضيًا
            anchor="w",     # تثبيت النص يسارًا
        )
        self.status_label.grid(row=8, column=0, padx=25, pady=(0, 10), sticky="ew") # Row updated

        # --- الدخول في الحالة الأولية عند بدء التشغيل ---
        self._enter_idle_state()

    def _enable_main_controls(self, enable_playlist_switch=True):
        """تمكين عناصر التحكم الرئيسية (الإدخال، الخيارات، المسار)."""
        self.top_frame_widget.enable_fetch()
        self.options_frame_widget.format_combobox.configure(state="normal")
        # تمكين/تعطيل مفتاح القائمة حسب الحاجة
        switch_state = "normal" if enable_playlist_switch else "disabled"
        self.options_frame_widget.playlist_switch.configure(state=switch_state)
        self.path_frame_widget.enable()

    def _enter_idle_state(self):
        """الدخول في حالة الخمول (الاستعداد لعملية جديدة)."""
        print("UI_Interface: Entering idle state.")
        self._enable_main_controls(enable_playlist_switch=True) # تمكين كل شيء
        self.bottom_controls_widget.disable_download(button_text="Download") # تعطيل التحميل
        self.bottom_controls_widget.hide_cancel_button() # إخفاء الإلغاء
        self.dynamic_area_label.configure(text="") # مسح العنوان الديناميكي

        # --- إزالة التعامل مع QualitySelector ---
        # self.quality_selector_widget.grid_remove()
        # self.quality_selector_widget.reset()

        # --- التأكد من إخفاء وإعادة تعيين محدد القائمة ---
        self.playlist_selector_widget.grid_remove()
        self.playlist_selector_widget.reset()

        self.fetched_info = None # مسح المعلومات المجوبة
        self.status_label.configure(text="Enter URL and click Fetch Info.", text_color="gray") # رسالة الحالة الافتراضية
        self.progress_bar.set(0) # إعادة تعيين شريط التقدم
        self.current_operation = None # لا توجد عملية نشطة
        # إعادة مفتاح القائمة إلى ON افتراضيًا
        self.options_frame_widget.set_playlist_mode(True)
        self._last_toggled_playlist_mode = True

    def _enter_fetching_state(self):
        """الدخول في حالة جلب المعلومات."""
        print("UI_Interface: Entering fetching state.")
        self.top_frame_widget.disable_fetch(button_text="Fetching...") # تعطيل الجلب
        self.options_frame_widget.disable() # تعطيل الخيارات
        self.path_frame_widget.disable() # تعطيل المسار
        self.bottom_controls_widget.disable_download() # تعطيل التحميل
        self.bottom_controls_widget.show_cancel_button() # إظهار الإلغاء
        self.status_label.configure(text="Fetching information...", text_color="orange") # تحديث الحالة
        self.progress_bar.set(0) # البدء من الصفر

    def _enter_info_fetched_state(self):
        """الدخول في حالة عرض المعلومات بعد جلبها بنجاح."""
        if not self.fetched_info:
            print("Error: _enter_info_fetched_state called without fetched_info.")
            self._enter_idle_state()
            self.update_status("Error: Failed to process fetched information.")
            return

        is_actually_playlist = isinstance(self.fetched_info.get("entries"), list)

        # تمكين عناصر التحكم الرئيسية (قد يتم تعطيل مفتاح القائمة إذا لم تكن قائمة)
        self._enable_main_controls(enable_playlist_switch=is_actually_playlist)

        # تحديد ما إذا كان يجب عرض واجهة القائمة
        should_show_playlist_view = (
            self.options_frame_widget.get_playlist_mode() and is_actually_playlist
        )

        print(
            f"UI_Interface: Entering info fetched state. Actual playlist: {is_actually_playlist}, "
            f"Switch ON: {self.options_frame_widget.get_playlist_mode()}, "
            f"Show Playlist View: {should_show_playlist_view}"
        )

        self.bottom_controls_widget.hide_cancel_button() # إخفاء الإلغاء

        # تمكين زر التحميل فقط إذا تم تحديد مسار صالح
        if self.path_frame_widget.get_path() and os.path.isdir(self.path_frame_widget.get_path()):
            self.bottom_controls_widget.enable_download(button_text="Download Selection")
        else:
            self.bottom_controls_widget.disable_download(button_text="Select Save Location")

        # --- إخفاء/إظهار منطقة اختيار القائمة بناءً على الحالة ---
        if should_show_playlist_view:
            self._extracted_from__enter_info_fetched_state_35()
        else:
            # إذا لم يكن وضع قائمة أو لم تكن قائمة فعلية
            video_title = self.fetched_info.get("title", "Untitled Video")
            self.dynamic_area_label.configure(text=f"Video: {video_title}")

            # التأكد من إخفاء محدد القائمة
            self.playlist_selector_widget.grid_remove()

            # --- إزالة عرض وتفعيل QualitySelector ---
            # self.quality_selector_widget.populate_options(self.fetched_info.get("formats", []))
            # self.quality_selector_widget.enable()
            # self.quality_selector_widget.grid(...)
            # print("UI_Interface: Quality frame gridded.") # إزالة هذه الطباعة

            # إذا كانت قائمة فعلية ولكن وضع القائمة معطل، تأكد من أن المفتاح قابل للتفعيل
            if is_actually_playlist:
                self.options_frame_widget.playlist_switch.configure(state="normal")

        self.update_idletasks() # تحديث الواجهة لعرض التغييرات فورًا

    # TODO Rename this here and in `_enter_info_fetched_state`
    def _extracted_from__enter_info_fetched_state_35(self):
        playlist_title = self.fetched_info.get("title", "Untitled Playlist")
        total_items = len(self.fetched_info.get("entries", []))
        self.dynamic_area_label.configure(text=f"Playlist: {playlist_title} ({total_items} items total)")

        # --- إزالة إخفاء QualitySelector ---
        # self.quality_selector_widget.grid_remove()

        # إظهار وتعبئة وتفعيل محدد القائمة
        self.playlist_selector_widget.populate_items(self.fetched_info.get("entries"))
        self.playlist_selector_widget.enable()
        # تعديل الصف والعمود ليكون في المنطقة الديناميكية
        self.playlist_selector_widget.grid(row=4, column=0, padx=20, pady=(5, 10), sticky="nsew") # Row updated
        print("UI_Interface: Playlist frame gridded.")

    def _enter_downloading_state(self):
        """الدخول في حالة التحميل."""
        print("UI_Interface: Entering downloading state.")
        self.top_frame_widget.disable_fetch() # تعطيل كل عناصر الإدخال والتحكم
        self.options_frame_widget.disable()
        self.path_frame_widget.disable()

        # --- إزالة تعطيل QualitySelector ---
        # self.quality_selector_widget.disable()
        self.playlist_selector_widget.disable() # تعطيل محدد القائمة

        self.bottom_controls_widget.disable_download(button_text="Downloading...") # تغيير نص زر التحميل وتعطيله
        self.bottom_controls_widget.show_cancel_button() # إظهار زر الإلغاء

    def browse_path_logic(self):
        """فتح مربع حوار لاختيار مجلد الحفظ وتحديث الواجهة."""
        if directory := filedialog.askdirectory(title="Select Download Folder"):
            self.path_frame_widget.set_path(directory)
            # إذا تم اختيار مسار وكانت المعلومات قد جُلبت، قم بتمكين زر التحميل
            if self.fetched_info and self.bottom_controls_widget.download_button.cget("state") == "disabled":
                self.bottom_controls_widget.enable_download(button_text="Download Selection")

    def fetch_video_info(self):
        """بدء عملية جلب المعلومات من الرابط المدخل."""
        url = self.top_frame_widget.get_url()
        if not url:
            messagebox.showerror("Input Error", "Please enter a URL.")
            return

        # إعادة تعيين الحالة قبل البدء
        self.fetched_info = None
        # --- إزالة إخفاء QualitySelector ---
        # self.quality_selector_widget.grid_remove()
        self.playlist_selector_widget.grid_remove()
        self.dynamic_area_label.configure(text="")
        self.top_frame_widget.set_url(url) # التأكد من أن الرابط لا يزال في الحقل

        self.current_operation = "fetch" # تحديد العملية الحالية
        # تخزين حالة مفتاح القائمة قبل بدء الجلب
        self._last_toggled_playlist_mode = self.options_frame_widget.get_playlist_mode()
        self._enter_fetching_state() # تغيير حالة الواجهة

        # استدعاء المنطق لبدء الجلب في خيط منفصل
        if self.logic:
            self.logic.start_info_fetch(url)

    def toggle_playlist_mode(self):
        """تُستدعى عند تغيير مفتاح وضع القائمة."""
        print("UI_Interface: Playlist switch toggled manually.")
        # تخزين الحالة الجديدة
        self._last_toggled_playlist_mode = self.options_frame_widget.get_playlist_mode()
        # إذا كانت المعلومات موجودة، أعد رسم الواجهة لتعكس التغيير
        if self.fetched_info:
            self._enter_info_fetched_state()

    def start_download_ui(self):
        """بدء عملية التحميل بناءً على الخيارات الحالية."""
        url = self.top_frame_widget.get_url()
        save_path = self.path_frame_widget.get_path()
        format_choice = self.options_frame_widget.get_format_choice() # الخيار العام دائمًا
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

        # --- إزالة متغير quality_format_id ---
        # quality_format_id = None
        playlist_items_string = None
        selected_items_count = 0
        total_playlist_count = 0
        is_actually_playlist = isinstance(self.fetched_info.get("entries"), list)

        if is_actually_playlist:
            total_playlist_count = len(self.fetched_info.get("entries", []))

        # تحديد سلوك التحميل (قائمة أو فردي)
        if is_playlist_mode_on and is_actually_playlist:
            # تحميل قائمة تشغيل
            playlist_items_string = self.playlist_selector_widget.get_selected_items_string()
            if not playlist_items_string:
                messagebox.showwarning("Selection Error", "No playlist items selected for download.")
                return
            selected_items_count = len(playlist_items_string.split(","))
            # --- لا نحتاج quality_format_id هنا ---
            print(f"UI: Starting playlist download. Selected: {selected_items_count}, Total: {total_playlist_count}, Items: {playlist_items_string}, Format: {format_choice}")

        elif not is_playlist_mode_on and self.fetched_info:
            # تحميل فيديو مفرد (أو أول فيديو من قائمة إذا كانت playlist mode off)
            if is_actually_playlist and not messagebox.askyesno(
                "Confirm Single Download",
                "This is a playlist, but playlist mode is off.\nDo you want to download only the first video/item based on the URL?",
            ):
                return
            # --- الحصول على الجودة من القائمة العامة format_choice فقط ---
            # --- إزالة quality_format_id = self.quality_selector_widget.get_selected_id() ---
            selected_items_count = 1 # فيديو واحد فقط
            print(f"UI: Starting single video/item download. General Format: {format_choice}, Playlist Total (if any): {total_playlist_count}")
        else:
            # حالة غير متوقعة
            messagebox.showerror("Logic Error", "Mismatch between UI state and fetched info during download.")
            return

        self.current_operation = "download" # تحديد العملية الحالية
        self._enter_downloading_state() # تغيير حالة الواجهة

        # استدعاء المنطق لبدء التحميل
        if self.logic:
            # --- إزالة تمرير quality_format_id ---
            self.logic.start_download(
                url=url,
                save_path=save_path,
                format_choice=format_choice, # تمرير الخيار العام دائمًا
                # quality_format_id=quality_format_id, <-- إزالة هذا السطر
                is_playlist=is_playlist_mode_on and is_actually_playlist,
                playlist_items=playlist_items_string,
                selected_items_count=selected_items_count,
                total_playlist_count=total_playlist_count,
            )

    def cancel_operation_ui(self):
        """طلب إلغاء العملية النشطة."""
        print("UI_Interface: Cancel button pressed.")
        if self.current_operation:
            self.update_status("Cancellation requested...")
        if self.logic:
            self.logic.cancel_operation() # إرسال طلب الإلغاء للمنطق
        else:
            # في حالة عدم وجود منطق (نادر جدًا)
            print("UI_Interface: No logic handler available to cancel.")
            self._enter_idle_state() # العودة للحالة الآمنة

    def update_status(self, message):
        """تحديث نص ولون رسالة الحالة في الواجهة (آمن للخيوط)."""
        def _update():
            # تحديد لون النص بناءً على الكلمات المفتاحية
            color = "gray" # اللون الافتراضي
            msg_lower = message.lower()
            # ضبط المحاذاة بناءً على عدد الأسطر
            if "\n" in message:
                self.status_label.configure(justify="left")
            else:
                self.status_label.configure(justify="center") # للرسائل ذات السطر الواحد

            if "error" in msg_lower: color = "red"
            elif "warning" in msg_lower: color = "orange"
            elif "cancel" in msg_lower: color = "orange"
            elif "complete" in msg_lower or "finished" in msg_lower or "success" in msg_lower: color = "green"
            elif "downloading" in msg_lower or "processing" in msg_lower or "fetching" in msg_lower or "starting" in msg_lower: color = "blue"

            # تحديث النص واللون
            self.status_label.configure(text=message, text_color=color)
        # استخدام after لضمان التنفيذ في خيط الواجهة الرئيسي
        self.after(1, _update)

    def update_progress(self, value):
        """تحديث قيمة شريط التقدم (آمن للخيوط)."""
        value = max(0.0, min(1.0, value)) # التأكد من أن القيمة بين 0 و 1
        # استخدام after لضمان التنفيذ في خيط الواجهة الرئيسي
        self.after(1, lambda: self.progress_bar.set(value))

    def on_info_success(self, info_dict):
        """تُستدعى عند نجاح جلب المعلومات من المنطق (آمن للخيوط)."""
        def _update():
            self.fetched_info = info_dict # تخزين المعلومات
            if not info_dict:
                self.on_info_error("Received empty or invalid info.")
                return

            is_actually_playlist = isinstance(info_dict.get("entries"), list)

            # استعادة حالة مفتاح القائمة التي كانت محددة قبل الجلب
            # أو تعطيله إذا لم تكن قائمة فعلية
            if is_actually_playlist:
                print(f"Info success: It's a playlist. Restoring switch state to: {self._last_toggled_playlist_mode}")
                self.options_frame_widget.set_playlist_mode(self._last_toggled_playlist_mode)
            else:
                print("Info success: It's not a playlist. Ensuring switch is OFF and disabled.")
                self.options_frame_widget.set_playlist_mode(False)
                self.options_frame_widget.playlist_switch.configure(state="disabled") # تعطيله أيضًا

            # الدخول في حالة عرض المعلومات
            self._enter_info_fetched_state()

            # تحديث رسالة الحالة
            status_msg = "Info fetched successfully. Ready to download."
            if self.options_frame_widget.get_playlist_mode() and is_actually_playlist:
                status_msg = "Playlist info fetched. Select items and download."
            self.update_status(status_msg)

        self.after(0, _update) # استخدام after(0) للتنفيذ الفوري في دورة الأحداث التالية

    def on_info_error(self, error_message):
        """تُستدعى عند فشل جلب المعلومات من المنطق (آمن للخيوط)."""
        def _update():
            print(f"UI_Interface: Info error callback received: {error_message}")
            messagebox.showerror("Information Fetch Error", f"Could not fetch information:\n{error_message}")
            # العودة لحالة الخمول عند الخطأ
            self._enter_idle_state()
        self.after(0, _update)

    def on_task_finished(self):
        """تُستدعى عند انتهاء أي مهمة (جلب أو تحميل) من المنطق (آمن للخيوط)."""
        def _process_finish():
            operation_type = self.current_operation
            # الحصول على الحالة النهائية من الواجهة نفسها
            final_status_text = self.status_label.cget("text")
            final_status_color = self.status_label.cget("text_color")

            print(f"UI_Interface: Task finished notification (Type: '{operation_type}'). Final status: '{final_status_text}' (Color: {final_status_color})")

            # تحديد ما إذا كانت المهمة قد أُلغيت أو فشلت
            was_cancelled = "cancel" in final_status_text.lower()
            was_error = (final_status_color == "red") or ("error" in final_status_text.lower())

            if was_cancelled:
                print("UI: Operation was cancelled. Restoring previous state if info exists.")
                if self.fetched_info:
                    # إذا كانت هناك معلومات، عد لحالة عرضها
                    self._enter_info_fetched_state()
                    self.update_status("Operation Cancelled.")
                else:
                    # إذا لم تكن هناك معلومات (إلغاء الجلب)، عد للخمول
                    self._enter_idle_state()
                    self.update_status("Info Fetch Cancelled.")
            elif was_error:
                print("UI: Operation failed with error. Restoring previous state if info exists.")
                if self.fetched_info:
                    # إذا كانت هناك معلومات، عد لحالة عرضها
                    self._enter_info_fetched_state()
                    # الحالة ستكون معروضة كخطأ بالفعل
                else:
                    # إذا فشل الجلب
                    self._enter_idle_state()
                    # الحالة ستكون معروضة كخطأ بالفعل
            elif operation_type == "fetch" and not was_error and not was_cancelled:
                # نجاح الجلب يتم التعامل معه بالفعل في on_info_success
                print("UI: Info fetch finished successfully (handled by on_info_success). State already updated.")
            elif operation_type == "download" and not was_error and not was_cancelled:
                # نجاح التحميل
                print("UI: Download finished successfully. Resetting to idle state.")
                messagebox.showinfo("Download Complete", f"Download finished successfully!\nFile(s) saved in:\n{self.path_frame_widget.get_path()}")
                # العودة لحالة الخمول بعد نجاح التحميل
                self._enter_idle_state()
            else:
                # حالة غير متوقعة أو نوع عملية غير معروف
                print(f"UI: Task finished with unknown state or type. Resetting. (Op: {operation_type}, Status: {final_status_text})")
                self._enter_idle_state()

            # إعادة تعيين نوع العملية الحالية
            self.current_operation = None

        # استخدام after لتأخير بسيط يضمن تحديث الحالة النهائية قبل اتخاذ القرار
        self.after(50, _process_finish)