import customtkinter as ctk
from ui import AppInterface
from logic import DownloaderLogic
import sys
import os

# --- Handling High DPI displays (Optional but recommended) ---
# Uncomment the following lines if you experience scaling issues on high DPI monitors
# import platform
# if platform.system() == "Windows":
#     try:
#         import ctypes
#         ctypes.windll.shcore.SetProcessDpiAwareness(1) # Try 1 or 2
#     except Exception as e:
#         print(f"Could not set DPI awareness: {e}")

if __name__ == "__main__":
    # Ensure the script directory is in the path (important for PyInstaller)
    # This helps find the ffmpeg_bin folder relative to the executable
    if getattr(sys, 'frozen', False):
        # If running as a bundled app (PyInstaller)
        application_path = os.path.dirname(sys.executable)
    else:
        # If running as a normal script
        application_path = os.path.dirname(__file__)

    # --- Instantiate components ---
    # Create the main application window/UI instance first
    app = AppInterface(logic_handler=None) # Pass None initially

    # Create the logic handler, passing the UI's update methods
    logic = DownloaderLogic(
        status_callback=app.update_status,
        progress_callback=app.update_progress,
        finished_callback=app.on_download_finished
    )

    # Now link the logic handler back to the app instance
    app.logic = logic

    # --- Run the application ---
    app.mainloop()