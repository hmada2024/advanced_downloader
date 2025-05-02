# -- ملف لتعريف الاستثناءات (الأخطاء) المخصصة للتطبيق --

class DownloadCancelled(Exception):
    """
    استثناء مخصص يُطلق عندما يقوم المستخدم بإلغاء عملية التحميل أو جلب المعلومات.
    Custom exception raised when the user cancels a download or info fetch operation.
    """
    pass