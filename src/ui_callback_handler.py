# src/ui_callback_handler.py
# -- Mixin class for handling callbacks from the logic layer --

import customtkinter as ctk
from tkinter import messagebox

# Note: This class assumes it's mixed into a class that has attributes like:
# self.status_label, self.progress_bar, self.fetched_info, self.current_operation,
# self.options_frame_widget, self.path_frame_widget,
# and methods from UIStateManagerMixin like _enter_idle_state, _enter_info_fetched_state

class UICallbackHandlerMixin:
    """Mixin class containing methods for handling callbacks from LogicHandler."""

    def update_status(self, message):
        """Updates the status label text and color (thread-safe)."""
        def _update():
            # Determine text color based on keywords
            color = "gray" # Default
            msg_lower = message.lower()
            # Adjust justification based on line breaks
            justify_val = "left" if "\n" in message else "center"

            if "error" in msg_lower: color = "red"
            elif "warning" in msg_lower: color = "orange"
            elif "cancel" in msg_lower: color = "orange"
            elif "complete" in msg_lower or "finished" in msg_lower or "success" in msg_lower: color = "green"
            elif "downloading" in msg_lower or "processing" in msg_lower or "fetching" in msg_lower or "starting" in msg_lower: color = "blue"

            # Update text, color, and justification
            self.status_label.configure(text=message, text_color=color, justify=justify_val)
        # Use after to ensure execution in the main UI thread
        self.after(1, _update)

    def update_progress(self, value):
        """Updates the progress bar value (thread-safe)."""
        value = max(0.0, min(1.0, value)) # Clamp value between 0 and 1
        # Use after to ensure execution in the main UI thread
        self.after(1, lambda: self.progress_bar.set(value))

    def on_info_success(self, info_dict):
        """Callback executed when info fetch succeeds (thread-safe)."""
        def _update():
            self.fetched_info = info_dict # Store fetched info
            if not info_dict:
                # Treat empty info as an error
                self.on_info_error("Received empty or invalid info.")
                return

            is_actually_playlist = isinstance(info_dict.get("entries"), list)

            # Restore the playlist switch state from before fetching,
            # or disable it if it's not actually a playlist.
            if is_actually_playlist:
                print(f"Info success: It's a playlist. Restoring switch state to: {self._last_toggled_playlist_mode}")
                self.options_frame_widget.set_playlist_mode(self._last_toggled_playlist_mode)
            else:
                print("Info success: It's not a playlist. Ensuring switch is OFF and disabled.")
                self.options_frame_widget.set_playlist_mode(False)
                self.options_frame_widget.playlist_switch.configure(state="disabled") # Also disable it

            # Enter the state to display the fetched info
            # _enter_info_fetched_state is in UIStateManagerMixin, accessible via self
            self._enter_info_fetched_state()

            # Update status message
            status_msg = "Info fetched successfully. Ready to download."
            if self.options_frame_widget.get_playlist_mode() and is_actually_playlist:
                status_msg = "Playlist info fetched. Select items and download."
            self.update_status(status_msg)

        # Use after(0) for immediate execution in the next event loop cycle
        self.after(0, _update)

    def on_info_error(self, error_message):
        """Callback executed when info fetch fails (thread-safe)."""
        def _update():
            print(f"UI_Interface: Info error callback received: {error_message}")
            messagebox.showerror("Information Fetch Error", f"Could not fetch information:\n{error_message}")
            # Return to idle state on error
            # _enter_idle_state is in UIStateManagerMixin, accessible via self
            self._enter_idle_state()
        self.after(0, _update)

    def on_task_finished(self):
        """Callback executed when any background task finishes (thread-safe)."""
        def _process_finish():
            operation_type = self.current_operation
            # Get the final status text and color directly from the label widget
            final_status_text = self.status_label.cget("text")
            final_status_color = self.status_label.cget("text_color") # Assuming text_color reflects state

            print(f"UI_Interface: Task finished notification (Type: '{operation_type}'). Final status: '{final_status_text}' (Color: {final_status_color})")

            # Determine if the task was cancelled or resulted in an error
            was_cancelled = "cancel" in final_status_text.lower()
            # Check color OR text for error indication
            was_error = (final_status_color == "red") or ("error" in final_status_text.lower())

            # Logic to transition UI state based on outcome
            if was_cancelled:
                print("UI: Operation was cancelled. Restoring previous state if info exists.")
                if self.fetched_info:
                    # If info exists, go back to showing it
                    self._enter_info_fetched_state()
                    self.update_status("Operation Cancelled.")
                else:
                    # If no info (fetch cancelled), go back to idle
                    self._enter_idle_state()
                    self.update_status("Info Fetch Cancelled.")
            elif was_error:
                print("UI: Operation failed with error. Restoring previous state if info exists.")
                if self.fetched_info:
                    # If info exists, go back to showing it (error status already set)
                    self._enter_info_fetched_state()
                else:
                    # If fetch failed, go back to idle (error status already set)
                    self._enter_idle_state()
            elif operation_type == "fetch" and not was_error and not was_cancelled:
                # Successful fetch is handled by on_info_success, state is already updated
                print("UI: Info fetch finished successfully (handled by on_info_success). State already updated.")
            elif operation_type == "download" and not was_error and not was_cancelled:
                # Successful download
                print("UI: Download finished successfully. Resetting to idle state.")
                save_path = self.path_frame_widget.get_path() # Get path for message box
                messagebox.showinfo("Download Complete", f"Download finished successfully!\nFile(s) saved in:\n{save_path}")
                # Return to idle state after successful download
                self._enter_idle_state()
            else:
                # Unexpected state or unknown operation type
                print(f"UI: Task finished with unknown state or type. Resetting. (Op: {operation_type}, Status: {final_status_text})")
                self._enter_idle_state()

            # Reset the current operation tracker
            self.current_operation = None

        # Use a small delay to ensure status label is updated before processing finish
        self.after(50, _process_finish)