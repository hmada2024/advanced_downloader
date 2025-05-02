import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import humanize # For readable file sizes (pip install humanize)

class AppInterface(ctk.CTk):
    def __init__(self, logic_handler):
        super().__init__()

        self.logic = logic_handler
        self.fetched_info = None
        self.selected_format_id = None
        self.playlist_checkboxes = []
        self.current_operation = None # <<-- ADD: Track current operation ('fetch' or 'download')
        self.format_map = {} # <<-- Initialize format_map here

        # --- Window Setup ---
        self.title("Enhanced Video/Audio Downloader")
        self.geometry("750x650")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- Configure Grid Layout ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(6, weight=1) # Playlist Frame row expands

        # --- Widgets --- (Rest of the widget setup remains the same as the previous corrected version)
        # Top Frame for URL and Fetch button
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="ew")
        self.top_frame.grid_columnconfigure(1, weight=1)

        self.url_label = ctk.CTkLabel(self.top_frame, text="Video/Playlist URL:")
        self.url_label.grid(row=0, column=0, padx=(0, 5), pady=5)
        self.url_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Enter URL and click Fetch Info", width=350)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.fetch_button = ctk.CTkButton(self.top_frame, text="Fetch Info", width=100, command=self.fetch_video_info)
        self.fetch_button.grid(row=0, column=2, padx=(5, 0), pady=5)

        # Options Frame
        self.options_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.options_frame.grid(row=1, column=0, columnspan=3, padx=15, pady=5, sticky="ew")
        self.options_frame.grid_columnconfigure(1, weight=1)
        self.options_frame.grid_columnconfigure(3, weight=0)

        self.format_label = ctk.CTkLabel(self.options_frame, text="Default Format:")
        self.format_label.grid(row=0, column=0, padx=(0,5), pady=5, sticky="w")
        self.format_combobox = ctk.CTkComboBox(self.options_frame, values=["Video (mp4, Best)", "Audio (mp3)"], width=180)
        self.format_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.format_combobox.set("Video (mp4, Best)")

        self.playlist_label = ctk.CTkLabel(self.options_frame, text="Is Playlist?")
        self.playlist_label.grid(row=0, column=2, padx=(20, 5), pady=5, sticky="e")
        self.playlist_switch_var = ctk.StringVar(value="off")
        self.playlist_switch = ctk.CTkSwitch(self.options_frame, text="", variable=self.playlist_switch_var,
                                              onvalue="on", offvalue="off", command=self.toggle_playlist_mode)
        self.playlist_switch.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # Save Path Frame
        self.path_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.path_frame.grid(row=2, column=0, columnspan=3, padx=15, pady=5, sticky="ew")
        self.path_frame.grid_columnconfigure(1, weight=1)

        self.path_label = ctk.CTkLabel(self.path_frame, text="Save Location:")
        self.path_label.grid(row=0, column=0, padx=(0,5), pady=5, sticky="w")
        self.path_entry = ctk.CTkEntry(self.path_frame, placeholder_text="Select download folder", state="readonly")
        self.path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_button = ctk.CTkButton(self.path_frame, text="Browse", width=80, command=self.browse_path)
        self.browse_button.grid(row=0, column=2, padx=(5, 0), pady=5)

        # Dynamic Area Title Label
        self.dynamic_area_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(weight="bold"))
        self.dynamic_area_label.grid(row=3, column=0, columnspan=3, padx=20, pady=(10,0), sticky="w")

        # Quality Selection Frame
        self.quality_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.quality_frame.grid_columnconfigure(0, weight=1)
        self.quality_label = ctk.CTkLabel(self.quality_frame, text="Available Qualities:")
        self.quality_label.grid(row=0, column=0, padx=5, pady=(5,0), sticky="w")
        self.quality_combobox = ctk.CTkComboBox(self.quality_frame, values=["Fetch info first"], state="disabled", command=self.on_quality_selected)
        self.quality_combobox.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        # Playlist Selection Frame
        self.playlist_frame = ctk.CTkScrollableFrame(self, label_text="Playlist Items")
        self.playlist_button_frame = ctk.CTkFrame(self.playlist_frame, fg_color="transparent")
        self.playlist_button_frame.pack(fill="x", pady=5, padx=5)
        self.playlist_select_all_button = ctk.CTkButton(self.playlist_button_frame, text="Select All", command=self.playlist_select_all)
        self.playlist_select_all_button.pack(side="left", padx=(0,5))
        self.playlist_deselect_all_button = ctk.CTkButton(self.playlist_button_frame, text="Deselect All", command=self.playlist_deselect_all)
        self.playlist_deselect_all_button.pack(side="left", padx=5)

        # Bottom Frame
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=7, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="ew")
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        self.bottom_frame.grid_columnconfigure(1, weight=0)

        self.download_button = ctk.CTkButton(self.bottom_frame, text="Download", command=self.start_download_ui, state="disabled")
        self.download_button.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
        self.cancel_button = ctk.CTkButton(self.bottom_frame, text="Cancel", command=self.cancel_operation_ui, state="disabled", fg_color="red", hover_color="darkred")

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=8, column=0, columnspan=3, padx=20, pady=(0, 5), sticky="ew")
        self.progress_bar.set(0)

        # Status Label
        self.status_label = ctk.CTkLabel(self, text="Enter URL and click Fetch Info.", text_color="gray")
        self.status_label.grid(row=9, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="ew")

        # Initial State
        self._enter_idle_state()


    # --- State Management Methods (_enter_idle_state, _enter_fetching_state, etc.) ---
    # (These remain mostly the same as the previous version, ensure grid rows are correct:
    # quality_frame uses row=5, playlist_frame uses row=6)

    def _enter_idle_state(self):
        """Reset UI to initial state, ready for new URL."""
        self.url_entry.configure(state="normal")
        self.fetch_button.configure(state="normal", text="Fetch Info")
        self.format_combobox.configure(state="normal")
        self.playlist_switch.configure(state="normal")
        self.browse_button.configure(state="normal")
        self.download_button.configure(state="disabled", text="Download")
        self.cancel_button.grid_remove()
        self.cancel_button.configure(state="disabled")
        self.download_button.grid_configure(columnspan=2)

        self.dynamic_area_label.configure(text="")
        self.quality_frame.grid_remove()
        self.playlist_frame.grid_remove()
        self.clear_playlist_checkboxes()
        self.quality_combobox.configure(values=["Fetch info first"], state="disabled")
        self.quality_combobox.set("Fetch info first")

        self.fetched_info = None
        self.selected_format_id = None
        self.status_label.configure(text="Enter URL and click Fetch Info.", text_color="gray")
        self.progress_bar.set(0)
        # self.current_operation = None # Reset operation type here too if needed


    def _enter_fetching_state(self):
        """UI state while fetching information."""
        self.url_entry.configure(state="disabled")
        self.fetch_button.configure(state="disabled", text="Fetching...")
        self.download_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="e")
        self.download_button.grid_configure(columnspan=1)
        self.status_label.configure(text="Fetching information...", text_color="orange")
        self.progress_bar.set(0)


    def _enter_info_fetched_state(self, is_playlist_mode):
        """UI state after info is fetched successfully."""
        print(f"DEBUG: Entering info fetched state. Playlist mode: {is_playlist_mode}") # Debug print
        self.fetch_button.configure(state="normal", text="Fetch Info")
        self.url_entry.configure(state="normal")

        if self.path_entry.get():
            self.download_button.configure(state="normal", text="Download Selection")
        else:
            self.download_button.configure(state="disabled", text="Select Save Location")

        self.cancel_button.grid_remove()
        self.cancel_button.configure(state="disabled")
        self.download_button.grid_configure(columnspan=2)

        # Show relevant dynamic section
        if is_playlist_mode and self.fetched_info and 'entries' in self.fetched_info:
            playlist_title = self.fetched_info.get('title', 'Untitled Playlist')
            self.dynamic_area_label.configure(text=f"Playlist: {playlist_title}")
            self.populate_playlist_items(self.fetched_info.get('entries'))
            self.quality_frame.grid_remove()
            # Ensure playlist frame uses correct row 6
            self.playlist_frame.grid(row=6, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")
            print("DEBUG: Playlist frame gridded.") # Debug print
        elif self.fetched_info:
            video_title = self.fetched_info.get('title', 'Untitled Video')
            self.dynamic_area_label.configure(text=f"Video: {video_title}")
            self.populate_quality_options(self.fetched_info.get('formats', []))
            self.playlist_frame.grid_remove()
            # Ensure quality frame uses correct row 5
            self.quality_frame.grid(row=5, column=0, columnspan=3, padx=15, pady=5, sticky="ew")
            print("DEBUG: Quality frame gridded.") # Debug print
        else:
             self.dynamic_area_label.configure(text="Error: Invalid information received.")
             self.quality_frame.grid_remove()
             self.playlist_frame.grid_remove()

        # Crucial: Force UI update to ensure the gridded frame becomes visible
        self.update_idletasks()


    def _enter_downloading_state(self):
        """UI state during active download."""
        self.fetch_button.configure(state="disabled")
        self.url_entry.configure(state="disabled")
        self.format_combobox.configure(state="disabled")
        self.playlist_switch.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        self.download_button.configure(state="disabled", text="Downloading...")
        self.cancel_button.configure(state="normal")
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="e")
        self.download_button.grid_configure(columnspan=1)

        self.quality_combobox.configure(state="disabled")
        for cb, var, index in self.playlist_checkboxes:
            if cb and isinstance(cb, ctk.CTkCheckBox):
                cb.configure(state="disabled")
        self.playlist_select_all_button.configure(state="disabled")
        self.playlist_deselect_all_button.configure(state="disabled")


    # --- Event Handlers & UI Logic ---
    # (browse_path, toggle_playlist_mode, quality methods, playlist methods remain the same)
    # --- Make sure populate_playlist_items uses the correct frame ---
    def clear_playlist_checkboxes(self):
         """Destroys old checkboxes and clears the internal list."""
         for cb, var, index in self.playlist_checkboxes:
             if cb and isinstance(cb, (ctk.CTkCheckBox, ctk.CTkLabel)):
                 try:
                     cb.destroy()
                 except Exception as e:
                     print(f"Error destroying widget: {e}")
         self.playlist_checkboxes = []

    def populate_playlist_items(self, entries):
        self.clear_playlist_checkboxes()
        container_frame = self.playlist_frame # Correct frame

        if not entries:
            no_items_label = ctk.CTkLabel(container_frame, text="No videos found in playlist.")
            no_items_label.pack(pady=5, padx=5, anchor="w")
            self.playlist_checkboxes.append((no_items_label, None, -1))
            self.playlist_select_all_button.configure(state="disabled")
            self.playlist_deselect_all_button.configure(state="disabled")
            return

        self.playlist_select_all_button.configure(state="normal")
        self.playlist_deselect_all_button.configure(state="normal")

        print(f"DEBUG: Populating playlist with {len(entries)} items.") # Debug
        for index, entry in enumerate(entries):
            if not entry: continue

            video_index = entry.get('playlist_index') or (index + 1)
            title = entry.get('title') or f'Video {video_index} (Untitled)'
            max_len = 70
            display_title = (title[:max_len] + '...') if len(title) > max_len else title

            var = ctk.StringVar(value="on")
            cb = ctk.CTkCheckBox(container_frame, text=f"{video_index}. {display_title}",
                                 variable=var, onvalue="on", offvalue="off")
            # Use pack INSIDE the scrollable frame
            cb.pack(anchor="w", padx=10, pady=(2, 2), fill="x")
            self.playlist_checkboxes.append((cb, var, video_index))
        print("DEBUG: Finished packing checkboxes.") # Debug


    def browse_path(self):
        directory = filedialog.askdirectory()
        if directory:
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, directory)
            self.path_entry.configure(state="readonly")
            if self.fetched_info and self.download_button.cget("state") == "disabled":
                 is_playlist_mode = self.playlist_switch_var.get() == "on"
                 is_actually_playlist = self.fetched_info and 'entries' in self.fetched_info
                 # Enable download if path is set AND (it's not playlist mode OR it is playlist mode with items)
                 if (not (is_playlist_mode and is_actually_playlist)) or \
                    (is_playlist_mode and is_actually_playlist and len(self.playlist_checkboxes) > 0):
                      self.download_button.configure(state="normal", text="Download Selection")

    def fetch_video_info(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return

        # Reset relevant parts of UI before starting fetch
        self.dynamic_area_label.configure(text="")
        self.quality_frame.grid_remove()
        self.playlist_frame.grid_remove()
        self.clear_playlist_checkboxes()
        self.quality_combobox.configure(values=["Fetch info first"], state="disabled")
        self.quality_combobox.set("Fetch info first")
        self.fetched_info = None
        self.selected_format_id = None
        self.download_button.configure(state="disabled", text="Download")

        self.current_operation = 'fetch' # <<-- SET Operation Type
        self._enter_fetching_state()
        self.logic.start_info_fetch(url)

    def toggle_playlist_mode(self):
        if self.fetched_info:
             is_playlist_mode = self.playlist_switch_var.get() == "on"
             is_actually_playlist = self.fetched_info and 'entries' in self.fetched_info
             if is_playlist_mode and not is_actually_playlist:
                  print("Cannot enter playlist mode: Fetched info has no 'entries'.")
                  self.playlist_switch_var.set("off")
                  self._enter_info_fetched_state(False)
             else:
                  self._enter_info_fetched_state(is_playlist_mode)

    def populate_quality_options(self, formats):
        self.quality_combobox.configure(state="normal")
        self.quality_combobox.set("Processing...")

        if not formats:
            self.quality_combobox.configure(values=["No formats available"], state="disabled")
            self.quality_combobox.set("No formats available")
            return

        options = ["Default (Use General Format)"]
        format_map = {"Default (Use General Format)": None}

        valid_formats = [f for f in formats if f and f.get('url') and f.get('format_id')]
        valid_formats.sort(key=lambda f: (
            f.get('ext') not in ('mp4', 'webm'),
            f.get('ext') != 'mp4',
            -(f.get('height') or 0),
            -(f.get('filesize') or f.get('filesize_approx') or 0)
            ), reverse=False)

        for f in valid_formats:
            desc = []
            fid = f.get('format_id')
            res = f.get('resolution')
            ext = f.get('ext', '?')
            vcodec = f.get('vcodec', 'none').split('.')[0]
            acodec = f.get('acodec', 'none').split('.')[0]
            dynamic_range = f.get('dynamic_range', '')
            fps = f.get('fps')
            size_bytes = f.get('filesize') or f.get('filesize_approx')
            size_readable = f" ({humanize.naturalsize(size_bytes, binary=True)})" if size_bytes else ""
            note = f.get('format_note', '')

            if vcodec != 'none' and res:
                desc.append(f"{res} {ext}")
                if fps: desc.append(f"{fps}fps")
                if dynamic_range: desc.append(dynamic_range)
                if note and note != res: desc.append(f"[{note}]")
                desc.append(f"(V:{vcodec}")
                if acodec != 'none': desc.append(f"+A:{acodec})")
                else: desc.append(")")
            elif acodec != 'none':
                 desc.append(f"Audio {ext}")
                 if note: desc.append(f"[{note}]")
                 desc.append(f"(A:{acodec})")
            else:
                desc.append(f"Format {fid} ({ext})")
                if note: desc.append(f"[{note}]")

            display_text = f"{' '.join(desc)}{size_readable}"
            options.append(display_text)
            format_map[display_text] = fid

        self.quality_combobox.configure(values=options)
        self.quality_combobox.set(options[0])
        self.format_map = format_map # Store the map
        self.selected_format_id = None

    def on_quality_selected(self, choice):
        self.selected_format_id = self.format_map.get(choice)
        print(f"Selected Quality: {choice}, Format ID: {self.selected_format_id}")
        if self.path_entry.get():
             self.download_button.configure(state="normal", text="Download Selection")

    def playlist_select_all(self):
        for cb, var, index in self.playlist_checkboxes:
            if var and isinstance(var, ctk.StringVar):
                var.set("on")

    def playlist_deselect_all(self):
        for cb, var, index in self.playlist_checkboxes:
            if var and isinstance(var, ctk.StringVar):
                var.set("off")

    def get_selected_playlist_items_string(self):
        selected_indices = []
        for cb, var, index in self.playlist_checkboxes:
            if cb and isinstance(cb, ctk.CTkCheckBox) and var and var.get() == "on":
                selected_indices.append(index)
        if not selected_indices: return None
        return ",".join(map(str, sorted(selected_indices)))

    def start_download_ui(self):
        url = self.url_entry.get()
        save_path = self.path_entry.get()
        format_choice = self.format_combobox.get()
        is_playlist = self.playlist_switch_var.get() == "on"

        if not url: messagebox.showerror("Error", "URL is missing."); return
        if not save_path: messagebox.showerror("Error", "Save location is missing."); return
        if not os.path.isdir(save_path): messagebox.showerror("Error", "Save location is not a valid directory."); return
        if not self.fetched_info: messagebox.showerror("Error", "Please fetch info before downloading."); return

        quality_format_id = None
        playlist_items_string = None
        is_actually_playlist = self.fetched_info and 'entries' in self.fetched_info

        if is_playlist and is_actually_playlist:
            playlist_items_string = self.get_selected_playlist_items_string()
            if not playlist_items_string:
                 messagebox.showwarning("Warning", "No playlist items selected for download.")
                 return
            quality_format_id = None # Use general format for playlist
        else:
            quality_format_id = self.selected_format_id

        self.current_operation = 'download' # <<-- SET Operation Type
        self._enter_downloading_state()
        self.logic.start_download(url, save_path, format_choice, quality_format_id, is_playlist, playlist_items_string)

    def cancel_operation_ui(self):
        print("Cancel button pressed.")
        self.logic.cancel_operation()


    # --- Callback Methods ---

    def update_status(self, message):
        def _update():
            # ... (status coloring logic remains the same) ...
            color = "gray"
            msg_lower = message.lower()
            if "error" in msg_lower: color = "red"
            elif "warning" in msg_lower: color = "orange"
            elif "cancel" in msg_lower: color = "orange"
            elif "complete" in msg_lower or "finished" in msg_lower or "success" in msg_lower : color = "green"
            elif "downloading" in msg_lower or "processing" in msg_lower or "fetching" in msg_lower: color="blue"
            self.status_label.configure(text=message, text_color=color)
        self.after(1, _update)

    def update_progress(self, value):
        value = max(0.0, min(1.0, value))
        self.after(1, lambda: self.progress_bar.set(value))

    def on_info_success(self, info_dict):
        """Callback when info is fetched successfully."""
        def _update():
            self.fetched_info = info_dict
            is_playlist_mode_requested = self.playlist_switch_var.get() == "on"
            is_actually_playlist = info_dict is not None and 'entries' in info_dict and isinstance(info_dict['entries'], list)

            final_playlist_mode = False
            if is_playlist_mode_requested and is_actually_playlist:
                final_playlist_mode = True
                self.playlist_switch.configure(state="normal")
            elif is_playlist_mode_requested and not is_actually_playlist:
                 print("Fetched info is not a playlist, turning switch off.")
                 self.playlist_switch_var.set("off")
                 final_playlist_mode = False
            elif not is_playlist_mode_requested and is_actually_playlist:
                 final_playlist_mode = False
                 self.playlist_switch.configure(state="normal")
            else:
                 final_playlist_mode = False

            # This is the key part: After successfully fetching info,
            # immediately enter the correct state. on_task_finished will handle button re-enabling later.
            self._enter_info_fetched_state(final_playlist_mode)
        self.after(0, _update)


    def on_info_error(self, error_message):
        """Callback when info fetching fails."""
        def _update():
            messagebox.showerror("Info Fetch Error", error_message)
            self._enter_idle_state() # Return to idle state on error
            self.current_operation = None # Clear operation type on error
        self.after(0, _update)


    def on_task_finished(self):
        """Callback when ANY background task finishes, fails, or cancels."""
        def _process_finish():
            # Get the type of operation that just finished
            operation_type = self.current_operation
            self.current_operation = None # Reset flag for the next operation

            final_status = self.status_label.cget("text").lower()
            print(f"Task finished (Type: '{operation_type}'), final status: {final_status}") # Debugging

            # Handle errors or cancellation first - these usually lead to reset
            if "error" in final_status or "cancel" in final_status:
                print("DEBUG: Error or Cancel detected, resetting UI.")
                if self.fetched_info:
                    # Try to restore the info fetched state if info exists
                    is_playlist_mode = self.playlist_switch_var.get() == "on"
                    is_actually_playlist = 'entries' in self.fetched_info and isinstance(self.fetched_info['entries'], list)
                    final_playlist_mode = is_playlist_mode and is_actually_playlist
                    self._enter_info_fetched_state(final_playlist_mode)
                else:
                    # Full reset if no info ever fetched
                    self._enter_idle_state()
            # If no error/cancel, check the operation type
            elif operation_type == 'fetch':
                # If info fetch finished successfully, the UI state should already
                # be mostly correct due to on_info_success. We just need to ensure
                # the buttons/controls are fully re-enabled correctly by reapplying the state.
                print("DEBUG: Fetch finished successfully. Re-applying info_fetched state.")
                if self.fetched_info:
                     is_playlist_mode = self.playlist_switch_var.get() == "on"
                     is_actually_playlist = 'entries' in self.fetched_info and isinstance(self.fetched_info['entries'], list)
                     final_playlist_mode = is_playlist_mode and is_actually_playlist
                     self._enter_info_fetched_state(final_playlist_mode) # Re-apply state
                else:
                     print("WARN: Fetch finished successfully but fetched_info is missing? Resetting.")
                     self._enter_idle_state() # Fallback if info missing
            elif operation_type == 'download':
                 # If download finished successfully, go back to idle state
                 print("DEBUG: Download finished successfully. Resetting to idle state.")
                 self._enter_idle_state()
            else:
                 # Unknown operation or finished unexpectedly? Go idle.
                 print(f"DEBUG: Unknown or no operation type ('{operation_type}'). Resetting to idle state.")
                 self._enter_idle_state()

        # Use after(10) to allow final status message to be seen before UI reset/change
        self.after(10, _process_finish)