# -- ملف لمكون إطار خيارات التحميل العامة --
# Purpose: UI component for the general download options frame (format and playlist switch).

import customtkinter as ctk

class OptionsControlFrame(ctk.CTkFrame):
    """إطار يحتوي على اختيار الصيغة العامة ومفتاح وضع قائمة التشغيل."""
    """Frame containing the general format selection and the playlist mode switch."""

    def __init__(self, master, toggle_playlist_command, **kwargs):
        """
        تهيئة الإطار.
        Initializes the frame.

        Args:
            master: الويدجت الأب. Parent widget.
            toggle_playlist_command (callable): الدالة التي تُستدعى عند تغيير مفتاح القائمة. Function called when playlist switch is toggled.
        """
        super().__init__(master, fg_color="transparent", **kwargs)
        self.toggle_playlist_command = toggle_playlist_command

        # إعداد الشبكة الداخلية Configure internal grid
        self.grid_columnconfigure(1, weight=1) # عمود الكومبوبوكس يتمدد Combobox column expands
        self.grid_columnconfigure(3, weight=0) # عمود المفتاح لا يتمدد Switch column doesn't expand

        # إنشاء وعرض العناصر Create and grid the widgets
        self.format_label = ctk.CTkLabel(self, text="Default Format:")
        self.format_label.grid(row=0, column=0, padx=(0,5), pady=5, sticky="w")

        self.format_combobox = ctk.CTkComboBox(self, values=["Video (mp4, Best)", "Audio (mp3)"], width=180)
        self.format_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.format_combobox.set("Video (mp4, Best)") # القيمة الافتراضية Default value

        self.playlist_label = ctk.CTkLabel(self, text="Is Playlist?")
        self.playlist_label.grid(row=0, column=2, padx=(20, 5), pady=5, sticky="e")

        self.playlist_switch_var = ctk.StringVar(value="off") # متغير لتتبع حالة المفتاح Variable to track switch state
        self.playlist_switch = ctk.CTkSwitch(self, text="", variable=self.playlist_switch_var,
                                              onvalue="on", offvalue="off",
                                              command=self.toggle_playlist_command) # ربط الأمر Connect command
        self.playlist_switch.grid(row=0, column=3, padx=5, pady=5, sticky="w")

    def get_format_choice(self):
        """تُرجع قيمة الصيغة العامة المختارة."""
        """Returns the selected general format choice."""
        return self.format_combobox.get()

    def get_playlist_mode(self):
        """تُرجع `True` إذا كان وضع القائمة مفعلًا، وإلا `False`."""
        """Returns `True` if playlist mode is enabled, otherwise `False`."""
        return self.playlist_switch_var.get() == "on"

    def set_playlist_mode(self, is_on):
        """تحدد حالة مفتاح وضع القائمة."""
        """Sets the state of the playlist mode switch."""
        self.playlist_switch_var.set("on" if is_on else "off")

    def enable(self):
        """تمكين عناصر التحكم."""
        """Enables the controls."""
        self.format_combobox.configure(state="normal")
        self.playlist_switch.configure(state="normal")

    def disable(self):
        """تعطيل عناصر التحكم."""
        """Disables the controls."""
        self.format_combobox.configure(state="disabled")
        self.playlist_switch.configure(state="disabled")