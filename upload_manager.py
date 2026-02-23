import os
import math
import random
import asyncio
import time
from telethon.tl.types import InputFileBig, InputFile, DocumentAttributeVideo
from telethon.tl.functions.upload import SaveBigFilePartRequest, SaveFilePartRequest
from video_processor import get_video_duration, generate_thumbnail

# Settings from main
PARALLEL_UPLOADS = 4

async def fast_upload(client, file_path, progress_callback=None):
    """
    يقوم برفع الملف باستخدام عدة اتصالات متوازية (Parallel Connections)
    لتسريع العملية بشكل كبير مقارنة بالرفع المتسلسل.
    """
    file_size = os.path.getsize(file_path)
    file_name = os.path.basename(file_path)
    
    # 512KB is a good chunk size
    chunk_size = 512 * 1024
    total_parts = math.ceil(file_size / chunk_size)
    file_id = random.randint(-(2**63), 2**63 - 1)
    
    # Semaphore للتحكم بعدد المهام المتزامنة
    sem = asyncio.Semaphore(PARALLEL_UPLOADS)
    
    uploaded_bytes = 0
    lock = asyncio.Lock()
    
    async def upload_part(part_index, part_bytes):
        nonlocal uploaded_bytes
        async with sem:
            if file_size > 10 * 1024 * 1024: # أكبر من 10 ميجا نستخدم BigPart
                await client(SaveBigFilePartRequest(
                    file_id=file_id,
                    file_part=part_index,
                    file_total_parts=total_parts,
                    bytes=part_bytes
                ))
            else:
                await client(SaveFilePartRequest(
                    file_id=file_id,
                    file_part=part_index,
                    bytes=part_bytes
                ))
                
            async with lock:
                uploaded_bytes += len(part_bytes)
                if progress_callback:
                    progress_callback(uploaded_bytes, file_size)

    tasks = []
    with open(file_path, 'rb') as f:
        for i in range(total_parts):
            chunk = f.read(chunk_size)
            tasks.append(upload_part(i, chunk))
    
    # استخدام return_exceptions لمنع توقف البرنامج عند حدوث خطأ في أي مهمة
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # التحقق من وجود أخطاء
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            raise Exception(f"فشل رفع الجزء {i}: {result}")

    if file_size > 10 * 1024 * 1024:
        return InputFileBig(
            id=file_id,
            parts=total_parts,
            name=file_name
        )
    else:
        return InputFile(
            id=file_id,
            parts=total_parts,
            name=file_name,
            md5_checksum='' # ليس ضرورياً
        )

async def send_file_tele(client, entity, fpath, caption=None, file_category="video", reply_to=None):
    """إرسال ملف باستخدام الرفع المتوازي مع دعم الصور المصغرة والمدة الزمنية والمستندات"""
    file_size = os.path.getsize(fpath)
    type_names = {"video": "فيديو", "image": "صورة", "document": "مستند"}
    file_type = type_names.get(file_category, "ملف")
    print(f"🚀 بدء الرفع السريع (Parallel Upload): {os.path.basename(fpath)} ({file_size/1024/1024:.2f} MB) [{file_type}]")
    
    start = time.time()
    last_print = start
    
    def progress_cb(current, total):
        nonlocal last_print
        now = time.time()
        pct = (current / total * 100) if total else 0
        if now - last_print >= 0.5 or pct >= 100:
            elapsed = now - start if now - start > 0 else 0.001
            speed = current / 1024 / 1024 / elapsed
            remaining = (total - current) / 1024 / 1024 / speed if speed > 0 else 0
            print(f"\r⚡ سرعة: {speed:.2f} MB/s | {pct:5.1f}% | {current/1024/1024:.2f}/{total/1024/1024:.2f} MB | باقي {int(remaining)}s", end="", flush=True)
            last_print = now

    # 1. Upload file handle first
    file_handle = await fast_upload(client, fpath, progress_callback=progress_cb)
    print() # newline

    # معالجة بيانات الفيديو الإضافية (صورة مصغرة ومدة)
    attributes = []
    thumb_path = None
    if file_category == "video":
        duration = get_video_duration(fpath)
        attributes.append(DocumentAttributeVideo(
            duration=duration,
            w=0, h=0, # الأبعاد يمكن تركها 0 أو استخراجها إن لزم الأمر
            supports_streaming=True
        ))
        
        output_dir = os.path.dirname(fpath)
        thumb_path = generate_thumbnail(fpath, output_dir)

    # 2. Send the message with the handle and attributes
    try:
        await client.send_file(
            entity,
            file_handle,
            caption=caption,
            thumb=thumb_path, # إضافة الغلاف
            attributes=attributes if attributes else None, # إضافة المدة
            supports_streaming=True if file_category == "video" else False,
            force_document=True if file_category == "document" else False, # إرسال المستندات كملف
            reply_to=reply_to  # للإرسال إلى توبيك معين
        )
    finally:
        # تنظيف الصورة المصغرة المؤقتة إن وُجدت
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except:
                pass

    print()  # newline after progress
