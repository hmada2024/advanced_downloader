# -- ملف لتعريف الاستثناءات (الأخطاء) المخصصة للتطبيق --
# Purpose: Defines custom exceptions used across the application.

class DownloadCancelled(Exception):
    """
    استثناء مخصص يُطلق عندما يقوم المستخدم بإلغاء عملية التحميل أو جلب المعلومات.
    Custom exception raised when the user cancels a download or info fetch operation.
    """
    pass

# يمكنك إضافة استثناءات أخرى هنا إذا احتجت لاحقًا
# You can add other custom exceptions here if needed later.