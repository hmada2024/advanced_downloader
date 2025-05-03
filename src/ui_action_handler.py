# src/ui_action_handler.py
# -- Mixin class for handling user actions from the UI --

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os # Needed for isdir check

# Note: This class assumes it's mixed into a class that has attributes like:
# self.logic, self.top_frame_widget, self.options_frame_widget,
# self.path_frame_widget, self.playlist_selector_widget, self.bottom_controls_widget,
# self.fetched_info, self.current_operation, self._last_toggled_playlist_mode
# and methods from UIStateManagerMixin like _enter_fetching_state, _enter_downloading_state, _enter_info_fetched_state
# and methods from UICallbackHandlerMixin like update_status

class UIActionHandlerMixin:
    """Mixin class containing methods for handling user actions and initiating logic operations."""

    def browse_path_logic(self):
        """Opens directory dialog, updates path widget, and enables download if appropriate."""
        # Use := assignment expression (Python 3.8+)
        if directory := filedialog.askdirectory(title="Select Download Folder"):
            self.path_frame_widget.set_path(directory)
            # If path is selected AND info was already fetched, enable download button
            # Check the button state to avoid unnecessary configuring
            if self.fetched_info and self.bottom_controls_widget.download_button.cget("state") == "disabled":
                self.bottom_controls_widget.enable_download(button_text="Download Selection")

    def fetch_video_info(self):
        """Initiates the process to fetch info for the entered URL."""
        url = self.top_frame_widget.get_url()
        if not url:
            messagebox.showerror("Input Error", "Please enter a URL.")
            return

        # Reset state before starting fetch
        self.fetched_info = None
        self.playlist_selector_widget.grid_remove()
        self.dynamic_area_label.configure(text="")
        self.top_frame_widget.set_url(url) # Ensure URL stays in the entry

        self.current_operation = "fetch" # Mark current operation
        # Store the playlist switch state BEFORE starting fetch
        self._last_toggled_playlist_mode = self.options_frame_widget.get_playlist_mode()
        self._enter_fetching_state() # Transition UI to fetching state

        # Call logic handler to start the actual fetch in a background thread
        if self.logic:
            self.logic.start_info_fetch(url)

    def toggle_playlist_mode(self):
        """Handles the manual toggling of the 'Is Playlist?' switch."""
        print("UI_Interface: Playlist switch toggled manually.")
        # Store the new state
        self._last_toggled_playlist_mode = self.options_frame_widget.get_playlist_mode()
        # If info is already fetched, re-render the UI to reflect the change
        if self.fetched_info:
            self._enter_info_fetched_state()

    def start_download_ui(self):
        """Initiates the download process based on current selections."""
        url = self.top_frame_widget.get_url()
        save_path = self.path_frame_widget.get_path()
        format_choice = self.options_frame_widget.get_format_choice() # Always use the general choice
        is_playlist_mode_on = self.options_frame_widget.get_playlist_mode()

        # Basic input validation
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

        playlist_items_string = None
        selected_items_count = 0
        total_playlist_count = 0
        is_actually_playlist = isinstance(self.fetched_info.get("entries"), list)

        if is_actually_playlist:
            total_playlist_count = len(self.fetched_info.get("entries", []))

        # Determine download behavior (playlist or single)
        if is_playlist_mode_on and is_actually_playlist:
            # Playlist download
            playlist_items_string = self.playlist_selector_widget.get_selected_items_string()
            if not playlist_items_string:
                messagebox.showwarning("Selection Error", "No playlist items selected for download.")
                return
            # Calculate selected count from the resulting string
            selected_items_count = len(playlist_items_string.split(","))
            print(f"UI: Starting playlist download. Selected: {selected_items_count}, Total: {total_playlist_count}, Items: {playlist_items_string}, Format: {format_choice}")

        elif not is_playlist_mode_on and self.fetched_info:
            # Single video download (or first item if playlist mode is off)
            if is_actually_playlist and not messagebox.askyesno(
                                "Confirm Single Download",
                                "This is a playlist, but playlist mode is off.\nDo you want to download only the first video/item based on the URL?",
                            ):
                return
            # Quality is determined solely by format_choice from the top dropdown
            selected_items_count = 1 # Only one item
            print(f"UI: Starting single video/item download. General Format: {format_choice}, Playlist Total (if any): {total_playlist_count}")
        else:
            # Should not happen if UI state logic is correct
            messagebox.showerror("Logic Error", "Mismatch between UI state and fetched info during download.")
            return

        self.current_operation = "download" # Mark current operation
        self._enter_downloading_state() # Transition UI to downloading state

        # Call logic handler to start the actual download
        if self.logic:
            self.logic.start_download(
                url=url,
                save_path=save_path,
                format_choice=format_choice, # Pass the general format choice
                # quality_format_id parameter is completely removed
                is_playlist=is_playlist_mode_on and is_actually_playlist,
                playlist_items=playlist_items_string,
                selected_items_count=selected_items_count,
                total_playlist_count=total_playlist_count,
            )

    def cancel_operation_ui(self):
        """Requests cancellation of the active background operation."""
        print("UI_Interface: Cancel button pressed.")
        if self.current_operation:
            # update_status is in UICallbackHandlerMixin, accessible via self
            self.update_status("Cancellation requested...")
        if self.logic:
            self.logic.cancel_operation() # Signal cancellation to logic handler
        else:
            # Fallback if logic handler isn't available (shouldn't happen)
            print("UI_Interface: No logic handler available to cancel.")
            # _enter_idle_state is in UIStateManagerMixin, accessible via self
            self._enter_idle_state() # Go back to a safe state