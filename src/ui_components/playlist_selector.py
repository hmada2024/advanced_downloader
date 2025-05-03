# -- ملف لمكون الواجهة الخاص بعرض واختيار عناصر قائمة التشغيل --
# Purpose: UI component for displaying and selecting playlist items.

import customtkinter as ctk

# كلاس يمثل الإطار القابل للتمرير لعناصر القائمة
# Class representing the scrollable frame for playlist items
class PlaylistSelector(ctk.CTkScrollableFrame):
    def __init__(self, master, **kwargs):
        """
        تهيئة إطار اختيار عناصر القائمة.
        Initializes the playlist item selection frame.
        Args:
            master: الويدجت الأب. Parent widget.
        """
        # استدعاء مُهيئ الأب مع تسمية للإطار
        # Call parent initializer with a label for the frame
        super().__init__(master, label_text="Playlist Items", **kwargs)

        self.checkboxes_data = [] # قائمة لتخزين بيانات مربعات الاختيار (widget, var, index) List to store checkbox data (widget, var, index)

        # إطار داخلي لأزرار التحكم (Select All / Deselect All)
        # Internal frame for control buttons (Select All / Deselect All)
        self.button_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.button_frame.pack(fill="x", pady=5, padx=5) # وضع الإطار في الأعلى Place the frame at the top

        # إنشاء أزرار التحكم ووضعها داخل إطار الأزرار
        # Create control buttons and place them within the button frame
        self.select_all_button = ctk.CTkButton(self.button_frame, text="Select All", command=self.select_all)
        self.select_all_button.pack(side="left", padx=(0,5))
        self.deselect_all_button = ctk.CTkButton(self.button_frame, text="Deselect All", command=self.deselect_all)
        self.deselect_all_button.pack(side="left", padx=5)

        # تعطيل الأزرار مبدئيًا Disable buttons initially
        self.disable()

    def clear_items(self):
        """
        تدمير مربعات الاختيار القديمة ومسح القائمة الداخلية.
        Destroys old checkboxes and clears the internal list.
        """
        for cb, var, index in self.checkboxes_data:
            if cb and isinstance(cb, (ctk.CTkCheckBox, ctk.CTkLabel)): # التحقق من النوع Check type
                try:
                    cb.destroy() # تدمير الويدجت Destroy widget
                except Exception as e:
                    print(f"Error destroying playlist item widget: {e}")
        self.checkboxes_data = [] # مسح القائمة المنطقية Clear the logical list
        # التأكد من تعطيل الأزرار عند عدم وجود عناصر Ensure buttons are disabled when no items
        self.disable()

    def populate_items(self, entries):
        """
        تملأ الإطار بمربعات الاختيار لعناصر القائمة.
        Populates the frame with checkboxes for playlist items.
        """
        self.clear_items() # مسح العناصر القديمة أولاً Clear old items first

        if not entries:
            # عرض رسالة إذا كانت القائمة فارغة Display message if list is empty
            no_items_label = ctk.CTkLabel(self, text="No videos found in playlist.")
            no_items_label.pack(pady=5, padx=5, anchor="w")
            # تخزين مؤقت للرسالة ليتم مسحها لاحقًا Temporarily store the label to be cleared later
            self.checkboxes_data.append((no_items_label, None, -1))
            self.disable() # تعطيل الأزرار Disable buttons
            return

        # تمكين الأزرار طالما هناك عناصر Enable buttons as long as there are items
        self.enable()

        print(f"PlaylistSelector: Populating with {len(entries)} items.") # للدييباج For debugging
        # إنشاء مربع اختيار لكل عنصر في القائمة Create a checkbox for each item in the list
        for index, entry in enumerate(entries):
            if not entry: continue # تجاوز العناصر الفارغة المحتملة Skip potential null entries

            video_index = entry.get('playlist_index') or (index + 1) # استخدام الفهرس من yt-dlp إن وجد Use index from yt-dlp if available
            title = entry.get('title') or f'Video {video_index} (Untitled)' # الحصول على العنوان Get title

            # قص العناوين الطويلة للعرض Truncate long titles for display
            max_len = 70
            display_title = (title[:max_len] + '...') if len(title) > max_len else title

            # إنشاء متغير وقيمة لمربع الاختيار Create variable and value for checkbox
            var = ctk.StringVar(value="on") # تحديد الكل افتراضيًا Select all by default
            cb = ctk.CTkCheckBox(self, text=f"{video_index}. {display_title}",
                                 variable=var, onvalue="on", offvalue="off")
            cb.pack(anchor="w", padx=10, pady=(2, 2), fill="x") # وضع مربع الاختيار Place checkbox

            # تخزين مربع الاختيار ومتغيره وفهرسه في القائمة الداخلية Store checkbox, variable, and index in internal list
            self.checkboxes_data.append((cb, var, video_index))
        print("PlaylistSelector: Finished packing checkboxes.") # للدييباج For debugging

    def select_all(self):
        """
        تحديد جميع مربعات الاختيار.
        Selects all checkboxes.
        """
        for cb, var, index in self.checkboxes_data:
            if var and isinstance(var, ctk.StringVar):
                var.set("on") # تغيير قيمة المتغير المرتبط Change associated variable value

    def deselect_all(self):
        """
        إلغاء تحديد جميع مربعات الاختيار.
        Deselects all checkboxes.
        """
        for cb, var, index in self.checkboxes_data:
            if var and isinstance(var, ctk.StringVar):
                var.set("off") # تغيير قيمة المتغير المرتبط Change associated variable value

    def get_selected_items_string(self):
        """
        تُرجع سلسلة نصية تحتوي على فهارس العناصر المحددة (مفصولة بفواصل).
        Returns a comma-separated string of selected item indices.
        """
        selected_indices = []
        for cb, var, index in self.checkboxes_data:
            # التأكد من أنه مربع اختيار صالح وتم تحديده Check if it's a valid checkbox and selected
            if cb and isinstance(cb, ctk.CTkCheckBox) and var and var.get() == "on":
                selected_indices.append(index) # إضافة الفهرس المخزن Add the stored index

        if not selected_indices:
            return None # لم يتم تحديد أي عنصر No item selected

        # إرجاع الفهارس مفصولة بفواصل (بعد ترتيبها) Return indices separated by commas (after sorting)
        return ",".join(map(str, sorted(selected_indices)))

    def reset(self):
        """
        إعادة تعيين المكون (مسح العناصر وتعطيل الأزرار).
        Resets the component (clears items and disables buttons).
        """
        self.clear_items()

    def enable(self):
        """
        تمكين أزرار التحكم ومربعات الاختيار.
        Enables control buttons and checkboxes.
        """
        self.select_all_button.configure(state="normal")
        self.deselect_all_button.configure(state="normal")
        # تمكين مربعات الاختيار الموجودة Enable existing checkboxes
        for cb, var, index in self.checkboxes_data:
             if cb and isinstance(cb, ctk.CTkCheckBox):
                cb.configure(state="normal")

    def disable(self):
        """
        تعطيل أزرار التحكم ومربعات الاختيار.
        Disables control buttons and checkboxes.
        """
        self.select_all_button.configure(state="disabled")
        self.deselect_all_button.configure(state="disabled")
        # تعطيل مربعات الاختيار الموجودة Disable existing checkboxes
        for cb, var, index in self.checkboxes_data:
            if cb and isinstance(cb, ctk.CTkCheckBox):
                cb.configure(state="disabled")