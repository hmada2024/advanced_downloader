# -- ملف نقطة الدخول الرئيسي لتشغيل التطبيق --

import customtkinter as ctk
# استيراد الكلاسات الجديدة من الملفات الجديدة
from ui_interface import UserInterface   # <--- تغيير هنا
from logic_handler import LogicHandler   # <--- تغيير هنا
import sys
import os

# Optional High DPI handling (Uncomment if needed)
# ... (الكود كما هو) ...

# نقطة البداية عند تشغيل السكربت مباشرة
if __name__ == "__main__":
    # التعامل مع مسار التطبيق عند التجميع بـ PyInstaller
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        try:
             application_path = os.path.dirname(__file__)
        except NameError:
             application_path = os.getcwd()

    # --- إنشاء مكونات التطبيق ---
    # إنشاء نسخة الواجهة أولاً
    app = UserInterface(logic_handler=None) # <--- تغيير هنا (اسم الكلاس)

    # إنشاء نسخة المنطق وتمرير دوال الكول باك من الواجهة إليه
    logic = LogicHandler(                  # <--- تغيير هنا (اسم الكلاس)
        status_callback=app.update_status,
        progress_callback=app.update_progress,
        finished_callback=app.on_task_finished,
        info_success_callback=app.on_info_success,
        info_error_callback=app.on_info_error
    )

    # ربط نسخة المنطق بنسخة الواجهة (حتى تتمكن الواجهة من استدعاء دوال المنطق)
    app.logic = logic

    # --- تشغيل حلقة الأحداث الرئيسية للواجهة ---
    app.mainloop()