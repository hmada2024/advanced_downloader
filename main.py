# -- ملف نقطة الدخول الرئيسي لتشغيل التطبيق --
# Purpose: Main entry point script to run the application.

import customtkinter as ctk
# استيراد الكلاسات الرئيسية من ملفاتها الجديدة
# Import the main classes from their new files
from ui_interface import UserInterface   # <-- التأكد من اسم الملف والكلاس Correct filename and class
from logic_handler import LogicHandler   # <-- التأكد من اسم الملف والكلاس Correct filename and class
import sys
import os

# Optional High DPI handling (Uncomment if needed)
# ... (الكود كما هو) ...

# نقطة البداية عند تشغيل السكربت مباشرة
# Entry point when script is run directly
if __name__ == "__main__":
    # التعامل مع مسار التطبيق عند التجميع بـ PyInstaller
    # Handle application path when bundled with PyInstaller
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        try:
             application_path = os.path.dirname(__file__)
        except NameError:
             application_path = os.getcwd()

    # --- إنشاء مكونات التطبيق --- Instantiate application components ---
    # إنشاء نسخة الواجهة أولاً Create UI instance first
    app = UserInterface(logic_handler=None) # <-- استخدام الكلاس الصحيح Use correct class

    # إنشاء نسخة المنطق وتمرير دوال الكول باك من الواجهة إليه Create logic instance and pass UI callbacks
    logic = LogicHandler(                  # <-- استخدام الكلاس الصحيح Use correct class
        status_callback=app.update_status,
        progress_callback=app.update_progress,
        finished_callback=app.on_task_finished,
        info_success_callback=app.on_info_success,
        info_error_callback=app.on_info_error
    )

    # ربط نسخة المنطق بنسخة الواجهة Link logic instance to UI instance
    app.logic = logic

    # --- تشغيل حلقة الأحداث الرئيسية للواجهة --- Run the main UI event loop ---
    app.mainloop()