import os
import asyncio
import sys
import json
import time
from telethon import TelegramClient, utils
from telethon.errors import FloodWaitError
from video_processor import check_ffmpeg, probe_codecs, reencode_with_progress
from smart_sort import smart_sort_key
from upload_manager import send_file_tele

import argparse
import re
import tkinter as tk
from tkinter import filedialog

# Check for cryptg
try:
    import cryptg
    print("✅ مكتبة التشفير السريع (cryptg) مثبتة وتعمل.")
except ImportError:
    print("⚠️ مكتبة (cryptg) غير موجودة! سيتم استخدام التشفير البطيء.")
except Exception as e:
    print(f"⚠️ خطأ في تحميل (cryptg): {e}. سيتم استخدام التشفير البطيء.")

# ---------- CONFIG ----------
API_ID = 9563612
API_HASH = "bb723be5e3d8196761e04d640337ee60"
# عدد الاتصالات المتوازية للرفع
PARALLEL_UPLOADS = 4
# حجم الجزء للرفع المتوازي (512 كيلوبايت هو الأمثل لتيليجرام)
CHUNK_SIZE_KB = 512 

def choose_folder_dialog():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    return filedialog.askdirectory(title="اختر المجلد الذي يحتوي الفيديوهات")
# ----------------------------

def parse_telegram_link(link_or_id, default_topic=None):
    """
    تحليل رابط تيليجرام أو معرّف واستخراج المعلومات
    
    Examples:
        https://t.me/c/2409670668/2014 -> (-1002409670668, 2014)
        https://t.me/username/2014 -> (username, 2014)
        @channelname -> (@channelname, None)
        -1002409670668 -> (-1002409670668, None)
    
    Returns:
        (entity_id, topic_id)
    """
    link_str = str(link_or_id).strip()
    
    # نمط رابط t.me/c/CHANNEL_ID/TOPIC_ID أو t.me/c/CHANNEL_ID/TOPIC_ID/MSG_ID
    pattern_c = r'https?://t\.me/c/(\d+)(?:/(\d+))?(?:/\d+)?'
    match_c = re.match(pattern_c, link_str)
    
    if match_c:
        channel_id = match_c.group(1)
        topic_id = match_c.group(2)
        entity_id = f"-100{channel_id}"
        if topic_id:
            return (entity_id, int(topic_id))
        else:
            return (entity_id, default_topic)
            
    # نمط رابط t.me/username/TOPIC_ID أو MSG_ID
    pattern_pub = r'https?://t\.me/([a-zA-Z0-9_]+)/(\d+)'
    match_pub = re.match(pattern_pub, link_str)
    if match_pub and not link_str.startswith('https://t.me/c/') and not link_str.startswith('https://t.me/+'):
        username = match_pub.group(1)
        topic_id = match_pub.group(2)
        return (username, int(topic_id))
    
    # تنظيف روابط username العادية t.me/username
    pattern_simple = r'https?://t\.me/([a-zA-Z0-9_]+)/?$'
    match_simple = re.match(pattern_simple, link_str)
    if match_simple and not link_str.startswith('https://t.me/c/') and not link_str.startswith('https://t.me/+'):
        return (match_simple.group(1), default_topic)

    # إذا لم يُطابق الأنماط السابقة، أرجع القيمة كما هي
    return (link_or_id, default_topic)




# ----------------------------
def build_caption(base_path, file_path, filename):
    """
    بناء وصف هيكلي (Caption) للملف بناءً على مكانه في المجلدات الفرعية.
    يضيف مسافات متدرجة لكل مستوى مجلد ليظهر الملف بشكل شجري.
    """
    rel_path = os.path.relpath(file_path, base_path)
    rel_dir = os.path.dirname(rel_path)
    
    # إذا كان الملف في المجلد الرئيسي مباشرة
    if rel_dir == "" or rel_dir == ".":
        return filename
        
    parts = rel_dir.split(os.sep)
    caption_lines = []
    
    indent = ""
    for part in parts:
        caption_lines.append(f"{indent}{part} /")
        indent += "    " # 4 مسافات للمستوى التالي
        
    # سطر فارغ قبل اسم الملف كما طلب المستخدم
    caption_lines.append("")
    # اسم الملف مع الإزاحة النهائية
    caption_lines.append(f"{indent}{filename}")
    
    return "\n".join(caption_lines)

# ----------------- Main flow -----------------
async def main(session_name, target, folder_path, topic_id=None, loop=None, existing_client=None, series_preferences=None):
    # تحليل الرابط أو المعرّف
    parsed_target, parsed_topic = parse_telegram_link(target, topic_id)
    
    # إذا تم استخراج topic من الرابط ولم يتم تحديد topic يدوياً، استخدم المستخرج
    if parsed_topic and not topic_id:
        topic_id = parsed_topic
        print(f"ℹ️ تم استخراج معرّف التوبيك من الرابط: {topic_id}")
    
    # استخدم المعرّف المحلل
    target = parsed_target
    print(f"🎯 الوجهة: {target}")
    
    ok, missing = check_ffmpeg()
    if not ok:
        print(f"❌ ffmpeg/ffprobe غير مُثبت أو غير موجود في PATH (مفقود: {missing}). رَكِّب FFmpeg وأعد المحاولة.")
        return

    if not os.path.isdir(folder_path):
        print("❌ مسار المجلد غير صالح:", folder_path)
        return

    uploaded_file = os.path.join(folder_path, "uploaded_files.json")
    if os.path.exists(uploaded_file) and os.path.getsize(uploaded_file) > 0:
        try:
            with open(uploaded_file, "r", encoding="utf-8") as f:
                uploaded = json.load(f)
        except Exception:
            uploaded = {}
    else:
        uploaded = {}

    # إذا تم تمرير كلاينت موجود (من الواجهة الرسومية)، نستخدمه مباشرةً
    if existing_client is not None:
        client = existing_client
        if not client.is_connected():
            await client.connect()
        owned_client = False  # لا نملكه، لا نقفل الاتصال عند الانتهاء
    else:
        client = TelegramClient(session_name, API_ID, API_HASH, loop=loop)
        await client.start()
        owned_client = True


    try:
        # Convert string ID to int if it looks like an ID
        if isinstance(target, str) and (target.startswith("-100") or target.lstrip('-').isdigit()):
            try:
                target = int(target)
            except ValueError:
                pass

        try:
            # معالجة روابط الدعوة الخاصة (Join Link) مثل t.me/+xxx أو t.me/joinchat/xxx
            invite_match = re.search(r't\.me/(?:\+|joinchat/)([a-zA-Z0-9_-]+)', str(target))
            if invite_match:
                hash_val = invite_match.group(1)
                from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
                from telethon.tl.types import ChatInviteAlready, ChatInvite
                try:
                    invite_res = await client(CheckChatInviteRequest(hash_val))
                    if isinstance(invite_res, ChatInviteAlready):
                        entity = invite_res.chat
                    elif isinstance(invite_res, ChatInvite):
                        print(f"⚠️ لست منضماً، جاري الانضمام إلى القناة/المجموعة عبر رابط الدعوة...")
                        updates = await client(ImportChatInviteRequest(hash_val))
                        entity = updates.chats[0]
                    else:
                        entity = invite_res.chat
                except Exception as e:
                    print(f"❌ فشل استخدام رابط الدعوة: {e}")
                    raise ValueError(f"Invalid invite link: {e}")
            else:
                entity = await client.get_entity(target)
        except ValueError:
            # Fallback: search in dialogs
            print(f"⚠️ لم يتم العثور المباشر، جاري البحث في المحادثات عن {target}...")
            found = False
            async for dialog in client.iter_dialogs():
                if dialog.id == target or (hasattr(dialog.entity, 'username') and dialog.entity.username and f"@{dialog.entity.username}" == target):
                    entity = dialog.entity
                    found = True
                    break
            
            if not found:
                raise Exception(f"Cannot find entity {target}")
            print("✅ تم العثور على الهدف في المحادثات.")

        if topic_id:
            print(f"📌 سيتم الإرسال إلى التوبيك: {topic_id}")
            
    except Exception as e:
        print("❌ خطأ في الحصول على الهدف:", e)
        if owned_client:
            await client.disconnect()
        return

    temp_dir = os.path.join(folder_path, ".temp_opt")
    os.makedirs(temp_dir, exist_ok=True)

    # امتدادات الملفات المدعومة
    VIDEO_EXTENSIONS = (".mp4", ".mkv", ".mov", ".avi", ".ts", ".webm", ".flv", ".wmv", ".mpeg", ".mpg", ".m4v", ".3gp")
    IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")
    DOC_EXTENSIONS = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".zip", ".rar", ".txt", ".csv", ".xlsx")
    SUPPORTED_EXTENSIONS = VIDEO_EXTENSIONS + IMAGE_EXTENSIONS + DOC_EXTENSIONS
    

    # البحث في المجلد الرئيسي وجميع المجلدات الفرعية
    files_to_upload = []
    
    for root, dirs, files_in_dir in os.walk(folder_path):
        # استبعاد المجلد المؤقت من البحث
        if ".temp_opt" in dirs:
            dirs.remove(".temp_opt")
            
        rel_root = os.path.relpath(root, folder_path)
        dir_name_display = rel_root if rel_root != '.' else 'المجلد الرئيسي'
        print(f"🔍 فحص المجلد: {dir_name_display}")
            
        # فرز المجلدات الفرعية ذكياً لضمان دخولها بالترتيب الصحيح
        dirs.sort(key=smart_sort_key)
        
        def custom_sort(f):
            priority, natsort_key = smart_sort_key(f)
            file_time = os.path.getctime(os.path.join(root, f))
            
            # الفرقة الأولى للصدارة، ثم الترتيب الطبيعي (النصوص والأرقام)، ثم وقت الإنشاء
            return (priority, natsort_key, file_time)
                
        # تطبيق الفرز على الملفات داخل هذا المجلد فقط وإضافتها لطابور الرفع
        files_in_dir.sort(key=custom_sort)
        for f in files_in_dir:
            if f.lower().endswith(SUPPORTED_EXTENSIONS):
                files_to_upload.append(os.path.join(root, f))
                
    if not files_to_upload:
        print("⚠️ لا توجد ملفات فيديو أو صور في المجلد أو المجلدات الفرعية.")
        if owned_client:
            await client.disconnect()
        return

    for fpath in files_to_upload:
        fname = os.path.basename(fpath)
        if fpath in uploaded:
            print(f"⏭️ {fname} — مُسجّل سابقًا، تخطّي.")
            continue

        print("\n------------------------------")
        
        # استخراج الوصف الهيكلي الشجري
        custom_caption = build_caption(folder_path, fpath, fname)
        
        print("📁 المعالجة:", fname)
        
        # تحديد نوع الملف
        ext = os.path.splitext(fname)[1].lower()
        is_video = ext in VIDEO_EXTENSIONS
        
        if ext in IMAGE_EXTENSIONS:
            file_category = "image"
            # الصور لا تحتاج معالجة، يتم إرسالها مباشرة
            print(f"🖼️ صورة تم اكتشافها — سيتم الإرسال مباشرة.")
            to_send = fpath
        elif ext in DOC_EXTENSIONS:
            file_category = "document"
            # المستندات ترسل مباشرة دون ترميز
            print(f"📄 مستند تم اكتشافه — سيتم الإرسال مباشرة.")
            to_send = fpath
        elif is_video:
            file_category = "video"
            # معالجة الفيديو
            vcodec, acodec, ext = probe_codecs(fpath)
            print(f" ▶ حزمة: ext={ext} video={vcodec} audio={acodec}")

            VALID_V = ("h264", "hevc", "h265", "mpeg4")
            VALID_A = ("aac", "mp3", "eac3")

            # Allow if validated or if validation is ambiguous (empty codec)
            is_valid_v = (vcodec in VALID_V)
            is_valid_a = (acodec in VALID_A) or (not acodec) # Allow empty audio

            if ext == ".mp4" and is_valid_v and is_valid_a:
                print(f"ℹ️ الملف ({vcodec}/{acodec}) مدعوم/مقبول — سيتم الإرسال دون إعادة ترميز.")
                to_send = fpath
            else:
                # re-encode into temp dir
                out_path = os.path.join(temp_dir, os.path.splitext(fname)[0] + "_opt.mp4")
                res = reencode_with_progress(fpath, out_path)
                if not res:
                    print("‼️ فشل التحويل، سيتم تخطي الملف.")
                    continue
                to_send = res

        # send
        try:
            print("⬆️ بدء الرفع إلى تيليجرام...")
            await send_file_tele(client, entity, to_send, caption=custom_caption, file_category=file_category, reply_to=topic_id)
            print("✅ تم الإرسال:", fname)
        except FloodWaitError as e:
            print(f"⏱️ FloodWait — الانتظار {e.seconds}s")
            await asyncio.sleep(e.seconds)
            # optionally retry after sleep
            continue
        except Exception as e:
            print("❌ خطأ أثناء الرفع:", e)
            continue

        # سجل الملف كمرسل (المسار الأصلي)
        uploaded[fpath] = {
            "name": fname,
            "path": fpath,
            "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(uploaded_file, "w", encoding="utf-8") as f:
            json.dump(uploaded, f, ensure_ascii=False, indent=2)
        print(f"💾 سُجّل في {uploaded_file}")

        # احذف الملف المؤقت المحسّن لتوفّر المساحة (إن لم يكن نفس الملف)
        if to_send != fpath:
            try:
                os.remove(to_send)
            except Exception:
                pass

    if owned_client:
        await client.disconnect()
    # حاول حذف المجلد المؤقت إن كان فارغًا

    try:
        if os.path.isdir(temp_dir) and not os.listdir(temp_dir):
            os.rmdir(temp_dir)
    except Exception:
        pass
    print("\n✅ انتهت المعالجة.")

# CLI.
if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="رفع الصور والفيديوهات إلى تيليجرام بسرعة عالية",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
أمثلة الاستخدام:
  # رفع إلى الرسائل المحفوظة (الافتراضي):
  python send_files_to_telegram.py --session mysession
  
  # رفع إلى قناة أو مجموعة (باستخدام معرّف المستخدم):
  python send_files_to_telegram.py --session mysession --target @channelname
  
  # رفع إلى قناة خاصة (باستخدام رابط الدعوة):
  python send_files_to_telegram.py --session mysession --target https://t.me/+xxxxxxxxxxxxx
  
  # رفع إلى توبيك معين باستخدام الرابط مباشرة (سيتم استخراج المعرف والتوبيك تلقائياً):
  python send_files_to_telegram.py --session mysession --target "https://t.me/c/2409670668/2014"
  
  # رفع إلى توبيك معين في مجموعة (طريقة يدوية):
  python send_files_to_telegram.py --session mysession --target @groupname --topic 123
  
  # تحديد المجلد:
  python send_files_to_telegram.py --session mysession --folder "C:\\path\\to\\folder"
        """
    )
    p.add_argument("--session", required=True, help="اسم ملف الجلسة (.session)")
    p.add_argument(
        "--target", 
        required=False, 
        default="me", 
        help="الوجهة: 'me' للرسائل المحفوظة، '@username' للقناة/مجموعة، أو رابط دعوة"
    )
    p.add_argument(
        "--topic",
        type=int,
        required=False,
        help="معرّف التوبيك (Topic ID) إذا كنت تريد الإرسال لتوبيك معين في مجموعة"
    )
    p.add_argument("--folder", required=False, help="مسار المجلد (إذا لم يتم تحديده، سيظهر مربع حوار)")
    args = p.parse_args()

    folder = args.folder
    if not folder:
        # gui folder picker
        folder = choose_folder_dialog()
    if not folder:
        print("❌ لم يتم تحديد مجلد. الخروج.")
        sys.exit(1)

    asyncio.run(main(args.session, args.target, folder, args.topic))
