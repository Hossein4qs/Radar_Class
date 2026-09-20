#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
اصلاح و یکسان‌سازی دیتابیس دروس دانشگاه.

کارهایی که انجام می‌ده:
1. بعضی جلسه‌ها (توی "زمان و مكان ارائه") به‌جای فیلدهای جدا (روز/ساعت شروع/
   ساعت پایان/مکان/نوع) فقط یه رشته‌ی "متن" دارن. این اسکریپت اون‌ها رو پارس
   می‌کنه و فیلدهای جدا رو به همون شکل بقیه‌ی جلسات اضافه می‌کنه.
2. برای هر جلسه (چه از قبل ساختاریافته بوده، چه تازه پارس شده) یه فیلد
   "شماره_کلاس" اضافه می‌کنه که فقط عدد اتاق/کلاسه (برای جستجوی سریع در UI).
3. گزارش آماری از کل کار می‌ده و اگه جلسه‌ای قابل‌پارس نبود، هشدار می‌ده.
"""

import json
import re
import sys
from collections import Counter

SRC = "/mnt/user-data/uploads/database.js"
DST = "/mnt/user-data/outputs/database.js"

# --- ۱. خواندن فایل و جدا کردن JSON از "window.COURSES = ...;" ---
with open(SRC, "r", encoding="utf-8") as f:
    raw = f.read().strip()

prefix = "window.COURSES ="
if not raw.startswith(prefix):
    sys.exit("فرمت فایل شبیه چیزی که انتظار داشتم نیست (باید با 'window.COURSES =' شروع بشه).")

json_part = raw[len(prefix):].strip()
if json_part.endswith(";"):
    json_part = json_part[:-1]

courses = json.loads(json_part)

# --- ۲. الگوی پارس کردن رشته‌ی "متن" ---
# نمونه‌ها:
#   "درس(ت): يك شنبه 13:00-15:00 ف مکان: كلاس 558"   (برچسب تک‌حرفی)
#   "درس(ت): دوشنبه 10:00-12:00 نيمه1 ت مکان: كلاس 608" (برچسب چندکلمه‌ای)
#   "درس(ت): چهارشنبه 12:00-14:00"                     (بدون مکان)
# چون بخش "برچسب" قبل از "مکان:" طول متغیر داره، اول رشته رو از روی
# "مکان:" می‌شکافیم و بعد قسمت اول رو با یه رگ‌اکسپ ساده‌تر پارس می‌کنیم.
SESSION_HEAD_RE = re.compile(
    r"^(?P<type>[^:]+):\s*"
    r"(?P<day>[\u0600-\u06FF\s]+?)\s+"
    r"(?P<start>\d{1,2}:\d{2})\s*-\s*(?P<end>\d{1,2}:\d{2})\s*"
    r"(?P<flag>.*)$"
)

ROOM_NUM_RE = re.compile(r"(\d+)")


def parse_session_text(text: str):
    """یه رشته‌ی 'متن' رو به فیلدهای جدا (نوع/روز/ساعت شروع/ساعت پایان/برچزم/مکان) تبدیل می‌کنه."""
    text = text.strip()
    if "مکان:" in text:
        head, place = text.split("مکان:", 1)
        place = place.strip() or None
    else:
        head, place = text, None
    m = SESSION_HEAD_RE.match(head.strip())
    if not m:
        return None
    result = {
        "نوع": m.group("type").strip(),
        "روز": m.group("day").strip(),
        "ساعت شروع": m.group("start").strip(),
        "ساعت پایان": m.group("end").strip(),
    }
    flag = m.group("flag").strip()
    if flag:
        result["پرچم_هفته"] = flag
    if place:
        result["مکان"] = place
    return result

stats = Counter()
unparsed_samples = []
place_without_digits = Counter()

def extract_room_number(place: str):
    """از رشته‌ی مکان فقط عدد کلاس/اتاق رو در میاره."""
    if not place:
        return None
    m = ROOM_NUM_RE.search(place)
    return m.group(1) if m else None


def fix_session(session: dict):
    stats["total_sessions"] += 1

    # اگر از قبل فیلدهای ساختاریافته رو داره
    if "روز" in session and "ساعت شروع" in session and "ساعت پایان" in session and "مکان" in session:
        stats["already_structured"] += 1
    elif "متن" in session:
        stats["text_only"] += 1
        parsed = parse_session_text(session["متن"])
        if parsed:
            session.update(parsed)
            stats["text_only_parsed"] += 1
            if "مکان" not in parsed:
                stats["text_only_parsed_no_place"] += 1
        else:
            stats["text_only_failed"] += 1
            if len(unparsed_samples) < 15:
                unparsed_samples.append(session.get("متن", ""))
            # جلسه‌ی پارس‌نشده رو دست‌نخورده نگه می‌داریم (بعداً قابل بررسیه)
    else:
        stats["neither_format"] += 1
        if len(unparsed_samples) < 15:
            unparsed_samples.append(json.dumps(session, ensure_ascii=False))

    # استخراج شماره کلاس (برای جلسه‌هایی که مکان مشخص شده)
    place = session.get("مکان")
    if place:
        room_num = extract_room_number(place)
        session["شماره_کلاس"] = room_num
        if room_num is None:
            place_without_digits[place] += 1


for course in courses:
    sessions = course.get("زمان و مكان ارائه") or []
    for session in sessions:
        fix_session(session)

# --- ۳. ذخیره‌ی خروجی ---
import os
os.makedirs("/mnt/user-data/outputs", exist_ok=True)
with open(DST, "w", encoding="utf-8") as f:
    f.write("window.COURSES = ")
    json.dump(courses, f, ensure_ascii=False)
    f.write(";")

# --- ۴. گزارش ---
print("=== گزارش اصلاح دیتابیس ===")
print(f"تعداد کل رکوردهای درس (course group): {len(courses)}")
print(f"تعداد کل جلسات (sessions): {stats['total_sessions']}")
print(f"  از قبل ساختاریافته: {stats['already_structured']}")
print(f"  فقط-متنی (نیاز به پارس): {stats['text_only']}")
print(f"    با موفقیت پارس شد: {stats['text_only_parsed']}")
print(f"    پارس نشد (نیاز به بررسی دستی): {stats['text_only_failed']}")
print(f"  نه ساختاریافته نه متنی (فرمت ناشناخته): {stats['neither_format']}")
print()
print(f"مکان‌هایی که عدد کلاس ازشون استخراج نشد ({len(place_without_digits)} مورد یکتا):")
for place, cnt in place_without_digits.most_common(20):
    print(f"  - {place!r}  (تعداد تکرار: {cnt})")

if unparsed_samples:
    print()
    print("نمونه‌ی مواردی که پارس نشدن:")
    for s in unparsed_samples:
        print(f"  - {s!r}")

print()
print(f"فایل خروجی ذخیره شد: {DST}")
