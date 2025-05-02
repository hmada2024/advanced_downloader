import customtkinter as ctk
from ui import AppInterface
from logic import DownloaderLogic
import sys
import os

# Optional High DPI handling (Uncomment if needed)
# import platform
# if platform.system() == "Windows":
#     try:
#         import ctypes
#         ctypes.windll.shcore.SetProcessDpiAwareness(1)
#     except Exception as e:
#         print(f"Could not set DPI awareness: {e}")

if __name__ == "__main__":
    # Handle path for PyInstaller bundling
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        try:
             application_path = os.path.dirname(__file__)
        except NameError: # Fallback for environments where __file__ is not defined
             application_path = os.getcwd()


    # --- Instantiate components ---
    # Pass None for logic first
    app = AppInterface(logic_handler=None)

    # Create logic, passing UI callback methods
    logic = DownloaderLogic(
        status_callback=app.update_status,
        progress_callback=app.update_progress,
        finished_callback=app.on_task_finished, # Renamed/repurposed callback
        info_success_callback=app.on_info_success,
        info_error_callback=app.on_info_error
    )

    # Link logic handler back to the app instance
    app.logic = logic

    # --- Run the application ---
    app.mainloop()