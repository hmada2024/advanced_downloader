# src/ui_state_manager.py
# -- Mixin class for managing UI states --

import customtkinter as ctk
import os # Needed for isdir check within _enter_info_fetched_state

# Note: This class assumes it's mixed into a class that has attributes like:
# self.top_frame_widget, self.options_frame_widget, self.path_frame_widget,
# self.bottom_controls_widget, self.playlist_selector_widget, self.dynamic_area_label,
# self.status_label, self.progress_bar, self.fetched_info, self.current_operation,
# self._last_toggled_playlist_mode, and methods like update_status

class UIStateManagerMixin:
    """Mixin class containing methods for managing the UI state transitions."""

    def _enable_main_controls(self, enable_playlist_switch=True):
        """Enables the main input controls (URL, options, path)."""
        self.top_frame_widget.enable_fetch()
        self.options_frame_widget.format_combobox.configure(state="normal")
        # Enable/disable playlist switch based on context
        switch_state = "normal" if enable_playlist_switch else "disabled"
        self.options_frame_widget.playlist_switch.configure(state=switch_state)
        self.path_frame_widget.enable()

    def _enter_idle_state(self):
        """Enters the idle state (ready for a new operation)."""
        print("UI_Interface: Entering idle state.")
        self._enable_main_controls(enable_playlist_switch=True) # Enable everything
        self.bottom_controls_widget.disable_download(button_text="Download") # Disable download
        self.bottom_controls_widget.hide_cancel_button() # Hide cancel
        self.dynamic_area_label.configure(text="") # Clear dynamic label

        # Ensure playlist selector is hidden and reset
        self.playlist_selector_widget.grid_remove()
        self.playlist_selector_widget.reset()

        self.fetched_info = None # Clear fetched info
        self.status_label.configure(text="Enter URL and click Fetch Info.", text_color="gray") # Default status
        self.progress_bar.set(0) # Reset progress bar
        self.current_operation = None # No active operation
        # Reset playlist switch to default ON state
        self.options_frame_widget.set_playlist_mode(True)
        self._last_toggled_playlist_mode = True

    def _enter_fetching_state(self):
        """Enters the state while fetching information."""
        print("UI_Interface: Entering fetching state.")
        self.top_frame_widget.disable_fetch(button_text="Fetching...") # Disable fetch
        self.options_frame_widget.disable() # Disable options
        self.path_frame_widget.disable() # Disable path
        self.bottom_controls_widget.disable_download() # Disable download
        self.bottom_controls_widget.show_cancel_button() # Show cancel
        self.status_label.configure(text="Fetching information...", text_color="orange") # Update status
        self.progress_bar.set(0) # Start progress at 0

    def _enter_downloading_state(self):
        """Enters the state during download/processing."""
        print("UI_Interface: Entering downloading state.")
        self.top_frame_widget.disable_fetch() # Disable all input/controls
        self.options_frame_widget.disable()
        self.path_frame_widget.disable()
        self.playlist_selector_widget.disable() # Disable playlist selector

        self.bottom_controls_widget.disable_download(button_text="Downloading...") # Change download button text/state
        self.bottom_controls_widget.show_cancel_button() # Show cancel button

    def _display_playlist_view(self):
        """Sets up and displays the playlist selection view."""
        playlist_title = self.fetched_info.get("title", "Untitled Playlist")
        total_items = len(self.fetched_info.get("entries", []))
        self.dynamic_area_label.configure(text=f"Playlist: {playlist_title} ({total_items} items total)")

        # Show, populate, and enable the playlist selector
        self.playlist_selector_widget.populate_items(self.fetched_info.get("entries"))
        self.playlist_selector_widget.enable()
        # Grid it into the dynamic area
        self.playlist_selector_widget.grid(row=4, column=0, padx=20, pady=(5, 10), sticky="nsew") # Dynamic row
        print("UI_Interface: Playlist frame gridded.")

    def _enter_info_fetched_state(self):
        """Enters the state after information has been successfully fetched."""
        if not self.fetched_info:
            print("Error: _enter_info_fetched_state called without fetched_info.")
            self._enter_idle_state()
            # update_status method is in UICallbackHandlerMixin, but accessible via self
            self.update_status("Error: Failed to process fetched information.")
            return

        is_actually_playlist = isinstance(self.fetched_info.get("entries"), list)

        # Enable main controls (playlist switch might be disabled if not a real playlist)
        self._enable_main_controls(enable_playlist_switch=is_actually_playlist)

        # Determine if playlist view should be shown
        should_show_playlist_view = (
            self.options_frame_widget.get_playlist_mode() and is_actually_playlist
        )

        print(
            f"UI_Interface: Entering info fetched state. Actual playlist: {is_actually_playlist}, "
            f"Switch ON: {self.options_frame_widget.get_playlist_mode()}, "
            f"Show Playlist View: {should_show_playlist_view}"
        )

        self.bottom_controls_widget.hide_cancel_button() # Hide cancel

        # Enable download button only if a valid path is selected
        save_path = self.path_frame_widget.get_path()
        if save_path and os.path.isdir(save_path):
             self.bottom_controls_widget.enable_download(button_text="Download Selection")
        else:
             self.bottom_controls_widget.disable_download(button_text="Select Save Location")

        # Show/hide the dynamic area content (playlist selector or video title)
        if should_show_playlist_view:
            self._display_playlist_view() # Use the renamed helper method
        else:
            # If not in playlist mode or not an actual playlist
            video_title = self.fetched_info.get("title", "Untitled Video")
            self.dynamic_area_label.configure(text=f"Video: {video_title}")

            # Ensure playlist selector is hidden
            self.playlist_selector_widget.grid_remove()

            # If it IS a playlist but the switch is OFF, ensure the switch is re-enabled
            if is_actually_playlist:
                self.options_frame_widget.playlist_switch.configure(state="normal")

        # Force UI update to reflect changes immediately
        self.update_idletasks()