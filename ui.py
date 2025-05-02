import customtkinter as ctk
from tkinter import filedialog, messagebox
import os

class AppInterface(ctk.CTk):
    def __init__(self, logic_handler):
        super().__init__()

        self.logic = logic_handler # Reference to the logic class instance

        # --- Window Setup ---
        self.title("Modern Video/Audio Downloader")
        self.geometry("650x450")
        ctk.set_appearance_mode("System")  # Modes: "System" (default), "Dark", "Light"
        ctk.set_default_color_theme("blue")  # Themes: "blue" (default), "green", "dark-blue"

        # --- Configure Grid Layout ---
        self.grid_columnconfigure(1, weight=1) # Allow entry/path fields to expand
        self.grid_rowconfigure(5, weight=1) # Allow status area to take space

        # --- Widgets ---

        # URL Input
        self.url_label = ctk.CTkLabel(self, text="Video/Playlist URL:")
        self.url_label.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")
        self.url_entry = ctk.CTkEntry(self, placeholder_text="Enter URL here", width=350)
        self.url_entry.grid(row=0, column=1, padx=20, pady=(20, 10), sticky="ew")

        # Format Selection
        self.format_label = ctk.CTkLabel(self, text="Format:")
        self.format_label.grid(row=1, column=0, padx=20, pady=10, sticky="w")
        self.format_combobox = ctk.CTkComboBox(self, values=["Video (mp4, Best)", "Audio (mp3)"])
        self.format_combobox.grid(row=1, column=1, padx=20, pady=10, sticky="ew")
        self.format_combobox.set("Video (mp4, Best)") # Default value

        # Playlist Toggle
        self.playlist_label = ctk.CTkLabel(self, text="Download Playlist?")
        self.playlist_label.grid(row=2, column=0, padx=20, pady=10, sticky="w")
        self.playlist_switch_var = ctk.StringVar(value="off") # Use StringVar for switch
        self.playlist_switch = ctk.CTkSwitch(self, text="", variable=self.playlist_switch_var,
                                              onvalue="on", offvalue="off")
        self.playlist_switch.grid(row=2, column=1, padx=20, pady=10, sticky="w")


        # Save Path
        self.path_label = ctk.CTkLabel(self, text="Save Location:")
        self.path_label.grid(row=3, column=0, padx=20, pady=10, sticky="w")
        self.path_entry = ctk.CTkEntry(self, placeholder_text="Select download folder", state="readonly")
        self.path_entry.grid(row=3, column=1, padx=(20, 5), pady=10, sticky="ew")
        self.browse_button = ctk.CTkButton(self, text="Browse", width=80, command=self.browse_path)
        self.browse_button.grid(row=3, column=2, padx=(5, 20), pady=10, sticky="e")


        # Download Button
        self.download_button = ctk.CTkButton(self, text="Download", command=self.start_download_ui)
        self.download_button.grid(row=4, column=0, columnspan=3, padx=20, pady=20, sticky="ew")

        # Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=5, column=0, columnspan=3, padx=20, pady=(0, 5), sticky="ew")
        self.progress_bar.set(0) # Initial state

        # Status Label
        self.status_label = ctk.CTkLabel(self, text="Ready", text_color="gray")
        self.status_label.grid(row=6, column=0, columnspan=3, padx=20, pady=(0, 20), sticky="ew")


    def browse_path(self):
        """Opens a dialog to select a directory and updates the path entry."""
        directory = filedialog.askdirectory()
        if directory: # Only update if a directory was selected
            self.path_entry.configure(state="normal") # Enable writing
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, directory)
            self.path_entry.configure(state="readonly") # Disable writing again

    def start_download_ui(self):
        """Gets user inputs from UI and triggers the download logic."""
        url = self.url_entry.get()
        save_path = self.path_entry.get()
        format_choice = self.format_combobox.get()
        is_playlist = self.playlist_switch_var.get() == "on"

        # Basic validation
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return
        if not save_path:
             messagebox.showerror("Error", "Please select a save location.")
             return
        if not os.path.isdir(save_path):
             messagebox.showerror("Error", "The selected save location is not a valid directory.")
             return

        # Disable button during download
        self.download_button.configure(state="disabled", text="Downloading...")
        self.status_label.configure(text="Preparing...", text_color="orange")
        self.progress_bar.set(0)

        # Start the download via the logic handler
        self.logic.start_download(url, save_path, format_choice, is_playlist)


    # --- Callback Methods (Called by Logic Handler) ---
    # These need to use `self.after` to safely update the UI from another thread

    def update_status(self, message):
        """Thread-safe method to update the status label."""
        def _update():
            # Determine color based on message content (basic example)
            color = "gray"
            if "Error" in message or "Warning" in message:
                color = "red"
            elif "complete" in message.lower():
                color = "green"
            elif "Downloading" in message or "processing" in message:
                color="blue" # Or keep default theme color
            self.status_label.configure(text=message, text_color=color)
        self.after(0, _update) # Schedule the update on the main UI thread

    def update_progress(self, value):
        """Thread-safe method to update the progress bar."""
        self.after(0, lambda: self.progress_bar.set(value)) # Schedule update

    def on_download_finished(self):
        """Thread-safe method called when download logic finishes (success or fail)."""
        def _reset():
            self.download_button.configure(state="normal", text="Download")
            # Optionally reset progress bar if not already at 1 or 0 after error
            # current_progress = self.progress_bar.get()
            # if "Error" in self.status_label.cget("text"):
            #    self.progress_bar.set(0)

        self.after(0, _reset) # Schedule reset on the main UI thread