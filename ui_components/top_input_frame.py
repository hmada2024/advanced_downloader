# -- ملف لمكون إطار الإدخال العلوي (الرابط وزر الجلب) --
# Purpose: UI component for the top input frame (URL entry and Fetch button).

import customtkinter as ctk

class TopInputFrame(ctk.CTkFrame):
    """إطار يحتوي على حقل إدخال الرابط وزر جلب المعلومات."""
    """Frame containing the URL input field and the Fetch Info button."""

    def __init__(self, master, fetch_command, **kwargs):
        """
        تهيئة الإطار.
        Initializes the frame.

        Args:
            master: الويدجت الأب (النافذة الرئيسية). Parent widget (main window).
            fetch_command (callable): الدالة التي تُستدعى عند الضغط على زر الجلب. Function to call when Fetch button is clicked.
        """
        super().__init__(master, fg_color="transparent", **kwargs)
        self.fetch_command = fetch_command

        # إعداد الشبكة الداخلية للإطار Configure internal grid
        self.grid_columnconfigure(1, weight=1) # السماح لحقل الإدخال بالتمدد Allow entry field to expand

        # إنشاء وعرض العناصر Create and grid the widgets
        self.url_label = ctk.CTkLabel(self, text="Video/Playlist URL:")
        self.url_label.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="w")

        self.url_entry = ctk.CTkEntry(self, placeholder_text="Enter URL and click Fetch Info", width=350)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        self.fetch_button = ctk.CTkButton(self, text="Fetch Info", width=100, command=self.fetch_command)
        self.fetch_button.grid(row=0, column=2, padx=(5, 0), pady=5, sticky="e")

    def get_url(self):
        """تُرجع النص الموجود في حقل إدخال الرابط."""
        """Returns the text currently in the URL entry field."""
        return self.url_entry.get()

    def set_url(self, url_text):
        """تحدد النص في حقل إدخال الرابط."""
        """Sets the text in the URL entry field."""
        self.url_entry.delete(0, 'end')
        self.url_entry.insert(0, url_text)

    def enable_fetch(self):
        """تمكين حقل الإدخال وزر الجلب."""
        """Enables the entry field and fetch button."""
        self.url_entry.configure(state="normal")
        self.fetch_button.configure(state="normal", text="Fetch Info")

    def disable_fetch(self, button_text="Fetching..."):
        """تعطيل حقل الإدخال وزر الجلب وتغيير نص الزر."""
        """Disables the entry field and fetch button, changing the button text."""
        self.url_entry.configure(state="disabled")
        self.fetch_button.configure(state="disabled", text=button_text)