# -- ملف كلاس الواجهة الرسومية الرئيسي للتطبيق --

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
# لا حاجة لـ humanize هنا الآن، سيتم استخدامه داخل QualitySelector

# استيراد مكونات الواجهة المنفصلة
from ui_components.quality_selector import QualitySelector
from ui_components.playlist_selector import PlaylistSelector

# الكلاس الرئيسي للواجهة، يرث من ctk.CTk (النافذة الرئيسية)
class UserInterface(ctk.CTk):
    def __init__(self, logic_handler):
        """
        تهيئة الواجهة الرسومية الرئيسية.
        Args:
            logic_handler: نسخة من كلاس LogicHandler للتواصل مع المنطق.
        """
        super().__init__()

        self.logic = logic_handler # تخزين نسخة معالج المنطق
        self.fetched_info = None   # لتخزين المعلومات المجوبة عن الرابط
        self.current_operation = None # لتتبع نوع العملية الحالية ('fetch' أو 'download')

        # --- إعداد النافذة ---
        self.title("Advanced Downloader") # تغيير العنوان قليلاً
        self.geometry("750x650") # تحديد الأبعاد
        ctk.set_appearance_mode("System") # الوضع الداكن/الفاتح حسب النظام
        ctk.set_default_color_theme("blue") # تحديد الثيم اللوني

        # --- إعداد تخطيط الشبكة (Grid Layout) للنافذة ---
        self.grid_columnconfigure(1, weight=1) # العمود الثاني (للإدخالات) يتمدد
        self.grid_rowconfigure(6, weight=1) # الصف السابع (لقائمة التشغيل) يتمدد أكثر

        # --- إنشاء عناصر الواجهة الثابتة ---

        # الإطار العلوي (الرابط وزر الجلب)
        self.top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.top_frame.grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="ew")
        self.top_frame.grid_columnconfigure(1, weight=1)
        self.url_label = ctk.CTkLabel(self.top_frame, text="Video/Playlist URL:")
        self.url_label.grid(row=0, column=0, padx=(0, 5), pady=5)
        self.url_entry = ctk.CTkEntry(self.top_frame, placeholder_text="Enter URL and click Fetch Info", width=350)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.fetch_button = ctk.CTkButton(self.top_frame, text="Fetch Info", width=100, command=self.fetch_video_info)
        self.fetch_button.grid(row=0, column=2, padx=(5, 0), pady=5)

        # إطار الخيارات (الصيغة العامة ومفتاح القائمة)
        self.options_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.options_frame.grid(row=1, column=0, columnspan=3, padx=15, pady=5, sticky="ew")
        self.options_frame.grid_columnconfigure(1, weight=1)
        self.options_frame.grid_columnconfigure(3, weight=0)
        self.format_label = ctk.CTkLabel(self.options_frame, text="Default Format:")
        self.format_label.grid(row=0, column=0, padx=(0,5), pady=5, sticky="w")
        self.format_combobox = ctk.CTkComboBox(self.options_frame, values=["Video (mp4, Best)", "Audio (mp3)"], width=180)
        self.format_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.format_combobox.set("Video (mp4, Best)")
        self.playlist_label = ctk.CTkLabel(self.options_frame, text="Is Playlist?")
        self.playlist_label.grid(row=0, column=2, padx=(20, 5), pady=5, sticky="e")
        self.playlist_switch_var = ctk.StringVar(value="off")
        self.playlist_switch = ctk.CTkSwitch(self.options_frame, text="", variable=self.playlist_switch_var,
                                              onvalue="on", offvalue="off", command=self.toggle_playlist_mode)
        self.playlist_switch.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        # إطار مسار الحفظ
        self.path_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.path_frame.grid(row=2, column=0, columnspan=3, padx=15, pady=5, sticky="ew")
        self.path_frame.grid_columnconfigure(1, weight=1)
        self.path_label = ctk.CTkLabel(self.path_frame, text="Save Location:")
        self.path_label.grid(row=0, column=0, padx=(0,5), pady=5, sticky="w")
        self.path_entry = ctk.CTkEntry(self.path_frame, placeholder_text="Select download folder", state="readonly")
        self.path_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        self.browse_button = ctk.CTkButton(self.path_frame, text="Browse", width=80, command=self.browse_path)
        self.browse_button.grid(row=0, column=2, padx=(5, 0), pady=5)

        # عنوان للمنطقة الديناميكية (الجودة أو القائمة)
        self.dynamic_area_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(weight="bold"))
        self.dynamic_area_label.grid(row=3, column=0, columnspan=3, padx=20, pady=(10,0), sticky="w")

        # --- إنشاء نسخ من مكونات الواجهة المنفصلة ---
        # لا يتم وضعها في الشبكة الآن، سيتم ذلك ديناميكيًا

        # مكون اختيار الجودة (يرث من CTkFrame)
        self.quality_selector_widget = QualitySelector(self)
        # لا نستخدم grid() هنا، سيتم إدارته لاحقًا

        # مكون اختيار القائمة (يرث من CTkScrollableFrame)
        self.playlist_selector_widget = PlaylistSelector(self)
        # لا نستخدم grid() هنا، سيتم إدارته لاحقًا

        # --- عناصر الواجهة السفلية (التحميل، الإلغاء، التقدم، الحالة) ---
        self.bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_frame.grid(row=7, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="ew")
        self.bottom_frame.grid_columnconfigure(0, weight=1)
        self.bottom_frame.grid_columnconfigure(1, weight=0)
        self.download_button = ctk.CTkButton(self.bottom_frame, text="Download", command=self.start_download_ui, state="disabled")
        self.download_button.grid(row=0, column=0, padx=(0, 5), pady=5, sticky="ew")
        self.cancel_button = ctk.CTkButton(self.bottom_frame, text="Cancel", command=self.cancel_operation_ui, state="disabled", fg_color="red", hover_color="darkred")
        # زر الإلغاء يدار ديناميكيًا (grid/grid_remove)
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=8, column=0, columnspan=3, padx=20, pady=(0, 5), sticky="ew")
        self.progress_bar.set(0)
        self.status_label = ctk.CTkLabel(self, text="Enter URL and click Fetch Info.", text_color="gray")
        self.status_label.grid(row=9, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="ew")

        # --- إعداد الحالة الأولية للواجهة ---
        self._enter_idle_state()


    # --- دوال إدارة حالة الواجهة ---

    def _enter_idle_state(self):
        """إعادة تعيين الواجهة للحالة الأولية (جاهزة لرابط جديد)."""
        self.url_entry.configure(state="normal")
        self.fetch_button.configure(state="normal", text="Fetch Info")
        self.format_combobox.configure(state="normal")
        self.playlist_switch.configure(state="normal")
        self.browse_button.configure(state="normal")
        self.download_button.configure(state="disabled", text="Download")
        self.cancel_button.grid_remove() # إخفاء زر الإلغاء
        self.cancel_button.configure(state="disabled")
        self.download_button.grid_configure(columnspan=2) # زر التحميل يأخذ كامل العرض

        # إخفاء وإعادة تعيين المكونات الديناميكية
        self.dynamic_area_label.configure(text="")
        self.quality_selector_widget.grid_remove() # إخفاء إطار الجودة
        self.quality_selector_widget.reset()       # إعادة تعيينه
        self.playlist_selector_widget.grid_remove() # إخفاء إطار القائمة
        self.playlist_selector_widget.reset()       # إعادة تعيينه

        self.fetched_info = None
        self.status_label.configure(text="Enter URL and click Fetch Info.", text_color="gray")
        self.progress_bar.set(0)
        # self.current_operation = None # يمكن إضافتها هنا أيضًا للتأكيد

    def _enter_fetching_state(self):
        """حالة الواجهة أثناء جلب المعلومات."""
        self.url_entry.configure(state="disabled")
        self.fetch_button.configure(state="disabled", text="Fetching...")
        self.download_button.configure(state="disabled")
        self.cancel_button.configure(state="normal") # تمكين زر الإلغاء
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="e") # إظهار زر الإلغاء
        self.download_button.grid_configure(columnspan=1) # تقليل عرض زر التحميل
        self.status_label.configure(text="Fetching information...", text_color="orange")
        self.progress_bar.set(0)

    def _enter_info_fetched_state(self, is_playlist_mode):
        """حالة الواجهة بعد جلب المعلومات بنجاح."""
        print(f"UI_Interface: Entering info fetched state. Playlist mode: {is_playlist_mode}")
        self.fetch_button.configure(state="normal", text="Fetch Info") # السماح بإعادة الجلب
        self.url_entry.configure(state="normal")

        # تمكين/تعطيل زر التحميل بناءً على وجود مسار حفظ
        if self.path_entry.get():
            self.download_button.configure(state="normal", text="Download Selection")
        else:
            self.download_button.configure(state="disabled", text="Select Save Location")

        self.cancel_button.grid_remove() # إخفاء زر الإلغاء
        self.cancel_button.configure(state="disabled")
        self.download_button.grid_configure(columnspan=2) # زر التحميل يأخذ كامل العرض

        # إظهار القسم الديناميكي المناسب (جودة أو قائمة)
        if is_playlist_mode and self.fetched_info and 'entries' in self.fetched_info:
            # وضع قائمة التشغيل
            playlist_title = self.fetched_info.get('title', 'Untitled Playlist')
            self.dynamic_area_label.configure(text=f"Playlist: {playlist_title}")
            # استخدام مكون القائمة لتعبئة العناصر
            self.playlist_selector_widget.populate_items(self.fetched_info.get('entries'))
            self.quality_selector_widget.grid_remove() # إخفاء إطار الجودة
            # إظهار إطار القائمة في الشبكة (الصف 6)
            self.playlist_selector_widget.grid(row=6, column=0, columnspan=3, padx=20, pady=10, sticky="nsew")
            print("UI_Interface: Playlist frame gridded.")
        elif self.fetched_info:
            # وضع الفيديو المفرد
            video_title = self.fetched_info.get('title', 'Untitled Video')
            self.dynamic_area_label.configure(text=f"Video: {video_title}")
            # استخدام مكون الجودة لتعبئة الخيارات
            self.quality_selector_widget.populate_options(self.fetched_info.get('formats', []))
            self.playlist_selector_widget.grid_remove() # إخفاء إطار القائمة
            # إظهار إطار الجودة في الشبكة (الصف 5)
            self.quality_selector_widget.grid(row=5, column=0, columnspan=3, padx=15, pady=5, sticky="ew")
            print("UI_Interface: Quality frame gridded.")
        else:
             # حالة خطأ غير متوقعة
             self.dynamic_area_label.configure(text="Error: Invalid information received.")
             self.quality_selector_widget.grid_remove()
             self.playlist_selector_widget.grid_remove()

        # تحديث الواجهة فورًا لإظهار التغييرات
        self.update_idletasks()

    def _enter_downloading_state(self):
        """حالة الواجهة أثناء التحميل الفعلي."""
        self.fetch_button.configure(state="disabled")
        self.url_entry.configure(state="disabled")
        self.format_combobox.configure(state="disabled")
        self.playlist_switch.configure(state="disabled")
        self.browse_button.configure(state="disabled")
        self.download_button.configure(state="disabled", text="Downloading...")
        self.cancel_button.configure(state="normal") # تمكين زر الإلغاء
        self.cancel_button.grid(row=0, column=1, padx=(5, 0), pady=5, sticky="e") # إظهار زر الإلغاء
        self.download_button.grid_configure(columnspan=1) # تقليل عرض زر التحميل

        # تعطيل المكونات الديناميكية
        self.quality_selector_widget.disable()
        self.playlist_selector_widget.disable()


    # --- معالجات الأحداث ومنطق الواجهة ---

    def browse_path(self):
        """فتح مربع حوار لاختيار مجلد الحفظ."""
        directory = filedialog.askdirectory()
        if directory:
            self.path_entry.configure(state="normal")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, directory)
            self.path_entry.configure(state="readonly")
            # تمكين زر التحميل إذا كانت الشروط الأخرى متحققة
            if self.fetched_info and self.download_button.cget("state") == "disabled":
                 is_playlist_mode = self.playlist_switch_var.get() == "on"
                 is_actually_playlist = self.fetched_info and 'entries' in self.fetched_info
                 if (not (is_playlist_mode and is_actually_playlist)) or \
                    (is_playlist_mode and is_actually_playlist): # يكفي أن تكون قائمة ليتم التمكين
                      self.download_button.configure(state="normal", text="Download Selection")

    def fetch_video_info(self):
        """بدء عملية جلب المعلومات للرابط المدخل."""
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return

        # إعادة تعيين الأجزاء الديناميكية قبل البدء
        self._enter_idle_state() # العودة للحالة الأولية أولاً
        self.url_entry.delete(0,'end') # مسح الإدخال
        self.url_entry.insert(0,url) # إعادة إدراج الرابط (لتجنب إعادة كتابته)

        self.current_operation = 'fetch' # تحديد نوع العملية
        self._enter_fetching_state() # الدخول لحالة الجلب
        self.logic.start_info_fetch(url) # استدعاء دالة المنطق

    def toggle_playlist_mode(self):
        """تحديث الواجهة عند تغيير مفتاح قائمة التشغيل (بعد جلب المعلومات)."""
        if self.fetched_info:
             is_playlist_mode = self.playlist_switch_var.get() == "on"
             is_actually_playlist = self.fetched_info and 'entries' in self.fetched_info
             if is_playlist_mode and not is_actually_playlist:
                  print("Cannot enter playlist mode: Fetched info has no 'entries'.")
                  self.playlist_switch_var.set("off")
                  self._enter_info_fetched_state(False) # عرض كفيديو مفرد
             else:
                  self._enter_info_fetched_state(is_playlist_mode) # عرض حسب الوضع المطلوب

    # --- دوال تفويض للمكونات (لم تعد هناك حاجة لمعظم الدوال القديمة هنا) ---
    # تم نقل populate_quality_options, on_quality_selected إلى QualitySelector
    # تم نقل clear_playlist_checkboxes, populate_playlist_items, playlist_select_all,
    # playlist_deselect_all, get_selected_playlist_items_string إلى PlaylistSelector

    def start_download_ui(self):
        """بدء عملية التحميل بناءً على التحديدات الحالية."""
        url = self.url_entry.get()
        save_path = self.path_entry.get()
        format_choice = self.format_combobox.get() # الصيغة العامة
        is_playlist = self.playlist_switch_var.get() == "on"

        # --- التحقق من المدخلات الأساسية ---
        if not url: messagebox.showerror("Error", "URL is missing."); return
        if not save_path: messagebox.showerror("Error", "Save location is missing."); return
        if not os.path.isdir(save_path): messagebox.showerror("Error", "Save location is not a valid directory."); return
        if not self.fetched_info: messagebox.showerror("Error", "Please fetch info before downloading."); return

        # --- الحصول على التحديدات من المكونات ---
        quality_format_id = None
        playlist_items_string = None
        is_actually_playlist = self.fetched_info and 'entries' in self.fetched_info

        if is_playlist and is_actually_playlist:
            # الحصول على العناصر المحددة من مكون القائمة
            playlist_items_string = self.playlist_selector_widget.get_selected_items_string()
            if not playlist_items_string:
                 messagebox.showwarning("Warning", "No playlist items selected for download.")
                 return
            quality_format_id = None # استخدام الصيغة العامة للقائمة
        else:
            # الحصول على الجودة المحددة من مكون الجودة
            quality_format_id = self.quality_selector_widget.get_selected_id()

        # --- بدء التحميل ---
        self.current_operation = 'download' # تحديد نوع العملية
        self._enter_downloading_state() # الدخول لحالة التحميل
        # استدعاء دالة المنطق مع كل البيانات اللازمة
        self.logic.start_download(url, save_path, format_choice, quality_format_id, is_playlist, playlist_items_string)

    def cancel_operation_ui(self):
        """استدعاء دالة الإلغاء في المنطق عند الضغط على الزر."""
        print("UI_Interface: Cancel button pressed.")
        self.logic.cancel_operation()


    # --- دوال الكول باك (Callbacks) التي يستدعيها المنطق ---

    def update_status(self, message):
        """تحديث نص الحالة (يتم استدعاؤها من المنطق)."""
        def _update():
            # ... (نفس منطق تلوين النص) ...
            color = "gray"; msg_lower = message.lower()
            if "error" in msg_lower: color = "red"
            elif "warning" in msg_lower: color = "orange"
            elif "cancel" in msg_lower: color = "orange"
            elif "complete" in msg_lower or "finished" in msg_lower or "success" in msg_lower : color = "green"
            elif "downloading" in msg_lower or "processing" in msg_lower or "fetching" in msg_lower: color="blue"
            self.status_label.configure(text=message, text_color=color)
        self.after(1, _update) # استخدام تأخير بسيط

    def update_progress(self, value):
        """تحديث شريط التقدم (يتم استدعاؤها من المنطق)."""
        value = max(0.0, min(1.0, value)) # ضمان القيمة بين 0 و 1
        self.after(1, lambda: self.progress_bar.set(value)) # استخدام تأخير بسيط

    def on_info_success(self, info_dict):
        """معالجة الواجهة عند نجاح جلب المعلومات (يتم استدعاؤها من المنطق)."""
        def _update():
            self.fetched_info = info_dict # تخزين المعلومات
            is_playlist_mode_requested = self.playlist_switch_var.get() == "on"
            is_actually_playlist = info_dict is not None and 'entries' in info_dict and isinstance(info_dict['entries'], list)

            # تحديد وضع العرض النهائي (قائمة أو مفرد)
            final_playlist_mode = False
            if is_playlist_mode_requested and is_actually_playlist:
                final_playlist_mode = True
                self.playlist_switch.configure(state="normal")
            elif is_playlist_mode_requested and not is_actually_playlist:
                 print("Fetched info is not a playlist, turning switch off.")
                 self.playlist_switch_var.set("off")
                 final_playlist_mode = False
            else: # الحالات الأخرى (طلب مفرد أو ليس قائمة أصلاً)
                 final_playlist_mode = False
                 if is_actually_playlist: # إذا كانت قائمة ولكن طلب مفرد، ابق المفتاح متاحًا
                     self.playlist_switch.configure(state="normal")

            # الدخول للحالة المناسبة لعرض المعلومات
            self._enter_info_fetched_state(final_playlist_mode)
        self.after(0, _update) # تحديث فوري للواجهة

    def on_info_error(self, error_message):
        """معالجة الواجهة عند فشل جلب المعلومات (يتم استدعاؤها من المنطق)."""
        def _update():
            messagebox.showerror("Info Fetch Error", error_message)
            self._enter_idle_state() # العودة للحالة الأولية عند الخطأ
            self.current_operation = None # مسح نوع العملية
        self.after(0, _update)

    def on_task_finished(self):
        """
        معالجة الواجهة عند انتهاء أي مهمة في الخلفية (جلب أو تحميل).
        (يتم استدعاؤها من المنطق).
        """
        def _process_finish():
            operation_type = self.current_operation
            self.current_operation = None # إعادة تعيين نوع العملية

            final_status = self.status_label.cget("text").lower()
            print(f"UI_Interface: Task finished (Type: '{operation_type}'), final status: {final_status}")

            # التعامل مع الأخطاء أو الإلغاء أولاً
            if "error" in final_status or "cancel" in final_status:
                print("UI_Interface: Error or Cancel detected, resetting UI.")
                if self.fetched_info:
                    # محاولة استعادة حالة عرض المعلومات إن وجدت
                    is_playlist_mode = self.playlist_switch_var.get() == "on"
                    is_actually_playlist = 'entries' in self.fetched_info and isinstance(self.fetched_info['entries'], list)
                    final_playlist_mode = is_playlist_mode and is_actually_playlist
                    # إعادة تطبيق حالة عرض المعلومات لتمكين الأزرار الصحيحة
                    self._enter_info_fetched_state(final_playlist_mode)
                else:
                    # العودة للحالة الأولية تمامًا إذا لم يتم جلب معلومات مطلقًا
                    self._enter_idle_state()
            # إذا لم يكن خطأ أو إلغاء، تحقق من نوع العملية
            elif operation_type == 'fetch':
                # نجاح جلب المعلومات: الواجهة يجب أن تكون بالفعل في الحالة الصحيحة
                # بفضل on_info_success. نضمن فقط أن الأزرار ممكنة.
                print("UI_Interface: Fetch finished successfully. Re-applying info_fetched state for button enablement.")
                if self.fetched_info:
                     is_playlist_mode = self.playlist_switch_var.get() == "on"
                     is_actually_playlist = 'entries' in self.fetched_info and isinstance(self.fetched_info['entries'], list)
                     final_playlist_mode = is_playlist_mode and is_actually_playlist
                     self._enter_info_fetched_state(final_playlist_mode) # إعادة تطبيق الحالة
                else:
                     print("WARN: Fetch finished but fetched_info is missing? Resetting.")
                     self._enter_idle_state() # حالة غير متوقعة، العودة للأولية
            elif operation_type == 'download':
                 # نجاح التحميل: العودة للحالة الأولية استعدادًا لعملية جديدة
                 print("UI_Interface: Download finished successfully. Resetting to idle state.")
                 self._enter_idle_state()
            else:
                 # عملية غير معروفة أو انتهاء غير متوقع
                 print(f"UI_Interface: Unknown or no operation type ('{operation_type}'). Resetting.")
                 self._enter_idle_state()

        # استخدام تأخير بسيط للسماح للمستخدم برؤية رسالة الحالة النهائية
        self.after(10, _process_finish)