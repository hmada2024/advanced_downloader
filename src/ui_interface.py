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
        self._last_toggled_playlist_mode = True

        # --- إعداد النافذة ---
        self.title("Advanced Downloader")
        self.geometry("850x750")
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
        self.playlist_selector_widget = PlaylistSelector(self)

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

    # --- دوال إدارة الحالة ---
    def _enable_main_controls(self, enable_playlist_switch=True):
        self.top_frame_widget.enable_fetch()
        self.options_frame_widget.format_combobox.configure(state="normal")
        switch_state = "normal" if enable_playlist_switch else "disabled"
        self.options_frame_widget.playlist_switch.configure(state=switch_state)
        self.path_frame_widget.enable()

    def _enter_idle_state(self):
        self._enable_main_controls(enable_playlist_switch=True)
        self.bottom_controls_widget.disable_download(button_text="Download")
        self.bottom_controls_widget.hide_cancel_button()
        self.dynamic_area_label.configure(text="")
        self.quality_selector_widget.grid_remove()
        self.quality_selector_widget.reset()
        self.playlist_selector_widget.grid_remove()
        self.playlist_selector_widget.reset()
        self.fetched_info = None
        self.status_label.configure(text="Enter URL and click Fetch Info.", text_color="gray")
        self.progress_bar.set(0)
        self.current_operation = None
        self.options_frame_widget.set_playlist_mode(True)
        self._last_toggled_playlist_mode = True

    def _enter_fetching_state(self):
        self.top_frame_widget.disable_fetch(button_text="Fetching...")
        self.options_frame_widget.disable()
        self.path_frame_widget.disable()
        self.bottom_controls_widget.disable_download()
        self.bottom_controls_widget.show_cancel_button()
        self.status_label.configure(text="Fetching information...", text_color="orange")
        self.progress_bar.set(0)

    def _enter_info_fetched_state(self):
        if not self.fetched_info:
            print("Error: _enter_info_fetched_state called without fetched_info.")
            self._enter_idle_state()
            self.update_status("Error: Failed to process fetched information.")
            return

        is_actually_playlist = isinstance(self.fetched_info.get('entries'), list)
        self._enable_main_controls(enable_playlist_switch=is_actually_playlist)
        should_show_playlist_view = self.options_frame_widget.get_playlist_mode() and is_actually_playlist

        print(f"UI_Interface: Entering info fetched state. Actual playlist: {is_actually_playlist}, Switch ON: {self.options_frame_widget.get_playlist_mode()}, Show Playlist View: {should_show_playlist_view}")

        self.bottom_controls_widget.hide_cancel_button()

        if self.path_frame_widget.get_path() and os.path.isdir(self.path_frame_widget.get_path()):
            self.bottom_controls_widget.enable_download(button_text="Download Selection")
        else:
            self.bottom_controls_widget.disable_download(button_text="Select Save Location")

        if should_show_playlist_view:
            playlist_title = self.fetched_info.get('title', 'Untitled Playlist')
            total_items = len(self.fetched_info.get('entries', []))
            self.dynamic_area_label.configure(text=f"Playlist: {playlist_title} ({total_items} items total)")
            self.quality_selector_widget.grid_remove()
            self.playlist_selector_widget.populate_items(self.fetched_info.get('entries'))
            self.playlist_selector_widget.enable()
            self.playlist_selector_widget.grid(row=6, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")
            print("UI_Interface: Playlist frame gridded.")
        else:
            video_title = self.fetched_info.get('title', 'Untitled Video')
            self.dynamic_area_label.configure(text=f"Video: {video_title}")
            self.playlist_selector_widget.grid_remove()
            self.quality_selector_widget.populate_options(self.fetched_info.get('formats', []))
            self.quality_selector_widget.enable()
            self.quality_selector_widget.grid(row=5, column=0, columnspan=3, padx=15, pady=5, sticky="ew")
            print("UI_Interface: Quality frame gridded.")
            if is_actually_playlist:
                 self.options_frame_widget.playlist_switch.configure(state="normal")

        self.update_idletasks()

    # --- التعريف الصحيح للدالة ---
    def _enter_downloading_state(self):
        """Set UI state during download."""
        self.top_frame_widget.disable_fetch()
        self.options_frame_widget.disable()
        self.path_frame_widget.disable()
        self.quality_selector_widget.disable()
        self.playlist_selector_widget.disable()
        self.bottom_controls_widget.disable_download(button_text="Downloading...")
        self.bottom_controls_widget.show_cancel_button()
    # ----------------------------

    # --- معالجات الأحداث ---
    def browse_path_logic(self):
        directory = filedialog.askdirectory(title="Select Download Folder")
        if directory:
            self.path_frame_widget.set_path(directory)
            if self.fetched_info and self.bottom_controls_widget.download_button.cget("state") == "disabled":
                 self.bottom_controls_widget.enable_download(button_text="Download Selection")

    def fetch_video_info(self):
        url = self.top_frame_widget.get_url()
        if not url: messagebox.showerror("Input Error", "Please enter a URL."); return
        self.fetched_info = None
        self.quality_selector_widget.grid_remove(); self.playlist_selector_widget.grid_remove(); self.dynamic_area_label.configure(text="")
        self.top_frame_widget.set_url(url); self.current_operation = 'fetch'
        self._last_toggled_playlist_mode = self.options_frame_widget.get_playlist_mode()
        self._enter_fetching_state()
        if self.logic: self.logic.start_info_fetch(url)

    def toggle_playlist_mode(self):
        print("UI_Interface: Playlist switch toggled manually.")
        self._last_toggled_playlist_mode = self.options_frame_widget.get_playlist_mode()
        if self.fetched_info: self._enter_info_fetched_state()

    def start_download_ui(self):
        """Handles the 'Download' button click."""
        url = self.top_frame_widget.get_url(); save_path = self.path_frame_widget.get_path()
        format_choice = self.options_frame_widget.get_format_choice(); is_playlist_mode_on = self.options_frame_widget.get_playlist_mode()
        if not url: messagebox.showerror("Error", "URL is missing."); return
        if not save_path: messagebox.showerror("Error", "Save location is missing."); return
        if not os.path.isdir(save_path): messagebox.showerror("Error", "Save location is not a valid directory."); return
        if not self.fetched_info: messagebox.showerror("Error", "Fetch info first."); return
        quality_format_id = None; playlist_items_string = None; playlist_items_count = 0; is_actually_playlist = isinstance(self.fetched_info.get('entries'), list)
        if is_playlist_mode_on and is_actually_playlist:
            playlist_items_string = self.playlist_selector_widget.get_selected_items_string()
            if not playlist_items_string: messagebox.showwarning("Selection Error", "No playlist items selected for download."); return
            playlist_items_count = len(playlist_items_string.split(',')); quality_format_id = None; print(f"UI: Starting playlist download. Count: {playlist_items_count}, Items: {playlist_items_string}")
        elif not is_playlist_mode_on and self.fetched_info:
            if is_actually_playlist and not messagebox.askyesno("Confirm Single Download", "This is a playlist, but playlist mode is off.\nDo you want to download only the first video?"): return
            quality_format_id = self.quality_selector_widget.get_selected_id(); playlist_items_count = 1; print(f"UI: Starting single video download. Format ID: {quality_format_id}, General: {format_choice}")
        else: messagebox.showerror("Logic Error", "Mismatch between UI state and fetched info during download."); return

        # --- التأكد من استدعاء الدالة المعرفة في الكلاس ---
        self.current_operation = 'download'
        self._enter_downloading_state() # <-- الاستدعاء هنا
        # ---------------------------------------------
        if self.logic:
            self.logic.start_download(url=url, save_path=save_path, format_choice=format_choice, quality_format_id=quality_format_id,
                                      is_playlist=is_playlist_mode_on and is_actually_playlist, playlist_items=playlist_items_string, playlist_items_count=playlist_items_count)

    def cancel_operation_ui(self):
        print("UI_Interface: Cancel button pressed.");
        if self.current_operation: self.update_status("Cancellation requested...");
        if self.logic: self.logic.cancel_operation()
        else: print("UI_Interface: No operation to cancel.")

    # --- دوال الكول باك (Callback Methods) ---
    # (update_status, update_progress لم تتغير)
    def update_status(self, message):
        def _update():
            color = "gray"; msg_lower = message.lower()
            if "error" in msg_lower: color = "red"
            elif "warning" in msg_lower: color = "orange"
            elif "cancel" in msg_lower: color = "orange"
            elif "complete" in msg_lower or "finished downloading" in msg_lower or "success" in msg_lower or "finished:" in msg_lower: color = "green"
            elif "downloading" in msg_lower or "processing" in msg_lower or "fetching" in msg_lower or "starting" in msg_lower: color="blue"
            self.status_label.configure(text=message, text_color=color)
        self.after(1, _update)

    def update_progress(self, value):
        value = max(0.0, min(1.0, value)); self.after(1, lambda: self.progress_bar.set(value))

    def on_info_success(self, info_dict):
        def _update():
            self.fetched_info = info_dict
            if not info_dict: self.on_info_error("Received empty or invalid info."); return
            is_actually_playlist = isinstance(info_dict.get('entries'), list)
            if is_actually_playlist: print(f"Info success: It's a playlist. Restoring switch state to: {self._last_toggled_playlist_mode}"); self.options_frame_widget.set_playlist_mode(self._last_toggled_playlist_mode)
            else: print("Info success: It's not a playlist. Ensuring switch is OFF."); self.options_frame_widget.set_playlist_mode(False)
            self._enter_info_fetched_state()
            status_msg = "Info fetched successfully. Ready to download."
            if self.options_frame_widget.get_playlist_mode() and is_actually_playlist: status_msg = "Playlist info fetched. Select items and download."
            self.update_status(status_msg)
        self.after(0, _update)

    def on_info_error(self, error_message):
        def _update():
            print(f"UI_Interface: Info error callback received: {error_message}"); messagebox.showerror("Information Fetch Error", f"Could not fetch information:\n{error_message}"); self._enter_idle_state()
        self.after(0, _update)

    def on_task_finished(self):
        def _process_finish():
            operation_type = self.current_operation; final_status_text = self.status_label.cget("text"); final_status_color = self.status_label.cget("text_color")
            print(f"UI_Interface: Task finished notification (Type: '{operation_type}'). Final status: '{final_status_text}' (Color: {final_status_color})")
            was_cancelled = "cancel" in final_status_text.lower(); was_error = final_status_color == "red" or "error" in final_status_text.lower()
            if was_cancelled:
                print("UI: Operation was cancelled. Restoring previous state if info exists.")
                if self.fetched_info: self._enter_info_fetched_state(); self.update_status("Operation Cancelled.")
                else: self._enter_idle_state(); self.update_status("Info Fetch Cancelled.")
            elif was_error:
                print("UI: Operation failed. Restoring previous state if info exists.")
                if self.fetched_info: self._enter_info_fetched_state()
                else: self._enter_idle_state()
            elif operation_type == 'fetch' and not was_error and not was_cancelled: print("UI: Info fetch finished successfully (handled by on_info_success). State already updated."); pass
            elif operation_type == 'download' and not was_error and not was_cancelled:
                 print("UI: Download finished successfully. Resetting to idle state."); messagebox.showinfo("Download Complete", f"Download finished successfully!\nFile(s) saved in:\n{self.path_frame_widget.get_path()}"); self._enter_idle_state()
            else: print(f"UI: Task finished with unknown state or type. Resetting. (Op: {operation_type}, Status: {final_status_text})"); self._enter_idle_state()
            self.current_operation = None
        self.after(50, _process_finish)