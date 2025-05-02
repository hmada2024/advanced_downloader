import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import humanize # For readable file sizes (pip install humanize)

class AppInterface(ctk.CTk):
    def __init__(self, logic_handler):
        super().__init__()

        self.logic = logic_handler # Logic handler instance passed from main.py
        self.fetched_info = None   # Store fetched video/playlist info
        self.selected_format_id = None # Store chosen quality format ID
        self.playlist_checkboxes = [] # Store playlist checkboxes

        # --- Window Setup ---
        self.title("Enhanced Video/Audio Downloader")
        self.geometry("750x650") # Increased size for new elements
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # --- Configure Grid Layout ---
        self.grid_columnconfigure(1, weight=1) # URL/Path entry column expands
        # Configure rows to allow expansion for playlist/quality sections
        self.grid_rowconfigure(5, weight=0) # Quality Frame row
        self.grid_rowconfigure(6, weight=1) # Playlist Frame row (expands most)
        self.grid_rowconfigure(9, weight=0) # Progress/Status row

        # --- Widgets ---

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
        self.options_frame.grid_columnconfigure(3, weight=1) # Add weight for spacing if needed

        # General Format Selection (Fallback/Initial)
        self.format_label = ctk.CTkLabel(self.options_frame, text="Default Format:")
        self.format_label.grid(row=0, column=0, padx=(0,5), pady=5, sticky="w")
        self.format_combobox = ctk.CTkComboBox(self.options_frame, values=["Video (mp4, Best)", "Audio (mp3)"], width=180)
        self.format_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.format_combobox.set("Video (mp4, Best)")

        # Playlist Toggle
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

        # --- Dynamic Area Title Label ---
        self.dynamic_area_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(weight="bold"))
        self.dynamic_area_label.grid(row=3, column=0, columnspan=3, padx=20, pady=(10,0), sticky="w")


        # --- Quality Selection Frame (Initially Hidden) ---
        self.quality_frame = ctk.CTkFrame(self, fg_color="transparent")
        # quality_frame is placed in grid later when needed (row 4)
        self.quality_frame.grid_columnconfigure(0, weight=1) # Make combobox expand

        self.quality_label = ctk.CTkLabel(self.quality_frame, text="Available Qualities:")
        self.quality_label.grid(row=0, column=0, padx=5, pady=(5,0), sticky="w")
        self.quality_combobox = ctk.CTkComboBox(self.quality_frame, values=["Fetch info first"], state="disabled", command=self.on_quality_selected)
        self.quality_combobox.grid(row=1, column=0, padx=5, pady=5, sticky="ew")


        # --- Playlist Selection Frame (Initially Hidden) ---
        self.playlist_frame = ctk.CTkScrollableFrame(self, label_text="Playlist Items")
        # playlist_frame is placed in grid later when needed (row 5)
        # self.playlist_frame.grid(row=5, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")
        # self.playlist_frame.grid_remove() # Hide it initially

        self.playlist_select_all_button = ctk.CTkButton(self.playlist_frame, text="Select All", command=self.playlist_select_all)
        self.playlist_select_all_button.pack(pady=5, padx=5, anchor="w")
        self.playlist_deselect_all_button = ctk.CTkButton(self.playlist_frame, text="Deselect All", command=self.playlist_deselect_all)
        self.playlist_deselect_all_button.pack(pady=5, padx=5, anchor="w")
        # Checkboxes will be added here dynamically


        # --- Bottom Frame for Download/Cancel and Progress ---
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=7, column=0, columnspan=3, padx=15, pady=(10, 15), sticky="ew")
        self.bottom_frame.grid_columnconfigure(0, weight=1) # Allow button to expand if needed
        self.bottom_frame.grid_columnconfigure(1, weight=0) # Keep cancel button fixed size


        # Download Button
        self.download_button = ctk.CTkButton(self.bottom_frame, text="Download", command=self.start_download_ui, state="disabled")
        self.download_button.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")

        # Cancel Button (Initially Hidden/Managed)
        self.cancel_button = ctk.CTkButton(self.bottom_frame, text="Cancel", command=self.cancel_operation_ui, state="disabled", fg_color="red", hover_color="darkred")
        # Cancel button is placed/removed dynamically

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=8, column=0, columnspan=3, padx=20, pady=(0, 5), sticky="ew")
        self.progress_bar.set(0)

        # Status Label
        self.status_label = ctk.CTkLabel(self, text="Enter URL and click Fetch Info.", text_color="gray")
        self.status_label.grid(row=9, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="ew")

        # Initial UI state setup
        self._enter_idle_state()


    # --- State Management ---

    def _enter_idle_state(self):
        """Reset UI to initial state, ready for new URL."""
        self.url_entry.configure(state="normal")
        self.fetch_button.configure(state="normal", text="Fetch Info")
        self.format_combobox.configure(state="normal")
        self.playlist_switch.configure(state="normal")
        self.browse_button.configure(state="normal")
        self.download_button.configure(state="disabled", text="Download")
        # Ensure cancel button is hidden and disabled
        self.cancel_button.grid_remove()
        self.cancel_button.configure(state="disabled")
        # Make download button span entire bottom row when cancel is hidden
        self.download_button.grid_configure(columnspan=2)


        # Clear dynamic areas
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


    def _enter_fetching_state(self):
        """UI state while fetching information."""
        self.url_entry.configure(state="disabled")
        self.fetch_button.configure(state="disabled", text="Fetching...")
        self.download_button.configure(state="disabled")
        self.cancel_button.configure(state="normal") # Enable cancel during fetch
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="e")
         # Make download button take less space
        self.download_button.grid_configure(columnspan=1)
        self.status_label.configure(text="Fetching information...", text_color="orange")
        self.progress_bar.set(0) # Or use indeterminate mode: self.progress_bar.start()


    def _enter_info_fetched_state(self, is_playlist_mode):
        """UI state after info is fetched successfully."""
        self.fetch_button.configure(state="normal", text="Fetch Info") # Allow re-fetching
        self.url_entry.configure(state="normal")
        self.browse_button.configure(state="disabled") # Disable browse after fetch? Or allow? User preference. Let's allow.

        # Enable download button only if save path is set
        if self.path_entry.get():
            self.download_button.configure(state="normal", text="Download Selection")
        else:
             self.download_button.configure(state="disabled", text="Select Save Location")

        self.cancel_button.grid_remove() # Hide cancel button
        self.cancel_button.configure(state="disabled")
        self.download_button.grid_configure(columnspan=2) # Download takes full width

        # Show relevant dynamic section
        if is_playlist_mode and 'entries' in self.fetched_info:
             self.dynamic_area_label.configure(text=f"Playlist: {self.fetched_info.get('title', 'Untitled Playlist')}")
             self.populate_playlist_items(self.fetched_info['entries'])
             self.quality_frame.grid_remove() # Hide quality selector for playlist
             self.playlist_frame.grid(row=6, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")
        else: # Single video or playlist treated as single
            video_title = self.fetched_info.get('title', 'Untitled Video')
            self.dynamic_area_label.configure(text=f"Video: {video_title}")
            self.populate_quality_options(self.fetched_info.get('formats', []))
            self.playlist_frame.grid_remove() # Hide playlist selector
            self.quality_frame.grid(row=4, column=0, columnspan=3, padx=15, pady=5, sticky="ew")


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

        # Disable dynamic areas too
        self.quality_combobox.configure(state="disabled")
        # Disable checkboxes (optional, but good practice)
        for cb, var in self.playlist_checkboxes:
            cb.configure(state="disabled")
        self.playlist_select_all_button.configure(state="disabled")
        self.playlist_deselect_all_button.configure(state="disabled")


    # --- Event Handlers & UI Logic ---

    def browse_path(self):
        directory = filedialog.askdirectory()
        if directory:
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, directory)
            self.path_entry.configure(state="readonly")
            # If info was already fetched, enable download button now
            if self.fetched_info and self.download_button.cget("state") == "disabled":
                self.download_button.configure(state="normal", text="Download Selection")


    def fetch_video_info(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return

        self._enter_fetching_state()
        self.logic.start_info_fetch(url)

    def toggle_playlist_mode(self):
        # If info is already fetched, update the UI to show/hide relevant sections
        if self.fetched_info:
             is_playlist_mode = self.playlist_switch_var.get() == "on"
             self._enter_info_fetched_state(is_playlist_mode)


    def populate_quality_options(self, formats):
        self.quality_combobox.configure(state="normal")
        if not formats:
            self.quality_combobox.configure(values=["No formats found"], state="disabled")
            self.quality_combobox.set("No formats found")
            return

        options = ["Default (Use General Format)"] # Option to use the top combobox
        format_map = {"Default (Use General Format)": None} # Map display string to format_id

        # Sort formats: prioritize mp4, then resolution, then filesize
        formats.sort(key=lambda f: (
            f.get('ext') != 'mp4', # False (mp4) comes first
            -(f.get('height') or 0), # Higher resolution first
            -(f.get('filesize') or f.get('filesize_approx') or 0) # Larger filesize (proxy for quality)
            ), reverse=False)


        for f in formats:
            # Create a readable description
            desc = []
            res = f.get('resolution', 'audio')
            ext = f.get('ext', '?')
            vcodec = f.get('vcodec', 'none')
            acodec = f.get('acodec', 'none')
            dynamic_range = f.get('dynamic_range', '')
            fps = f.get('fps')
            size_bytes = f.get('filesize') or f.get('filesize_approx')
            size_readable = f" ({humanize.naturalsize(size_bytes, binary=True)})" if size_bytes else ""

            if vcodec != 'none':
                desc.append(f"{res} {ext}")
                if fps: desc.append(f"{fps}fps")
                if dynamic_range : desc.append(dynamic_range)
                # desc.append(f"V:{vcodec.split('.')[0]}") # Short codec name
            # Only show audio details if it's audio-only or specifically requested
            if acodec != 'none' and vcodec == 'none':
                 desc.append(f"Audio {ext}")
                 # desc.append(f"A:{acodec.split('.')[0]}")
            elif acodec != 'none':
                 pass # Already covered by video info usually
                 # desc.append(f"A:{acodec.split('.')[0]}")

            if not desc: # Fallback if no details found
                desc_str = f"Format {f.get('format_id', '?')} ({ext})"
            else:
                desc_str = ' '.join(desc)

            display_text = f"{desc_str}{size_readable}"
            options.append(display_text)
            format_map[display_text] = f.get('format_id')

        self.quality_combobox.configure(values=options)
        self.quality_combobox.set(options[0]) # Select default
        self.format_map = format_map # Store the map for later lookup
        self.selected_format_id = None # Reset selection


    def on_quality_selected(self, choice):
        """Stores the format_id when a quality is chosen from the combobox."""
        self.selected_format_id = self.format_map.get(choice)
        print(f"Selected Quality: {choice}, Format ID: {self.selected_format_id}")


    def clear_playlist_checkboxes(self):
         for cb, var in self.playlist_checkboxes:
             cb.destroy()
         self.playlist_checkboxes = []

    def populate_playlist_items(self, entries):
        self.clear_playlist_checkboxes()
        if not entries:
            # Handle case where playlist fetch returned no entries
            no_items_label = ctk.CTkLabel(self.playlist_frame, text="No videos found in playlist.")
            no_items_label.pack(pady=5, padx=5)
            self.playlist_checkboxes.append((no_items_label, None)) # Add placeholder
            return

        for index, entry in enumerate(entries):
            if not entry: continue # Skip if entry is None
            title = entry.get('title', f'Video {index + 1} (Untitled)')
            # Make title shorter if too long
            max_len = 80
            display_title = (title[:max_len] + '...') if len(title) > max_len else title

            var = ctk.StringVar(value="on") # Default to selected
            cb = ctk.CTkCheckBox(self.playlist_frame, text=f"{index + 1}. {display_title}", variable=var, onvalue="on", offvalue="off")
            cb.pack(anchor="w", padx=10, pady=2)
            # Store checkbox, its variable, and the original index+1
            self.playlist_checkboxes.append((cb, var, index + 1))


    def playlist_select_all(self):
        for cb, var, index in self.playlist_checkboxes:
            if var: var.set("on")

    def playlist_deselect_all(self):
        for cb, var, index in self.playlist_checkboxes:
             if var: var.set("off")

    def get_selected_playlist_items_string(self):
        """Generates the playlist items string (e.g., '1,3,5-7') for yt-dlp."""
        selected_indices = []
        for cb, var, index in self.playlist_checkboxes:
            if var and var.get() == "on":
                selected_indices.append(index)

        if not selected_indices:
            return None # No items selected

        # Basic implementation: comma-separated string
        # TODO: Implement range compression (e.g., 1,2,3,5 -> 1-3,5) for efficiency if needed
        return ",".join(map(str, selected_indices))


    def start_download_ui(self):
        url = self.url_entry.get()
        save_path = self.path_entry.get()
        format_choice = self.format_combobox.get() # General format
        is_playlist = self.playlist_switch_var.get() == "on"

        # --- Validation ---
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
             messagebox.showerror("Error", "Please fetch info before downloading.")
             return

        # --- Get Specific Selections ---
        quality_format_id = self.selected_format_id # Might be None if 'Default' was chosen
        playlist_items_string = None
        if is_playlist and 'entries' in self.fetched_info:
            playlist_items_string = self.get_selected_playlist_items_string()
            if not playlist_items_string:
                 messagebox.showwarning("Warning", "No playlist items selected for download.")
                 return # Or proceed to download all? User choice. Let's stop.

        # --- Start Download ---
        self._enter_downloading_state()
        self.logic.start_download(url, save_path, format_choice, quality_format_id, is_playlist, playlist_items_string)

    def cancel_operation_ui(self):
        """Called when the Cancel button is pressed."""
        self.logic.cancel_operation()
        # UI state change (e.g., showing "Cancelling...") is handled by the status callback
        # Button state will be reset in on_task_finished


    # --- Callback Methods (Called by Logic Handler via self.after) ---

    def update_status(self, message):
        def _update():
            color = "gray"
            msg_lower = message.lower()
            if "error" in msg_lower: color = "red"
            elif "warning" in msg_lower: color = "orange"
            elif "cancel" in msg_lower: color = "orange"
            elif "complete" in msg_lower or "finished" in msg_lower or "success" in msg_lower : color = "green"
            elif "downloading" in msg_lower or "processing" in msg_lower or "fetching" in msg_lower: color="blue"
            self.status_label.configure(text=message, text_color=color)
        self.after(0, _update)

    def update_progress(self, value):
        self.after(0, lambda: self.progress_bar.set(value))

    def on_info_success(self, info_dict):
        """Callback when info is fetched successfully."""
        def _update():
            self.fetched_info = info_dict
            is_playlist_mode = self.playlist_switch_var.get() == "on"
             # If it's not a playlist according to yt-dlp, force switch off
            if 'entries' not in info_dict and is_playlist_mode:
                print("Fetched info is not a playlist, turning switch off.")
                self.playlist_switch_var.set("off")
                is_playlist_mode = False
                # Optionally disable the switch entirely if it's definitely not a playlist
                # self.playlist_switch.configure(state="disabled")
            else:
                 # Re-enable switch if it was disabled maybe?
                 self.playlist_switch.configure(state="normal")

            self._enter_info_fetched_state(is_playlist_mode)
        self.after(0, _update)


    def on_info_error(self, error_message):
        """Callback when info fetching fails."""
        def _update():
            messagebox.showerror("Info Fetch Error", error_message)
            self._enter_idle_state() # Return to idle state on error
        self.after(0, _update)


    def on_task_finished(self):
        """Callback when any background task (fetch or download) finishes/fails/cancels."""
        def _reset_ui():
             # Check the final status message to decide the next state
            final_status = self.status_label.cget("text").lower()
            if "error" in final_status or "cancel" in final_status:
                 # If there was an error or cancellation, go back to idle/ready state
                 # but keep fetched info if available to allow retry or modification
                 if self.fetched_info:
                     is_playlist_mode = self.playlist_switch_var.get() == "on"
                     self._enter_info_fetched_state(is_playlist_mode) # Re-enable controls based on fetched info
                 else:
                     self._enter_idle_state() # Full reset if no info was ever fetched
            else:
                 # Assume success, ready for next operation
                 self._enter_idle_state() # Go back to idle after successful download
        self.after(0, _reset_ui)