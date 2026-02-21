import os
import subprocess
import math
import random

def check_ffmpeg():
    """تأكد من وجود ffmpeg و ffprobe"""
    for tool in ("ffmpeg", "ffprobe"):
        try:
            subprocess.run([tool, "-version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        except Exception:
            return False, tool
    return True, None

def ffprobe_duration(path):
    """إرجاع مدة الفيديو بالثواني (float) باستخدام ffprobe"""
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ], stderr=subprocess.DEVNULL)
        return float(out.decode().strip())
    except Exception:
        return None

def probe_codecs(path):
    """إرجاع (video_codec, audio_codec, container_ext) أو (None, None, None) عند الفشل"""
    try:
        v = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ])
        a = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-select_streams", "a:0",
            "-show_entries", "stream=codec_name",
            "-of", "default=noprint_wrappers=1:nokey=1",
            path
        ])
        return v.decode().strip(), a.decode().strip(), os.path.splitext(path)[1].lower()
    except Exception:
        return None, None, None

def get_hw_encoder():
    """Detect available hardware encoder (NVENC, AMF, QSV)"""
    try:
        res = subprocess.check_output(["ffmpeg", "-encoders"], stderr=subprocess.DEVNULL).decode()
        if "h264_nvenc" in res: return "h264_nvenc"
        if "h264_amf" in res: return "h264_amf"
        if "h264_qsv" in res: return "h264_qsv"
        if "h264_videotoolbox" in res: return "h264_videotoolbox"
    except:
        pass
    return "libx264"

def reencode_with_progress(input_path, output_path):
    """
    إعادة ترميز الفيديو. يحاول استخدام Hardward Acceleration إذا توفر.
    مع وجود محاولة احتياطية (Fallback) لاستخدام المعالج إذا فشل كرت الشاشة.
    """
    dur = ffprobe_duration(input_path)
    # القائمة التي سنجربها: أولاً الهاردوير، ثم السوفتوير
    encoders_to_try = []
    
    hw_enc = get_hw_encoder()
    if hw_enc != "libx264":
        encoders_to_try.append(hw_enc)
    encoders_to_try.append("libx264")

    print(f"🔄 محاولة إعادة الترميز: {os.path.basename(input_path)}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    for encoder in encoders_to_try:
        current_method = "GPU" if encoder != "libx264" else "CPU"
        print(f"   .. محاولة باستخدام {current_method} ({encoder})...")

        cmd = ["ffmpeg", "-y", "-i", input_path, "-c:v", encoder]

        # settings based on encoder
        if "nvenc" in encoder:
            # -pix_fmt yuv420p is CRITICAL for 10-bit inputs to avoid crash
            cmd.extend(["-preset", "p4", "-rc", "constqp", "-qp", "23", "-pix_fmt", "yuv420p"])
        elif "amf" in encoder:
            cmd.extend(["-usage", "transcoding", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23", "-pix_fmt", "yuv420p"])
        elif "libx264" in encoder:
            cmd.extend(["-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p"])
        else:
            cmd.extend(["-b:v", "5M", "-pix_fmt", "yuv420p"])

        cmd.extend(["-c:a", "aac", "-b:a", "128k", "-movflags", "faststart", output_path])
        
        # Run ffmpeg
        proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, universal_newlines=True, bufsize=1)
        
        last_print = 0.0
        success = False
        try:
            while True:
                line = proc.stderr.readline()
                if not line:
                    if proc.poll() is not None:
                        break
                    continue
                line = line.strip()
                if "time=" in line:
                    try:
                        idx = line.index("time=")
                        time_str = line[idx+5:].split()[0]
                        parts = time_str.split(':')
                        secs = float(parts[-1]) + int(parts[-2])*60 + (int(parts[0]) * 3600 if len(parts) == 3 else 0)
                        if dur:
                            pct = min(100.0, (secs / dur) * 100.0)
                            if pct - last_print >= 1.0 or pct >= 99.9:
                                print(f"\r     ⏳ تقدم: {pct:.1f}% ({secs:.1f}/{dur:.1f}s)", end="", flush=True)
                                last_print = pct
                    except Exception:
                        pass
            
            ret = proc.wait()
            if ret == 0:
                print("\r     ✅ تم التحويل بنجاح.                          ")
                success = True
                break # Exit loop if success
            else:
                print(f"\n     ❌ فشل هذا المشفر (Code {ret}). سيتم تجربة التالي...")

        except KeyboardInterrupt:
            proc.kill()
            raise
    
    if success:
        return output_path
    else:
        print("\n❌ كل محاولات التحويل فشلت.")
        return None

def get_video_duration(path):
    """إرجاع مدة الفيديو بالثواني (int) لاستخدامها في تليجرام"""
    dur = ffprobe_duration(path)
    return int(math.floor(dur)) if dur else 0

def generate_thumbnail(video_path, output_dir):
    """
    استخراج الإطار الأول (أو إطار من الثانية 2) كصورة مصغرة (Thumbnail)
    """
    thumb_path = os.path.join(output_dir, f"thumb_{random.randint(1000, 9999)}.jpg")
    try:
        # استخراج صورة من الثانية 00:00:02 (أو 00:00:00 إذا كان الفيديو قصيراً)
        cmd = [
            "ffmpeg", "-y", "-ss", "00:00:02", "-i", video_path, 
            "-vframes", "1", "-q:v", "2", thumb_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            return thumb_path
        return None
    except Exception:
        return None
