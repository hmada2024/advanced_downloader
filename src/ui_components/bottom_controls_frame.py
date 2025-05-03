# -- ملف لمكون إطار أزرار التحكم السفلية (تحميل وإلغاء) --
# Purpose: UI component for the bottom control buttons frame (Download and Cancel).

import customtkinter as ctk

class BottomControlsFrame(ctk.CTkFrame):
    """إطار يحتوي على أزرار التحميل والإلغاء."""
    """Frame containing the Download and Cancel buttons."""

    def __init__(self, master, download_command, cancel_command, **kwargs):
        """
        تهيئة الإطار.
        Initializes the frame.

        Args:
            master: الويدجت الأب. Parent widget.
            download_command (callable): الدالة عند الضغط على "Download". Function for "Download" click.
            cancel_command (callable): الدالة عند الضغط على "Cancel". Function for "Cancel" click.
        """
        super().__init__(master, fg_color="transparent", **kwargs)
        self.download_command = download_command
        self.cancel_command = cancel_command

        # إعداد الشبكة الداخلية Configure internal grid
        self.grid_columnconfigure(0, weight=1) # زر التحميل يتمدد Download button expands
        self.grid_columnconfigure(1, weight=0) # زر الإلغاء لا يتمدد Cancel button doesn't expand

        # إنشاء الأزرار Create buttons
        self.download_button = ctk.CTkButton(self, text="Download", command=self.download_command, state="disabled")
        # وضع زر التحميل مبدئيًا ليأخذ كامل العرض Place download button initially spanning both columns
        self.download_button.grid(row=0, column=0, columnspan=2, padx=(0, 5), pady=5, sticky="ew")

        self.cancel_button = ctk.CTkButton(self, text="Cancel", command=self.cancel_command, state="disabled", fg_color="red", hover_color="darkred")
        # زر الإلغاء لا يوضع في الشبكة مبدئيًا Cancel button is not gridded initially

    def show_cancel_button(self):
        """إظهار زر الإلغاء وتعديل عرض زر التحميل."""
        """Shows the cancel button and adjusts the download button's span."""
        self.download_button.grid_configure(columnspan=1) # تقليل عرض زر التحميل Reduce download button span
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="e") # وضع زر الإلغاء Place cancel button
        self.cancel_button.configure(state="normal") # تمكين زر الإلغاء Enable cancel button

    def hide_cancel_button(self):
        """إخفاء زر الإلغاء وإعادة عرض زر التحميل ليأخذ كامل العرض."""
        """Hides the cancel button and makes the download button span full width again."""
        self.cancel_button.grid_remove() # إزالة زر الإلغاء من الشبكة Remove cancel button from grid
        self.cancel_button.configure(state="disabled") # تعطيله Disable it
        self.download_button.grid_configure(columnspan=2) # إعادة زر التحميل للعرض الكامل Restore download button to full span

    def enable_download(self, button_text="Download Selection"):
        """تمكين زر التحميل وتحديد نصه."""
        """Enables the download button and sets its text."""
        self.download_button.configure(state="normal", text=button_text)

    def disable_download(self, button_text="Download"):
        """تعطيل زر التحميل وتحديد نصه."""
        """Disables the download button and sets its text."""
        self.download_button.configure(state="disabled", text=button_text)

    def set_download_button_text(self, text):
        """تحديد نص زر التحميل."""
        """Sets the text of the download button."""
        self.download_button.configure(text=text)