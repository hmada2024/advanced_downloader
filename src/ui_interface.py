# -- ملف كلاس الواجهة الرسومية الرئيسي للتطبيق والمنسق بين المكونات --
# Purpose: Main application UI window class and coordinator between components.

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os

# استيراد مكونات الواجهة المنفصلة
from ui_components.top_input_frame import TopInputFrame
from ui_components.options_control_frame import OptionsControlFrame
from ui_components.path_selection_frame import PathSelectionFrame
from ui_components.bottom_controls_frame import BottomControlsFrame
from ui_components.quality_selector import QualitySelector
from ui_components.playlist_selector import PlaylistSelector

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
        self.geometry("850x750") # الحجم من المرحلة الأولى
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- إعداد تخطيط الشبكة ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(6, weight=1)

        # --- إنشاء وتنسيق مكونات الواجهة ---
        self.top_frame_widget = TopInputFrame(self, fetch_command=self.fetch_video_info)
        self.top_frame_widget.grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="ew")

        self.options_frame_widget = OptionsControlFrame(self, toggle_playlist_command=self.toggle_playlist_mode)
        self.options_frame_widget.grid(row=1, column=0, columnspan=3, padx=15, pady=5, sticky="ew")

        self.path_frame_widget = PathSelectionFrame(self, browse_callback=self.browse_path_logic)
        self.path_frame_widget.grid(row=2, column=0, columnspan=3, padx=15, pady=5, sticky="ew")

        self.dynamic_area_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(weight="bold"))
        self.dynamic_area_label.grid(row=3, column=0, columnspan=3, padx=20, pady=(10,0), sticky="w")

        self.quality_selector_widget = QualitySelector(self)
        # لا يوضع الآن

        self.playlist_selector_widget = PlaylistSelector(self)
        # لا يوضع الآن

        self.bottom_controls_widget = BottomControlsFrame(
            self,
            download_command=self.start_download_ui,
            cancel_command=self.cancel_operation_ui
        )
        self.bottom_controls_widget.grid(row=7, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="ew")

        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=8, column=0, columnspan=3, padx=20, pady=(0, 5), sticky="ew")
        self.progress_bar.set(0)

        self.status_label = ctk.CTkLabel(self, text="Enter URL and click Fetch Info.", text_color="gray")
        self.status_label.grid(row=9, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="ew")

        # --- الحالة الأولية ---
        self._enter_idle_state()

    # --- دوال إدارة الحالة (معظمها بدون تغيير) ---
    def _enable_main_controls(self): # تم إعادة تسمية الدالة المعاد هيكلتها
        self.top_frame_widget.enable_fetch()
        self.options_frame_widget.enable()
        self.path_frame_widget.enable()

    def _enter_idle_state(self):
        self._enable_main_controls()
        self.bottom_controls_widget.disable_download(button_text="Download")
        self.bottom_controls_widget.hide_cancel_button()
        self.dynamic_area_label.configure(text="")
        self.quality_selector_widget.grid_remove(); self.quality_selector_widget.reset()
        self.playlist_selector_widget.grid_remove(); self.playlist_selector_widget.reset()
        self.fetched_info = None
        self.status_label.configure(text="Enter URL and click Fetch Info.", text_color="gray")
        self.progress_bar.set(0)
        self.current_operation = None

    def _enter_fetching_state(self):
        self.top_frame_widget.disable_fetch(button_text="Fetching...")
        self.options_frame_widget.disable()
        self.path_frame_widget.disable()
        self.bottom_controls_widget.disable_download()
        self.bottom_controls_widget.show_cancel_button()
        self.status_label.configure(text="Fetching information...", text_color="orange")
        self.progress_bar.set(0)

    def _enter_info_fetched_state(self, is_playlist_mode):
        print(f"UI_Interface: Entering info fetched state. Playlist mode: {is_playlist_mode}")
        self._enable_main_controls()
        self.bottom_controls_widget.hide_cancel_button()

        if self.path_frame_widget.get_path():
            self.bottom_controls_widget.enable_download(button_text="Download Selection")
        else:
            self.bottom_controls_widget.disable_download(button_text="Select Save Location")

        is_actually_playlist = isinstance(self.fetched_info.get('entries'), list)

        if is_playlist_mode and is_actually_playlist:
            playlist_title = self.fetched_info.get('title', 'Untitled Playlist')
            self.dynamic_area_label.configure(text=f"Playlist: {playlist_title}")
            self.quality_selector_widget.grid_remove()
            self.playlist_selector_widget.populate_items(self.fetched_info.get('entries'))
            self.playlist_selector_widget.enable()
            self.playlist_selector_widget.grid(row=6, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")
            print("UI_Interface: Playlist frame gridded.")
        elif self.fetched_info:
            video_title = self.fetched_info.get('title', 'Untitled Video')
            self.dynamic_area_label.configure(text=f"Video: {video_title}")
            self.playlist_selector_widget.grid_remove()
            self.quality_selector_widget.populate_options(self.fetched_info.get('formats', []))
            self.quality_selector_widget.enable()
            self.quality_selector_widget.grid(row=5, column=0, columnspan=3, padx=15, pady=5, sticky="ew")
            print("UI_Interface: Quality frame gridded.")
        else:
             self.dynamic_area_label.configure(text="Error: Invalid information received.")
             self.quality_selector_widget.grid_remove()
             self.playlist_selector_widget.grid_remove()

        self.update_idletasks()

    def _enter_downloading_state(self):
        self.top_frame_widget.disable_fetch()
        self.options_frame_widget.disable()
        self.path_frame_widget.disable()
        self.quality_selector_widget.disable()
        self.playlist_selector_widget.disable()
        self.bottom_controls_widget.disable_download(button_text="Downloading...")
        self.bottom_controls_widget.show_cancel_button()

    # --- معالجات الأحداث ---
    def browse_path_logic(self):
        if directory := filedialog.askdirectory():
            self.path_frame_widget.set_path(directory)
            if self.fetched_info and self.bottom_controls_widget.download_button.cget("state") == "disabled":
                 self.bottom_controls_widget.enable_download(button_text="Download Selection")

    def fetch_video_info(self):
        url = self.top_frame_widget.get_url()
        if not url: messagebox.showerror("Error", "Please enter a URL."); return
        self._enter_idle_state()
        self.top_frame_widget.set_url(url)
        self.current_operation = 'fetch'
        self._enter_fetching_state()
        if self.logic: self.logic.start_info_fetch(url)

    def toggle_playlist_mode(self):
        if self.fetched_info:
             is_playlist_mode = self.options_frame_widget.get_playlist_mode()
             is_actually_playlist = isinstance(self.fetched_info.get('entries'), list)
             if is_playlist_mode and not is_actually_playlist:
                  print("UI_Interface: Cannot enter playlist mode: Fetched info is not a playlist.")
                  self.options_frame_widget.set_playlist_mode(False)
                  self._enter_info_fetched_state(False)
             else:
                  self._enter_info_fetched_state(is_playlist_mode)

    def start_download_ui(self):
        url = self.top_frame_widget.get_url()
        save_path = self.path_frame_widget.get_path()
        format_choice = self.options_frame_widget.get_format_choice() # الخيار الجديد
        is_playlist = self.options_frame_widget.get_playlist_mode()

        if not url: messagebox.showerror("Error", "URL is missing."); return
        if not save_path: messagebox.showerror("Error", "Save location is missing."); return
        if not os.path.isdir(save_path): messagebox.showerror("Error", "Save location not valid."); return
        if not self.fetched_info: messagebox.showerror("Error", "Fetch info first."); return

        quality_format_id = None
        playlist_items_string = None
        playlist_items_count = 0 # -- START Phase 2 Change: Initialize count --
        is_actually_playlist = isinstance(self.fetched_info.get('entries'), list)

        if is_playlist and is_actually_playlist:
            playlist_items_string = self.playlist_selector_widget.get_selected_items_string()
            if not playlist_items_string:
                 messagebox.showwarning("Warning", "No playlist items selected.")
                 return
            # -- START Phase 2 Change: Calculate count --
            # حساب عدد العناصر المحددة فعلياً
            playlist_items_count = len(playlist_items_string.split(','))
            # -- END Phase 2 Change --
            quality_format_id = None # جودة الفيديو المفرد لا تستخدم للقوائم
        else:
            quality_format_id = self.quality_selector_widget.get_selected_id()
            # إذا لم يكن وضع قائمة التشغيل، نعتبر العدد 1 (للفيديو المفرد)
            if not is_playlist:
                playlist_items_count = 1 # -- Phase 2 Change: Set count for single video --


        self.current_operation = 'download'
        self._enter_downloading_state()
        if self.logic:
            # -- START Phase 2 Change: Pass playlist_items_count --
            self.logic.start_download(
                url=url,
                save_path=save_path,
                format_choice=format_choice, # تمرير الخيار الجديد
                quality_format_id=quality_format_id,
                is_playlist=is_playlist,
                playlist_items=playlist_items_string,
                playlist_items_count=playlist_items_count # تمرير العدد
            )
            # -- END Phase 2 Change --

    def cancel_operation_ui(self):
        print("UI_Interface: Cancel button pressed.")
        if self.logic: self.logic.cancel_operation()

    # --- دوال الكول باك (Callback Methods) ---
    def update_status(self, message):
        """Updates the status label."""
        # (المنطق الداخلي لتحديد اللون لم يتغير)
        def _update():
            color = "gray"; msg_lower = message.lower()
            if "error" in msg_lower: color = "red"
            elif "warning" in msg_lower: color = "orange"
            elif "cancel" in msg_lower: color = "orange"
            elif "complete" in msg_lower or "finished downloading" in msg_lower or "success" in msg_lower : color = "green" # تعديل بسيط للنص
            elif "downloading" in msg_lower or "processing" in msg_lower or "fetching" in msg_lower: color="blue"
            self.status_label.configure(text=message, text_color=color)
        self.after(1, _update)

    def update_progress(self, value):
        value = max(0.0, min(1.0, value))
        self.after(1, lambda: self.progress_bar.set(value))

    def on_info_success(self, info_dict):
        def _update():
            self.fetched_info = info_dict
            is_playlist_mode_requested = self.options_frame_widget.get_playlist_mode()
            is_actually_playlist = isinstance(info_dict.get('entries'), list) if info_dict else False

            final_playlist_mode = False
            if is_playlist_mode_requested and is_actually_playlist:
                final_playlist_mode = True
                self.options_frame_widget.enable()
            elif is_playlist_mode_requested and not is_actually_playlist:
                 print("UI_Interface: Fetched info is not a playlist, turning switch off.")
                 self.options_frame_widget.set_playlist_mode(False)
                 final_playlist_mode = False
                 self.options_frame_widget.enable() # يمكن تغيير الوضع حتى لو لم تكن قائمة
            else: # طلب مفرد
                 final_playlist_mode = False
                 # تمكين المفتاح إذا كانت المعلومات قائمة فعلاً
                 if is_actually_playlist: self.options_frame_widget.enable()
                 else: self.options_frame_widget.disable() # تعطيله إذا لم يكن قائمة

            self._enter_info_fetched_state(final_playlist_mode)
        self.after(0, _update)

    def on_info_error(self, error_message):
        def _update():
            messagebox.showerror("Info Fetch Error", error_message) # سيتم تحسينه في المرحلة 3
            self._enter_idle_state()
        self.after(0, _update)

    def on_task_finished(self):
        def _process_finish():
            operation_type = self.current_operation
            self.current_operation = None

            final_status = self.status_label.cget("text").lower()
            print(f"UI_Interface: Task finished (Type: '{operation_type}'), final status: {final_status}")

            # --- (منطق التعامل مع الأخطاء والنجاح لم يتغير جوهريًا هنا، سيعتمد على رسالة الحالة النهائية) ---
            # --- (Logic for handling errors/success remains similar here, relies on final status message) ---
            if "error" in final_status or "cancel" in final_status:
                print("UI_Interface: Error or Cancel detected, restoring state.")
                if self.fetched_info:
                    is_playlist_mode = self.options_frame_widget.get_playlist_mode()
                    is_actually_playlist = isinstance(self.fetched_info.get('entries'), list)
                    final_playlist_mode = is_playlist_mode and is_actually_playlist
                    self._enter_info_fetched_state(final_playlist_mode)
                else:
                    self._enter_idle_state()
            elif operation_type == 'fetch' and "success" in final_status: # كن أكثر تحديدًا Be more specific
                 # حالة النجاح تم التعامل معها بالفعل في on_info_success
                 # Success case already handled in on_info_success
                 pass # لا تفعل شيئًا إضافيًا No need to do extra here
            elif operation_type == 'download' and ("complete" in final_status or "finished" in final_status):
                 print("UI_Interface: Download finished successfully. Resetting.")
                 self._enter_idle_state()
            else: # حالات أخرى (مثل فشل الجلب الذي يتم التعامل معه في on_info_error أو حالات غير متوقعة)
                 print(f"UI_Interface: Task finished state ('{final_status}') - Resetting or handled elsewhere.")
                 # غالبًا ما يكون قد تم إعادة التعيين بالفعل بواسطة معالج خطأ آخر
                 # Often already reset by another error handler
                 # تأكد من أننا في حالة مستقرة Ensure we are in a stable state
                 if not self.fetched_info or self.current_operation is not None:
                      self._enter_idle_state()


        self.after(10, _process_finish)