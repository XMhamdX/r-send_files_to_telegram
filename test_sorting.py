import os
from datetime import datetime
from smart_sort import smart_sort_key

# Mock creation times (in minutes elapsed today for ease)
files_and_times = {
    # المجموعة الأولى: صدارة مطلقة (typ = -1) - رغم وقتها المتأخر
    "تعريف عام.mp4": 1100,  
    "فيديو تعريفي.mp4": 1028,
    
    # المجموعة الثانية: ملفات حرة بدون أرقام (typ = 0)
    "الرؤية.mp4": 1030,
    "المهام.mp4": 1031,
    "أسئلة للمخرج.mp4": 1032,
    "تحديد المهام والتخطيط.mp4": 1032,
    "التطبيقات الخاصة بالتصوير.mp4": 1038,
    "ملف عام.mp4": 1033, 
    
    # المجموعة الثالثة: سلاسل مبدوءة برقم (typ = 1)
    "1.الدرس.mp4": 150,
    "2.نظرة عامة على البر.mp4": 140,
    "3.ضبط خصائص البرنا.mp4": 160,
    "10.تثبيت الإطار.mp4": 100,

    # المجموعة الرابعة: سلاسل منتهية برقم (typ = 1)
    "المعدات الخاصة بالتصوير 1.mp4": 1036,
    "المعدات الخاصة بالتصوير 2.mp4": 1037,
    "تفريغ و تحليل مشاهد السيناريو 1.mp4": 1031,
    "تفريغ و تحليل مشاهد السيناريو 2.mp4": 1031,
    "قائمة مهام التصوير 2.mp4": 1033, 
    
    # المجموعة الخامسة: كلمات عربية (typ = 1)
    "مقدمة كورس التصوير.mp4": 500, # كلمة "مقدمة" تعتبر رقم 1
    "الدرس الثاني.mp4": 501,
}

def run_test(test_name):
    def custom_sort(f):
        priority, natsort_key = smart_sort_key(f)
        file_time = files_and_times[f]
        
        return (priority, natsort_key, file_time)

    files = list(files_and_times.keys())
    files.sort(key=custom_sort)
    
    print(f"\n=== الترتيب النهائي - {test_name} ===")
    for i, f in enumerate(files, 1):
        time_val = files_and_times[f]
        priority, natsort_key = smart_sort_key(f)
        
        if priority == -1: tag = " [الصدارة المطلقة]"
        elif priority == 0: tag = " [ملف حر - بدون أرقام]"
        else: tag = " [تسلسل رقمي - Natural Sort]"
        
        print(f"{i:02d}. [Time: {time_val}] {f}{tag}")
    print("==============================================\n")

run_test("التسلسل الرقمي المرجعي المحسن (Tuple Sorting)")
