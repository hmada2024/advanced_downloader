# -- ملف نقطة الدخول الرئيسي لتشغيل التطبيق --
# Purpose: Main entry point script to run the application.

import customtkinter as ctk

# استيراد الكلاسات الرئيسية من حزمة src الجديدة
# Import the main classes from the new src package
from src.ui_interface import UserInterface  # <-- تم التعديل: استخدام src.
from src.logic_handler import LogicHandler  # <-- تم التعديل: استخدام src.
import sys
import os

# Optional High DPI handling (Uncomment if needed)
# try:
#     from ctypes import windll, byref, sizeof, c_int
# except ImportError:
#     pass # Ignore if not on Windows or ctypes not available

# def set_high_dpi_awareness():
#     """Attempts to set high DPI awareness for the application."""
#     try:
#         # PROCESS_SYSTEM_DPI_AWARE = 1, PROCESS_PER_MONITOR_DPI_AWARE = 2
#         PROCESS_PER_MONITOR_DPI_AWARE_V2 = 2
#         # Earlier Windows versions might only support 1 (System Aware)
#         # Windows 10 Creators Update (1703) added support for 2 (Per-Monitor v2)
#         windll.shcore.SetProcessDpiAwareness(PROCESS_PER_MONITOR_DPI_AWARE_V2)
#         print("High DPI awareness set (Per-Monitor v2).")
#         return True
#     except AttributeError:
#         # Function doesn't exist (older Windows or non-Windows)
#         print("Could not set Per-Monitor v2 DPI awareness (likely older Windows or not Windows).")
#         try:
#             # Try setting system DPI awareness instead
#             windll.user32.SetProcessDPIAware()
#             print("High DPI awareness set (System Aware).")
#             return True
#         except AttributeError:
#             print("Could not set System DPI awareness.")
#             return False
#     except Exception as e:
#         print(f"An error occurred while setting DPI awareness: {e}")
#         return False

# نقطة البداية عند تشغيل السكربت مباشرة
# Entry point when script is run directly
if __name__ == "__main__":
    # # --- Uncomment the line below to enable High DPI ---
    # set_high_dpi_awareness()

    # التعامل مع مسار التطبيق عند التجميع بـ PyInstaller
    # Handle application path when bundled with PyInstaller
    if getattr(sys, "frozen", False):
        application_path = os.path.dirname(sys.executable)
    else:
        try:
            application_path = os.path.dirname(
                os.path.abspath(__file__)
            )  # Use abspath for reliability
        except NameError:
            application_path = os.getcwd()

    # --- إنشاء مكونات التطبيق --- Instantiate application components ---
    # إنشاء نسخة الواجهة أولاً Create UI instance first
    app = UserInterface(logic_handler=None)

    # إنشاء نسخة المنطق وتمرير دوال الكول باك من الواجهة إليه Create logic instance and pass UI callbacks
    logic = LogicHandler(
        status_callback=app.update_status,
        progress_callback=app.update_progress,
        finished_callback=app.on_task_finished,
        info_success_callback=app.on_info_success,
        info_error_callback=app.on_info_error,
    )

    # ربط نسخة المنطق بنسخة الواجهة Link logic instance to UI instance
    app.logic = logic

    # --- تشغيل حلقة الأحداث الرئيسية للواجهة --- Run the main UI event loop ---
    app.mainloop()
