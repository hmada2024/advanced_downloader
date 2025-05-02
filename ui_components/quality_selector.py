# -- ملف لمكون الواجهة الخاص باختيار جودة الفيديو المفرد --

import customtkinter as ctk
import humanize # لمكتبة تحويل حجم الملفات لصيغة مقروءة

# كلاس يمثل إطار اختيار الجودة
class QualitySelector(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        """
        تهيئة إطار اختيار الجودة.
        Args:
            master: الويدجت الأب (النافذة الرئيسية عادة).
        """
        super().__init__(master, fg_color="transparent", **kwargs)

        self.selected_format_id = None # لتخزين معرف الجودة المختارة
        self.format_map = {} # قاموس لربط النص المعروض بمعرف الجودة

        # إعداد الشبكة الداخلية للإطار
        self.grid_columnconfigure(0, weight=1) # السماح للكومبوبوكس بالتمدد

        # إنشاء عناصر الواجهة داخل الإطار
        self.quality_label = ctk.CTkLabel(self, text="Available Qualities:")
        self.quality_label.grid(row=0, column=0, padx=5, pady=(5,0), sticky="w")

        self.quality_combobox = ctk.CTkComboBox(
            self,
            values=["Fetch info first"],
            state="disabled",
            command=self._on_quality_selected_internal # استدعاء دالة داخلية عند التغيير
        )
        self.quality_combobox.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

    def populate_options(self, formats):
        """تملأ القائمة المنسدلة بخيارات الجودة المتاحة."""
        self.quality_combobox.configure(state="normal")
        self.quality_combobox.set("Processing...")

        if not formats:
            self.quality_combobox.configure(values=["No formats available"], state="disabled")
            self.quality_combobox.set("No formats available")
            self.format_map = {}
            self.selected_format_id = None
            return

        options = ["Default (Use General Format)"] # خيار استخدام الإعداد العام
        format_map = {"Default (Use General Format)": None}

        # تصفية الصيغ الصالحة فقط
        valid_formats = [f for f in formats if f and f.get('url') and f.get('format_id')]

        # ترتيب الصيغ (الأولوية لـ mp4/webm، ثم الدقة، ثم حجم الملف)
        valid_formats.sort(key=lambda f: (
            f.get('ext') not in ('mp4', 'webm'),
            f.get('ext') != 'mp4',
            -(f.get('height') or 0),
            -(f.get('filesize') or f.get('filesize_approx') or 0)
            ), reverse=False)

        # إنشاء نص وصفي لكل صيغة
        for f in valid_formats:
            # ... (نفس منطق إنشاء النص الوصفي من ui.py الأصلي) ...
            desc = []
            fid = f.get('format_id')
            res = f.get('resolution')
            ext = f.get('ext', '?')
            vcodec = f.get('vcodec', 'none').split('.')[0]
            acodec = f.get('acodec', 'none').split('.')[0]
            dynamic_range = f.get('dynamic_range', '')
            fps = f.get('fps')
            size_bytes = f.get('filesize') or f.get('filesize_approx')
            size_readable = f" ({humanize.naturalsize(size_bytes, binary=True)})" if size_bytes else ""
            note = f.get('format_note', '')

            if vcodec != 'none' and res:
                desc.append(f"{res} {ext}")
                if fps: desc.append(f"{fps}fps")
                if dynamic_range: desc.append(dynamic_range)
                if note and note != res: desc.append(f"[{note}]")
                desc.append(f"(V:{vcodec}")
                if acodec != 'none': desc.append(f"+A:{acodec})")
                else: desc.append(")")
            elif acodec != 'none':
                 desc.append(f"Audio {ext}")
                 if note: desc.append(f"[{note}]")
                 desc.append(f"(A:{acodec})")
            else:
                desc.append(f"Format {fid} ({ext})")
                if note: desc.append(f"[{note}]")

            display_text = f"{' '.join(desc)}{size_readable}"
            options.append(display_text)
            format_map[display_text] = fid # ربط النص بالمعرف

        # تحديث القائمة المنسدلة
        self.quality_combobox.configure(values=options)
        self.quality_combobox.set(options[0]) # اختيار الخيار الافتراضي
        self.format_map = format_map # تخزين قاموس الربط
        self.selected_format_id = None # إعادة تعيين التحديد

    def _on_quality_selected_internal(self, choice):
        """دالة داخلية تُستدعى عند اختيار عنصر من القائمة."""
        self.selected_format_id = self.format_map.get(choice)
        print(f"QualitySelector - Selected Quality: {choice}, Format ID: {self.selected_format_id}")
        # يمكن إضافة استدعاء لدالة خارجية (callback) هنا إذا احتاجت الواجهة الرئيسية لمعرفة التغيير فورًا

    def get_selected_id(self):
        """تُرجع معرف الجودة المحدد حاليًا."""
        return self.selected_format_id

    def reset(self):
        """إعادة تعيين المكون لحالته الأولية."""
        self.quality_combobox.configure(values=["Fetch info first"], state="disabled")
        self.quality_combobox.set("Fetch info first")
        self.selected_format_id = None
        self.format_map = {}

    def enable(self):
        """تمكين القائمة المنسدلة (إذا كانت تحتوي على خيارات)."""
        if self.quality_combobox.cget("values") != ["Fetch info first"]:
             self.quality_combobox.configure(state="normal")

    def disable(self):
        """تعطيل القائمة المنسدلة."""
        self.quality_combobox.configure(state="disabled")