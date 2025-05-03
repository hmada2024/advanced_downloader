# src/logic_utils.py
# -- ملف يحتوي على دوال مساعدة عامة للمنطق --
# Purpose: Contains general helper functions for the logic part.

import sys
from pathlib import Path
import re
import yt_dlp # Needed for find_ffmpeg -> yt_dlp.utils.ffmpeg_executable

def find_ffmpeg():
    """
    يبحث عن الملف التنفيذي لـ FFmpeg.
    Looks for the FFmpeg executable.
    الأولوية للملف المضمن في مجلد ffmpeg_bin، ثم لمتغيرات البيئة PATH.
    Priority is given to the bundled executable in ffmpeg_bin, then the system PATH.

    Returns:
        str | None: مسار FFmpeg إذا وجد، وإلا None. Path to ffmpeg if found, else None.
    """
    try:
        # تحديد المسار الأساسي سواء كان التطبيق مجمداً أو يعمل كسكربت
        # Determine the base path whether the app is frozen or running as a script
        if getattr(sys, "frozen", False):
            base_path = Path(sys.executable).parent # المسار عند التجميد Path when frozen
        else:
            # المسار نسبة لملف logic_utils.py الحالي (src/logic_utils.py)
            # Path relative to the current logic_utils.py file (src/logic_utils.py)
            # نحتاج للصعود مستويين للوصول لمجلد المشروع الرئيسي
            # We need to go up two levels to reach the main project directory
            base_path = Path(__file__).resolve().parent.parent
    except Exception as e:
        print(f"Error determining base path: {e}")
        base_path = Path(".") # مسار احتياطي Fallback path

    # البحث عن النسخة المضمنة Check for bundled version
    bundled_path = base_path / "ffmpeg_bin" / "ffmpeg.exe"
    if bundled_path.is_file():
        print(f"Found bundled ffmpeg: {bundled_path}")
        return str(bundled_path)
    else:
        # البحث في متغيرات البيئة PATH Check the system PATH
        print(f"Bundled ffmpeg not found at '{bundled_path}'. Checking PATH...")
        try:
            # استخدام دالة yt-dlp للبحث في PATH Use yt-dlp's function to check PATH
            ffmpeg_path_in_env = yt_dlp.utils.ffmpeg_executable()
            if ffmpeg_path_in_env and Path(ffmpeg_path_in_env).is_file():
                print(f"Using ffmpeg from PATH: {ffmpeg_path_in_env}")
                return ffmpeg_path_in_env
        except Exception as e:
            # قد يحدث خطأ إذا لم يتمكن yt-dlp من تنفيذ الأوامر An error might occur if yt-dlp can't execute commands
            print(f"Error checking for ffmpeg in PATH: {e}")

        # إذا لم يتم العثور عليه في أي مكان If not found anywhere
        print("Warning: ffmpeg not found in bundle or system PATH.")
        return None

def clean_filename(filename):
    """
    ينظف اسم الملف بإزالة الأحرف غير الصالحة واستبدال أخرى.
    Cleans a filename by removing invalid characters and replacing others.

    Args:
        filename (str | None): اسم الملف الأصلي. The original filename.

    Returns:
        str: اسم الملف المنظف. The cleaned filename.
             Returns "downloaded_file" if the cleaned name is empty.
    """
    if not filename:
        return "downloaded_file" # قيمة افتراضية إذا كان الإدخال فارغًا Default if input is empty

    # إزالة الأحرف غير المسموح بها في ويندوز Remove disallowed characters in Windows
    cleaned = re.sub(r'[\\/*?:"<>|]', "", filename)
    # استبدال النقطتين بـ " - " (شائع في العناوين) Replace colon with " - " (common in titles)
    cleaned = cleaned.replace(":", " -")
    # استبدال المسافات المتعددة بمسافة واحدة Replace multiple spaces with a single space
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    # إزالة النقاط أو المسافات الزائدة في النهاية Remove trailing dots or spaces
    cleaned = cleaned.rstrip(". ")

    # التأكد من عدم إرجاع اسم فارغ Ensure not returning an empty name
    return cleaned or "downloaded_file"