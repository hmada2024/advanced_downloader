# -- ملف كلاس الواجهة الرسومية الرئيسي للتطبيق والمنسق بين المكونات --
# Purpose: Main application UI window class and coordinator between components.

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os

# استيراد مكونات الواجهة المنفصلة
# Import the separate UI components
from ui_components.top_input_frame import TopInputFrame
from ui_components.options_control_frame import OptionsControlFrame
from ui_components.path_selection_frame import PathSelectionFrame
from ui_components.bottom_controls_frame import BottomControlsFrame
from ui_components.quality_selector import QualitySelector
from ui_components.playlist_selector import PlaylistSelector

# الكلاس الرئيسي للواجهة، يرث من ctk.CTk (النافذة الرئيسية)
# Main UI class, inherits from ctk.CTk (the main window)
class UserInterface(ctk.CTk):
    def __init__(self, logic_handler):
        """
        تهيئة الواجهة الرسومية الرئيسية.
        Initializes the main graphical user interface.
        Args:
            logic_handler: نسخة من كلاس LogicHandler للتواصل مع المنطق. Instance of LogicHandler for logic communication.
        """
        super().__init__()

        self.logic = logic_handler # تخزين نسخة معالج المنطق Store logic handler instance
        self.fetched_info = None   # لتخزين المعلومات المجوبة عن الرابط To store fetched info about the URL
        self.current_operation = None # لتتبع نوع العملية الحالية ('fetch' أو 'download') To track current operation ('fetch' or 'download')

        # --- إعداد النافذة --- Window Setup ---
        self.title("Advanced Downloader") # تغيير العنوان Title change
        # -- START Phase 1 Change: Increase window size --
        self.geometry("850x750") # زيادة الأبعاد Dimensions increased
        # -- END Phase 1 Change --
        ctk.set_appearance_mode("System") # الوضع الداكن/الفاتح حسب النظام System theme mode
        ctk.set_default_color_theme("blue") # تحديد الثيم اللوني Color theme

        # --- إعداد تخطيط الشبكة (Grid Layout) للنافذة --- Grid Layout Setup ---
        self.grid_columnconfigure(1, weight=1) # العمود الثاني يتمدد Column 1 expands
        self.grid_rowconfigure(6, weight=1) # الصف السابع (القائمة) يتمدد أكثر Row 6 (playlist) expands most

        # --- إنشاء وتنسيق مكونات الواجهة --- Create and layout UI components ---

        # 1. الإطار العلوي (الرابط والجلب) - Top Frame (URL & Fetch)
        # تمرير دالة fetch_video_info كأمر لزر الجلب Pass fetch_video_info as the command for the fetch button
        self.top_frame_widget = TopInputFrame(self, fetch_command=self.fetch_video_info)
        self.top_frame_widget.grid(row=0, column=0, columnspan=3, padx=15, pady=(15, 5), sticky="ew")

        # 2. إطار الخيارات (الصيغة والمفتاح) - Options Frame (Format & Switch)
        # تمرير دالة toggle_playlist_mode كأمر لمفتاح القائمة Pass toggle_playlist_mode as the command for the switch
        self.options_frame_widget = OptionsControlFrame(self, toggle_playlist_command=self.toggle_playlist_mode)
        self.options_frame_widget.grid(row=1, column=0, columnspan=3, padx=15, pady=5, sticky="ew")

        # 3. إطار مسار الحفظ - Path Frame
        # تمرير دالة browse_path_logic كأمر لزر التصفح Pass browse_path_logic as the command for the browse button
        self.path_frame_widget = PathSelectionFrame(self, browse_callback=self.browse_path_logic)
        self.path_frame_widget.grid(row=2, column=0, columnspan=3, padx=15, pady=5, sticky="ew")

        # 4. عنوان المنطقة الديناميكية - Dynamic Area Label
        self.dynamic_area_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(weight="bold"))
        self.dynamic_area_label.grid(row=3, column=0, columnspan=3, padx=20, pady=(10,0), sticky="w")

        # 5. مكون اختيار الجودة (يتم إظهاره/إخفاؤه ديناميكيًا) - Quality Selector (Managed dynamically)
        self.quality_selector_widget = QualitySelector(self)
        # لا يتم وضعه في الشبكة الآن Not gridded now

        # 6. مكون اختيار القائمة (يتم إظهاره/إخفاؤه ديناميكيًا) - Playlist Selector (Managed dynamically)
        self.playlist_selector_widget = PlaylistSelector(self)
        # لا يتم وضعه في الشبكة الآن Not gridded now

        # 7. الإطار السفلي (التحميل والإلغاء) - Bottom Frame (Download & Cancel)
        # تمرير دوال start_download_ui و cancel_operation_ui كأوامر للأزرار Pass callbacks for buttons
        self.bottom_controls_widget = BottomControlsFrame(
            self,
            download_command=self.start_download_ui,
            cancel_command=self.cancel_operation_ui
        )
        self.bottom_controls_widget.grid(row=7, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="ew")

        # 8. شريط التقدم - Progress Bar
        self.progress_bar = ctk.CTkProgressBar(self)
        self.progress_bar.grid(row=8, column=0, columnspan=3, padx=20, pady=(0, 5), sticky="ew")
        self.progress_bar.set(0)

        # 9. نص الحالة - Status Label
        self.status_label = ctk.CTkLabel(self, text="Enter URL and click Fetch Info.", text_color="gray")
        self.status_label.grid(row=9, column=0, columnspan=3, padx=20, pady=(0, 10), sticky="ew")

        # --- إعداد الحالة الأولية للواجهة --- Initial UI State Setup ---
        self._enter_idle_state()


    # --- دوال إدارة حالة الواجهة --- UI State Management Functions ---

    def _enter_idle_state(self):
        """إعادة تعيين الواجهة للحالة الأولية."""
        """Resets the UI to the initial state."""
        self._extracted_from__enter_info_fetched_state_4()
        self.bottom_controls_widget.disable_download(button_text="Download")
        self.bottom_controls_widget.hide_cancel_button()

        self.dynamic_area_label.configure(text="")
        self.quality_selector_widget.grid_remove() # إخفاء Hide
        self.quality_selector_widget.reset()       # إعادة تعيين Reset
        self.playlist_selector_widget.grid_remove()# إخفاء Hide
        self.playlist_selector_widget.reset()      # إعادة تعيين Reset

        self.fetched_info = None
        self.status_label.configure(text="Enter URL and click Fetch Info.", text_color="gray")
        self.progress_bar.set(0)
        self.current_operation = None # مسح نوع العملية Clear operation type

    def _enter_fetching_state(self):
        """حالة الواجهة أثناء جلب المعلومات."""
        """UI state during information fetching."""
        self.top_frame_widget.disable_fetch(button_text="Fetching...")
        # ترك الخيارات الأخرى ممكنة للسماح بتغيير رأي المستخدم Leave other options enabled? Maybe disable them? Let's disable for now.
        self.options_frame_widget.disable()
        self.path_frame_widget.disable()
        self.bottom_controls_widget.disable_download() # تأكيد تعطيل التحميل Ensure download is disabled
        self.bottom_controls_widget.show_cancel_button() # إظهار وتمكين الإلغاء Show and enable cancel
        self.status_label.configure(text="Fetching information...", text_color="orange")
        self.progress_bar.set(0)

    def _enter_info_fetched_state(self, is_playlist_mode):
        """حالة الواجهة بعد جلب المعلومات بنجاح."""
        """UI state after info fetched successfully."""
        print(f"UI_Interface: Entering info fetched state. Playlist mode: {is_playlist_mode}")
        self._extracted_from__enter_info_fetched_state_4()
        self.bottom_controls_widget.hide_cancel_button() # إخفاء الإلغاء Hide cancel

        # تمكين زر التحميل فقط إذا تم اختيار مسار حفظ
        # Enable download button only if save path is set
        if self.path_frame_widget.get_path():
            self.bottom_controls_widget.enable_download(button_text="Download Selection")
        else:
            self.bottom_controls_widget.disable_download(button_text="Select Save Location")

        # إظهار القسم الديناميكي المناسب (جودة أو قائمة) Show the appropriate dynamic section
        if is_playlist_mode and self.fetched_info and 'entries' in self.fetched_info:
            playlist_title = self.fetched_info.get('title', 'Untitled Playlist')
            self.dynamic_area_label.configure(text=f"Playlist: {playlist_title}")
            self.quality_selector_widget.grid_remove() # إخفاء الجودة Hide quality selector
            self.playlist_selector_widget.populate_items(self.fetched_info.get('entries')) # تعبئة القائمة Populate playlist
            self.playlist_selector_widget.enable() # تمكين عناصر القائمة Enable playlist items
            self.playlist_selector_widget.grid(row=6, column=0, columnspan=3, padx=20, pady=10, sticky="nsew") # إظهار القائمة Show playlist
            print("UI_Interface: Playlist frame gridded.")
        elif self.fetched_info:
            video_title = self.fetched_info.get('title', 'Untitled Video')
            self.dynamic_area_label.configure(text=f"Video: {video_title}")
            self.playlist_selector_widget.grid_remove() # إخفاء القائمة Hide playlist selector
            self.quality_selector_widget.populate_options(self.fetched_info.get('formats', [])) # تعبئة الجودة Populate quality
            self.quality_selector_widget.enable() # تمكين اختيار الجودة Enable quality selector
            self.quality_selector_widget.grid(row=5, column=0, columnspan=3, padx=15, pady=5, sticky="ew") # إظهار الجودة Show quality
            print("UI_Interface: Quality frame gridded.")
        else:
             self.dynamic_area_label.configure(text="Error: Invalid information received.")
             self.quality_selector_widget.grid_remove()
             self.playlist_selector_widget.grid_remove()

        self.update_idletasks() # فرض تحديث الواجهة Force UI update

    # TODO Rename this here and in `_enter_idle_state` and `_enter_info_fetched_state`
    def _extracted_from__enter_info_fetched_state_4(self):
        self.top_frame_widget.enable_fetch()
        self.options_frame_widget.enable()
        self.path_frame_widget.enable()

    def _enter_downloading_state(self):
        """حالة الواجهة أثناء التحميل الفعلي."""
        """UI state during active download."""
        self.top_frame_widget.disable_fetch() # تعطيل الجلب Disable fetch
        self.options_frame_widget.disable()   # تعطيل الخيارات Disable options
        self.path_frame_widget.disable()      # تعطيل التصفح Disable browse
        self.quality_selector_widget.disable()# تعطيل اختيار الجودة Disable quality selection
        self.playlist_selector_widget.disable()# تعطيل اختيار القائمة Disable playlist selection
        self.bottom_controls_widget.disable_download(button_text="Downloading...") # تعطيل زر التحميل Disable download button
        self.bottom_controls_widget.show_cancel_button() # إظهار وتمكين الإلغاء Show and enable cancel


    # --- معالجات الأحداث ومنطق الواجهة --- Event Handlers & UI Logic ---

    def browse_path_logic(self):
        """
        منطق ما يحدث عند الضغط على زر التصفح (يتم استدعاؤه بواسطة PathSelectionFrame).
        Logic for when the browse button is clicked (called by PathSelectionFrame).
        """
        # استخدام Walrus Operator لتحديد المجلد والتحقق منه في خطوة واحدة
        # Use Walrus Operator to assign and check directory in one step
        if directory := filedialog.askdirectory():
            # تحديث المسار في المكون المختص Update path in the dedicated component
            self.path_frame_widget.set_path(directory)
            # تمكين زر التحميل إذا كانت المعلومات مجلوبة والزر معطل
            # Enable download button if info is fetched and button is disabled
            # (تم تبسيط الشرط بواسطة VS Code) (Condition simplified by VS Code)
            if self.fetched_info and self.bottom_controls_widget.download_button.cget("state") == "disabled":
                 self.bottom_controls_widget.enable_download(button_text="Download Selection")

    def fetch_video_info(self):
        """
        بدء عملية جلب المعلومات (يتم استدعاؤها بواسطة TopInputFrame).
        Starts the info fetching process (called by TopInputFrame).
        """
        # الحصول على الرابط من المكون المختص Get URL from the dedicated component
        url = self.top_frame_widget.get_url()
        if not url:
            messagebox.showerror("Error", "Please enter a URL.")
            return

        # إعادة تعيين الأجزاء الديناميكية قبل البدء Reset dynamic parts before starting
        self._enter_idle_state()
        self.top_frame_widget.set_url(url) # إعادة وضع الرابط Re-set the URL

        self.current_operation = 'fetch' # تحديد نوع العملية Set operation type
        self._enter_fetching_state() # الدخول لحالة الجلب Enter fetching state
        if self.logic: # التأكد من وجود معالج المنطق Check if logic handler exists
            self.logic.start_info_fetch(url) # استدعاء المنطق Call logic

    def toggle_playlist_mode(self):
        """
        تحديث الواجهة عند تغيير مفتاح القائمة (يتم استدعاؤها بواسطة OptionsControlFrame).
        Updates UI when playlist switch is toggled (called by OptionsControlFrame).
        """
        if self.fetched_info:
             is_playlist_mode = self.options_frame_widget.get_playlist_mode()
             # التحقق من أن المعلومات المجوبة هي بالفعل قائمة تشغيل
             # Check if the fetched info is actually a playlist
             is_actually_playlist = isinstance(self.fetched_info.get('entries'), list)

             if is_playlist_mode and not is_actually_playlist:
                  print("UI_Interface: Cannot enter playlist mode: Fetched info is not a playlist.")
                  self.options_frame_widget.set_playlist_mode(False) # إجبار على الإيقاف Force off
                  self._enter_info_fetched_state(False) # إعادة العرض كفيديو مفرد Re-render as single video
             else:
                  self._enter_info_fetched_state(is_playlist_mode) # إعادة العرض حسب الوضع الجديد Re-render based on new mode

    def start_download_ui(self):
        """
        بدء عملية التحميل (يتم استدعاؤها بواسطة BottomControlsFrame).
        Starts the download process (called by BottomControlsFrame).
        """
        # الحصول على القيم من المكونات المختصة Get values from dedicated components
        url = self.top_frame_widget.get_url()
        save_path = self.path_frame_widget.get_path()
        format_choice = self.options_frame_widget.get_format_choice() # <--- سيحتوي الآن على الأسماء الجديدة This will now contain the new names
        is_playlist = self.options_frame_widget.get_playlist_mode()

        # --- التحقق الأساسي --- Basic Validation ---
        if not url: messagebox.showerror("Error", "URL is missing."); return
        if not save_path: messagebox.showerror("Error", "Save location is missing."); return
        if not os.path.isdir(save_path): messagebox.showerror("Error", "Save location is not a valid directory."); return
        if not self.fetched_info: messagebox.showerror("Error", "Please fetch info before downloading."); return

        # --- الحصول على التحديدات الديناميكية --- Get Dynamic Selections ---
        quality_format_id = None
        playlist_items_string = None
        is_actually_playlist = isinstance(self.fetched_info.get('entries'), list)

        if is_playlist and is_actually_playlist:
            playlist_items_string = self.playlist_selector_widget.get_selected_items_string()
            if not playlist_items_string:
                 messagebox.showwarning("Warning", "No playlist items selected for download.")
                 return
            quality_format_id = None # استخدام الصيغة العامة للقائمة (سيتم التعامل معها في المرحلة 2) Use general format for playlist (will be handled in Phase 2)
        else:
            quality_format_id = self.quality_selector_widget.get_selected_id()

        # --- بدء التحميل --- Start Download ---
        self.current_operation = 'download' # تحديد نوع العملية Set operation type
        self._enter_downloading_state() # الدخول لحالة التحميل Enter downloading state
        if self.logic: # التأكد من وجود المنطق Check for logic handler
            # تمرير format_choice كما هو الآن Passing format_choice as is for now
            self.logic.start_download(url, save_path, format_choice, quality_format_id, is_playlist, playlist_items_string)

    def cancel_operation_ui(self):
        """
        طلب إلغاء العملية (يتم استدعاؤها بواسطة BottomControlsFrame).
        Requests cancellation (called by BottomControlsFrame).
        """
        print("UI_Interface: Cancel button pressed.")
        if self.logic: # التأكد من وجود المنطق Check for logic handler
            self.logic.cancel_operation()


    # --- دوال الكول باك (يستدعيها المنطق) --- Callback Methods (Called by Logic) ---

    def update_status(self, message):
        """تحديث نص الحالة."""
        """Updates the status label."""
        def _update():
            color = "gray"; msg_lower = message.lower() # تحديد اللون Determine color
            if "error" in msg_lower: color = "red"
            elif "warning" in msg_lower: color = "orange"
            elif "cancel" in msg_lower: color = "orange"
            elif "complete" in msg_lower or "finished" in msg_lower or "success" in msg_lower : color = "green"
            elif "downloading" in msg_lower or "processing" in msg_lower or "fetching" in msg_lower: color="blue"
            self.status_label.configure(text=message, text_color=color)
        self.after(1, _update) # تأخير بسيط Slight delay

    def update_progress(self, value):
        """تحديث شريط التقدم."""
        """Updates the progress bar."""
        value = max(0.0, min(1.0, value))
        self.after(1, lambda: self.progress_bar.set(value)) # تأخير بسيط Slight delay

    def on_info_success(self, info_dict):
        """معالجة الواجهة عند نجاح جلب المعلومات."""
        """Handles the UI upon successful info fetch."""
        def _update():
            self.fetched_info = info_dict # تخزين المعلومات Store info
            is_playlist_mode_requested = self.options_frame_widget.get_playlist_mode()
            is_actually_playlist = info_dict is not None and isinstance(info_dict.get('entries'), list)

            # تحديد وضع العرض النهائي Determine final display mode
            final_playlist_mode = False
            if is_playlist_mode_requested and is_actually_playlist:
                final_playlist_mode = True; self.options_frame_widget.enable() # تمكين المفتاح Enable switch
            elif is_playlist_mode_requested and not is_actually_playlist:
                 print("UI_Interface: Fetched info is not a playlist, turning switch off.")
                 self.options_frame_widget.set_playlist_mode(False); final_playlist_mode = False
            else: # طلب مفرد أو ليس قائمة أصلاً Requesting single or not a playlist anyway
                 final_playlist_mode = False
                 if is_actually_playlist: self.options_frame_widget.enable() # ابق المفتاح متاحًا Keep switch enabled if it's a playlist

            # الدخول للحالة المناسبة لعرض المعلومات Enter the appropriate state to display info
            self._enter_info_fetched_state(final_playlist_mode)
        self.after(0, _update) # تحديث فوري Immediate update

    def on_info_error(self, error_message):
        """معالجة الواجهة عند فشل جلب المعلومات."""
        """Handles the UI upon failed info fetch."""
        def _update():
            messagebox.showerror("Info Fetch Error", error_message)
            self._enter_idle_state() # العودة للحالة الأولية Go back to idle state
        self.after(0, _update)

    def on_task_finished(self):
        """
        معالجة الواجهة عند انتهاء أي مهمة (جلب أو تحميل).
        Handles the UI when any background task (fetch or download) finishes.
        """
        def _process_finish():
            operation_type = self.current_operation
            self.current_operation = None # إعادة التعيين Reset

            final_status = self.status_label.cget("text").lower()
            print(f"UI_Interface: Task finished (Type: '{operation_type}'), final status: {final_status}")

            # التعامل مع الأخطاء أو الإلغاء Handle errors or cancellation
            if "error" in final_status or "cancel" in final_status:
                print("UI_Interface: Error or Cancel detected, attempting to restore previous state.")
                if self.fetched_info:
                    # محاولة استعادة حالة عرض المعلومات Restore info fetched state if possible
                    is_playlist_mode = self.options_frame_widget.get_playlist_mode()
                    is_actually_playlist = isinstance(self.fetched_info.get('entries'), list)
                    final_playlist_mode = is_playlist_mode and is_actually_playlist
                    self._enter_info_fetched_state(final_playlist_mode) # إعادة تطبيق الحالة Reapply state
                else:
                    self._enter_idle_state() # العودة للأولية إذا لا توجد معلومات Go idle if no info ever fetched
            # التعامل مع النجاح Handle success
            elif operation_type == 'fetch':
                # نجاح جلب المعلومات: الواجهة يجب أن تكون بالفعل في الحالة الصحيحة Fetch success: UI should already be correct
                print("UI_Interface: Fetch finished successfully. Ensuring UI is in info_fetched state.")
                # إعادة تطبيق الحالة للتأكد من تمكين الأزرار Reapply state to ensure buttons are enabled
                if self.fetched_info:
                    is_playlist_mode = self.options_frame_widget.get_playlist_mode()
                    is_actually_playlist = isinstance(self.fetched_info.get('entries'), list)
                    final_playlist_mode = is_playlist_mode and is_actually_playlist
                    self._enter_info_fetched_state(final_playlist_mode)
                else:
                    print("WARN: UI_Interface: Fetch finished but fetched_info is missing? Resetting.")
                    self._enter_idle_state() # حالة غير متوقعة Unexpected state
            elif operation_type == 'download':
                 # نجاح التحميل: العودة للحالة الأولية Download success: Go back to idle state
                 print("UI_Interface: Download finished successfully. Resetting to idle state.")
                 self._enter_idle_state()
            else:
                 # حالة غير معروفة Unknown state
                 print(f"UI_Interface: Unknown or no operation type ('{operation_type}'). Resetting.")
                 self._enter_idle_state()

        self.after(10, _process_finish) # تأخير بسيط Small delay