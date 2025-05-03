# -- ملف لمكون إطار اختيار مسار الحفظ --
# Purpose: UI component for the save path selection frame.

import customtkinter as ctk
from tkinter import filedialog # استيراد مربع حوار الملفات Import file dialog

class PathSelectionFrame(ctk.CTkFrame):
    """إطار يحتوي على حقل عرض مسار الحفظ وزر التصفح."""
    """Frame containing the save path display field and the Browse button."""

    def __init__(self, master, browse_callback, **kwargs):
        """
        تهيئة الإطار.
        Initializes the frame.

        Args:
            master: الويدجت الأب. Parent widget.
            browse_callback (callable): الدالة التي تُستدعى عند الضغط على زر التصفح. Function to call when Browse button is clicked.
                                       (ملاحظة: هذه الدالة يجب أن تُنفذ منطق التصفح الفعلي وتحديث المسار).
                                       (Note: This callback should implement the actual browsing logic and path update).
        """
        super().__init__(master, fg_color="transparent", **kwargs)
        self.browse_callback = browse_callback

        # إعداد الشبكة الداخلية Configure internal grid
        self.grid_columnconfigure(1, weight=1) # السماح لحقل المسار بالتمدد Allow path entry to expand

        # إنشاء وعرض العناصر Create and grid the widgets
        self.path_label = ctk.CTkLabel(self, text="Save Location:")
        self.path_label.grid(row=0, column=0, padx=(0,5), pady=5, sticky="w")

        self.path_entry = ctk.CTkEntry(self, placeholder_text="Select download folder", state="readonly") # للقراءة فقط Read-only
        self.path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.browse_button = ctk.CTkButton(self, text="Browse", width=80, command=self.browse_callback) # ربط أمر الزر Connect button command
        self.browse_button.grid(row=0, column=2, padx=(5, 0), pady=5, sticky="e")

    def get_path(self):
        """تُرجع مسار الحفظ الحالي."""
        """Returns the current save path."""
        return self.path_entry.get()

    def set_path(self, path_text):
        """
        تحدث النص في حقل المسار (تجعله قابلاً للكتابة مؤقتًا).
        Updates the text in the path field (makes it writable temporarily).
        """
        current_state = self.path_entry.cget("state")
        self.path_entry.configure(state="normal") # تمكين للكتابة Enable writing
        self.path_entry.delete(0, "end")
        self.path_entry.insert(0, path_text)
        self.path_entry.configure(state=current_state) # إعادة الحالة الأصلية (عادة readonly) Restore original state (usually readonly)

    def enable(self):
        """تمكين زر التصفح."""
        """Enables the browse button."""
        # حقل الإدخال يبقى للقراءة فقط عادة The entry usually stays read-only
        self.browse_button.configure(state="normal")

    def disable(self):
        """تعطيل زر التصفح."""
        """Disables the browse button."""
        self.browse_button.configure(state="disabled")