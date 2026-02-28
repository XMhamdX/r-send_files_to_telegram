import os
import re

NUMERAL_WORDS = {
    'الاولى': 1, 'الاول': 1, 'الأولى': 1, 'الأول': 1, 'اولى': 1, 'اول': 1, 'أولى': 1, 'أول': 1,
    'مقدمة': 1, 'المقدمة': 1, 'تقديم': 1, 'التقديم': 1, 'تعريف': 1, 'التعريف': 1, 'تمهيد': 1, 'التمهيد': 1,
    'الثانية': 2, 'الثاني': 2, 'الثانيه': 2, 'ثانية': 2, 'ثاني': 2,
    'الثالثة': 3, 'الثالث': 3, 'الثالثه': 3, 'ثالثة': 3, 'ثالث': 3,
    'الرابعة': 4, 'الرابع': 4, 'الرابعه': 4, 'رابعة': 4, 'رابع': 4,
    'الخامسة': 5, 'الخامس': 5, 'الخامسه': 5, 'خامسة': 5, 'خامس': 5,
    'السادسة': 6, 'السادس': 6, 'السادسه': 6, 'سادسة': 6, 'سادس': 6,
    'السابعة': 7, 'السابع': 7, 'السابعه': 7, 'سابعة': 7, 'سابع': 7,
    'الثامنة': 8, 'الثامن': 8, 'الثامنه': 8, 'ثامنة': 8, 'ثامن': 8,
    'التاسعة': 9, 'التاسع': 9, 'التاسعه': 9, 'تاسعة': 9, 'تاسع': 9,
    'العاشرة': 10, 'العاشر': 10, 'العاشره': 10, 'عاشرة': 10, 'عاشر': 10,
}
ABSOLUTE_FIRST_PHRASES = ['تعريف عام', 'مقدمة عامة', 'فيديو تعريفي']

def smart_sort_key(filename):
    name_without_ext = os.path.splitext(filename)[0]
    cleaned_name = re.sub(r'[_.\-]', ' ', name_without_ext).strip()
    words = cleaned_name.split()

    if any(phrase in cleaned_name for phrase in ABSOLUTE_FIRST_PHRASES):
        return (-1, cleaned_name, (0,))

    SEQUENCE_HINTS = ['جزء', 'الجزء', 'محاضرة', 'المحاضرة', 'درس', 'الدرس', 'مقطع', 'المقطع', 'قسم', 'القسم', 'حلقة', 'الحلقة']

    base_name = cleaned_name
    for hint in SEQUENCE_HINTS:
        base_name = re.sub(rf'\b{hint}\b', '', base_name)
    for word in NUMERAL_WORDS:
        base_name = re.sub(rf'\b{word}\b', '', base_name)
    base_name = re.sub(r'\d+', '', base_name)
    base_name = re.sub(r'\s+', ' ', base_name).strip()

    num_seq = []
    # Find all standalone digits and numeral words
    for word in words:
        if word.isdigit():
            num_seq.append(int(word))
        elif word in NUMERAL_WORDS:
            num_seq.append(NUMERAL_WORDS[word])

    if not num_seq:
        return (0, cleaned_name, (float('inf'),))

    return (1, base_name, tuple(num_seq))

names = [
    "دوبلاج 4- المحاضرة الخامسة.mp4",
    "دوبلاج 4- المحاضرة السادسة جزء 1.mp4",
    "دوبلاج 4- المحاضرة السادسة جزء 2.mp4",
    "قائمة مهام التصوير 1.mp4",
    "قائمة مهام التصوير 9.mp4",
    "1.الدرس.mp4",
    "تعريف عام.mp4",
    "ملف غير مرقم.mp4"
]

res = []
for n in names:
    res.append(smart_sort_key(n))

res.sort()

for r in res:
    print(r)
