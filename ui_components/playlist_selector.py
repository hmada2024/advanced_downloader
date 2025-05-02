# -- ملف لمكون الواجهة الخاص بعرض واختيار عناصر قائمة التشغيل --

import customtkinter as ctk

# كلاس يمثل الإطار القابل للتمرير لعناصر القائمة
class PlaylistSelector(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        """
        تهيئة إطار اختيار عناصر القائمة.
        Args:
            master: الويدجت الأب.
        """
        # استدعاء مُهيئ الأب مع تسمية للإطار
        super().__init__(master, label_text="Playlist Items", **kwargs)

        self.checkboxes_data = [] # قائمة لتخزين بيانات مربعات الاختيار (widget, var, index)

        # إطار داخلي لأزرار التحكم (Select All / Deselect All)
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(fill="x", pady=5, padx=5) # وضع الإطار في الأعلى داخل الإطار القابل للتمرير

        # إنشاء أزرار التحكم ووضعها داخل إطار الأزرار
        self.select_all_button = ctk.CTkButton(self.button_frame, text="Select All", command=self.select_all)
        self.select_all_button.pack(side="left", padx=(0,5))
        self.deselect_all_button = ctk.CTkButton(self.button_frame, text="Deselect All", command=self.deselect_all)
        self.deselect_all_button.pack(side="left", padx=5)

        # تعطيل الأزرار مبدئيًا
        self.disable()

    def clear_items(self):
        """تدمير مربعات الاختيار القديمة ومسح القائمة الداخلية."""
        for cb, var, index in self.checkboxes_data:
            if cb and isinstance(cb, (ctk.CTkCheckBox, ctk.CTkLabel)): # التحقق من النوع
                try:
                    cb.destroy() # تدمير الويدجت
                except Exception as e:
                    print(f"Error destroying playlist item widget: {e}")
        self.checkboxes_data = [] # مسح القائمة المنطقية
        # التأكد من تعطيل الأزرار عند عدم وجود عناصر
        self.disable()

    def populate_items(self, entries):
        """تملأ الإطار بمربعات الاختيار لعناصر القائمة."""
        self.clear_items() # مسح العناصر القديمة أولاً

        if not entries:
            # عرض رسالة إذا كانت القائمة فارغة
            no_items_label = ctk.CTkLabel(self, text="No videos found in playlist.")
            no_items_label.pack(pady=5, padx=5, anchor="w")
            # تخزين مؤقت للرسالة ليتم مسحها لاحقًا
            self.checkboxes_data.append((no_items_label, None, -1))
            self.disable() # تعطيل الأزرار
            return

        # تمكين الأزرار طالما هناك عناصر
        self.enable()

        print(f"PlaylistSelector: Populating with {len(entries)} items.") # للدييباج
        # إنشاء مربع اختيار لكل عنصر في القائمة
        for index, entry in enumerate(entries):
            if not entry: continue # تجاوز العناصر الفارغة المحتملة

            video_index = entry.get('playlist_index') or (index + 1) # استخدام الفهرس من yt-dlp إن وجد
            title = entry.get('title') or f'Video {video_index} (Untitled)' # الحصول على العنوان

            # قص العناوين الطويلة للعرض
            max_len = 70
            display_title = (title[:max_len] + '...') if len(title) > max_len else title

            # إنشاء متغير وقيمة لمربع الاختيار
            var = ctk.StringVar(value="on") # تحديد الكل افتراضيًا
            cb = ctk.CTkCheckBox(self, text=f"{video_index}. {display_title}",
                                 variable=var, onvalue="on", offvalue="off")
            cb.pack(anchor="w", padx=10, pady=(2, 2), fill="x") # وضع مربع الاختيار داخل الإطار القابل للتمرير

            # تخزين مربع الاختيار ومتغيره وفهرسه في القائمة الداخلية
            self.checkboxes_data.append((cb, var, video_index))
        print("PlaylistSelector: Finished packing checkboxes.") # للدييباج

    def select_all(self):
        """تحديد جميع مربعات الاختيار."""
        for cb, var, index in self.checkboxes_data:
            if var and isinstance(var, ctk.StringVar):
                var.set("on") # تغيير قيمة المتغير المرتبط

    def deselect_all(self):
        """إلغاء تحديد جميع مربعات الاختيار."""
        for cb, var, index in self.checkboxes_data:
            if var and isinstance(var, ctk.StringVar):
                var.set("off") # تغيير قيمة المتغير المرتبط

    def get_selected_items_string(self):
        """
        تُرجع سلسلة نصية تحتوي على فهارس العناصر المحددة (مفصولة بفواصل).
        Returns a comma-separated string of selected item indices.
        """
        selected_indices = []
        for cb, var, index in self.checkboxes_data:
            # التأكد من أنه مربع اختيار صالح وتم تحديده
            if cb and isinstance(cb, ctk.CTkCheckBox) and var and var.get() == "on":
                selected_indices.append(index) # إضافة الفهرس المخزن

        if not selected_indices:
            return None # لم يتم تحديد أي عنصر

        # إرجاع الفهارس مفصولة بفواصل (بعد ترتيبها)
        return ",".join(map(str, sorted(selected_indices)))

    def reset(self):
        """إعادة تعيين المكون (مسح العناصر وتعطيل الأزرار)."""
        self.clear_items()

    def enable(self):
        """تمكين أزرار التحكم."""
        self.select_all_button.configure(state="normal")
        self.deselect_all_button.configure(state="normal")
        # يمكن إضافة تمكين لمربعات الاختيار هنا إذا تم تعطيلها سابقًا

    def disable(self):
        """تعطيل أزرار التحكم ومربعات الاختيار."""
        self.select_all_button.configure(state="disabled")
        self.deselect_all_button.configure(state="disabled")
        # تعطيل مربعات الاختيار الموجودة
        for cb, var, index in self.checkboxes_data:
            if cb and isinstance(cb, ctk.CTkCheckBox):
                cb.configure(state="disabled")