import os
from datetime import datetime
from smart_sort import smart_sort_key

# Mock creation times (in minutes elapsed today for ease)
# Format based on the user screenshot: File Name -> Time Given
files_and_times = {
    "المعدات الخاصة بالتصوير 1.mp4": 12*60 + 36,
    "المعدات الخاصة بالتصوير 2.mp4": 12*60 + 37,
    "المعدات الخاصة بالتصوير 3.mp4": 12*60 + 37,
    "المعدات الخاصة بالتصوير 4.mp4": 12*60 + 37,
    "المهارات المطلوبة لحضور التصوير 1.mp4": 12*60 + 29,
    "المهارات المطلوبة لحضور التصوير 2.mp4": 12*60 + 29,
    "تفريغ و تحليل مشاهد السيناريو 1.mp4": 12*60 + 31,
    "تفريغ و تحليل مشاهد السيناريو 2.mp4": 12*60 + 31,
    "قائمة مهام التصوير 2.mp4": 12*60 + 33,
    "أسئلة للمخرج.mp4": 12*60 + 32,
    "التطبيقات الخاصة بالتصوير.mp4": 12*60 + 38,
    "الرؤية.mp4": 12*60 + 30,
    "المهام.mp4": 12*60 + 31,
    "تحديد المهام والتخطيط.mp4": 12*60 + 32,
    "تعريف عام.mp4": 12*60 + 28,
}

# The custom sorting logic deployed in send_files_to_telegram.py
def custom_sort(f):
    base_name, num = smart_sort_key(f)
    file_time = files_and_times[f]
    
    if num != float('inf'):
        # Numbered series: priority (0, base_name, number, file_time)
        return (0, base_name, num, file_time)
    else:
        # Non-numbered files: priority (1, file_time, inf) 
        return (1, "", float('inf'), file_time)

files = list(files_and_times.keys())
files.sort(key=custom_sort)

print("\n=== الترتيب النهائي كما سيقوم به البرنامج ===")
for i, f in enumerate(files, 1):
    time_str = f"{files_and_times[f] // 60:02d}:{files_and_times[f] % 60:02d}"
    print(f"{i:02d}. [{time_str}] {f}")
print("==============================================\n")
