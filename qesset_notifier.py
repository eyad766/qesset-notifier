# -*- coding: utf-8 -*-
"""
منبّه حلقات قصة عشق (qesset.com)
يراقب صفحة آخر الحلقات ويرسل إشعار للجوال فيه اسم الحلقة ورابطها.

التشغيل:
    pip install requests
    python qesset_notifier.py          # يشتغل باستمرار ويفحص كل فترة
    python qesset_notifier.py --test   # يرسل آخر حلقة كإشعار تجريبي
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import requests

# ================== الإعدادات ==================

# طريقة الإشعار: "ntfy" (الأسهل) أو "telegram"
NOTIFY_METHOD = os.environ.get("NOTIFY_METHOD", "ntfy")

# --- ntfy: نزّل تطبيق ntfy من المتجر واشترك بنفس الاسم هذا (غيّره لاسم خاص فيك) ---
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "eyad-qesset-episodes-7391")

# --- telegram: سوّ بوت من @BotFather وحط التوكن، والـ chat id من @userinfobot ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# مسلسلات معيّنة فقط؟ اكتب أجزاء من الاسم (عربي أو من الرابط). اتركها فاضية = كل الحلقات
WATCH_LIST = []  # مثال: ["حيث تشرق الشمس", "gunesin-dogdugu-yer", "القهوة المالحة"]

CHECK_EVERY_MINUTES = 10

# ===============================================

PAGE_URL = "https://qesset.com/son-bolumler/"
STATE_FILE = Path(__file__).with_name("qesset_seen.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "ar,en;q=0.8",
}

LINK_RE = re.compile(
    r'<a[^>]+href="(https://qesset\.com/clarus/[^"]*?-episode-\d+/?)"[^>]*>(.*?)</a>',
    re.S | re.I,
)
TITLE_ATTR_RE = re.compile(r'title="([^"]+)"')


def clean(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = (text.replace("&#8211;", "-").replace("&amp;", "&")
                .replace("&quot;", '"').replace("&#039;", "'"))
    return re.sub(r"\s+", " ", text).strip()


def fetch_episodes():
    """يرجّع قائمة [(الرابط, العنوان)] بالترتيب من الأحدث."""
    html = requests.get(PAGE_URL, headers=HEADERS, timeout=30).text
    episodes, seen = [], set()
    for m in LINK_RE.finditer(html):
        url, inner = m.group(1), m.group(2)
        if url in seen:
            continue
        title = clean(inner)
        if not title:  # رابط صورة بدون نص: خذ العنوان من title=
            t = TITLE_ATTR_RE.search(m.group(0))
            title = clean(t.group(1)) if t else ""
        title = title.replace(" - قصة عشق", "").strip()
        if not title:
            title = url.rstrip("/").split("/")[-1].replace("-", " ")
        seen.add(url)
        episodes.append((url, title))
    return episodes


def wanted(url, title):
    if not WATCH_LIST:
        return True
    return any(w.lower() in title.lower() or w.lower() in url.lower() for w in WATCH_LIST)


def notify(title, url):
    message = f"🎬 نزلت حلقة جديدة!\n{title}\n{url}"
    if NOTIFY_METHOD == "telegram":
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": message},
            timeout=30,
        ).raise_for_status()
    else:
        requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=f"{title}\n{url}".encode("utf-8"),
            headers={
                "Title": "New episode - qesset".encode("utf-8"),
                "Click": url,          # الضغط على الإشعار يفتح الحلقة
                "Tags": "tv",
            },
            timeout=30,
        ).raise_for_status()
    print(f"✅ أُرسل إشعار: {title}")


def load_seen():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    return None


def save_seen(seen):
    STATE_FILE.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=1), encoding="utf-8")


def check_once():
    episodes = fetch_episodes()
    if not episodes:
        print("⚠️ ما لقيت حلقات في الصفحة (يمكن تغيّر شكل الموقع)")
        return
    seen = load_seen()
    if seen is None:
        # أول تشغيل: نحفظ الموجود بدون إشعارات عشان ما ينزل عليك 50 إشعار
        save_seen({u for u, _ in episodes})
        print(f"أول تشغيل: حُفظت {len(episodes)} حلقة. آخر حلقة: {episodes[0][1]}")
        return
    new = [(u, t) for u, t in episodes if u not in seen]
    for url, title in reversed(new):  # الأقدم أولاً
        if wanted(url, title):
            try:
                notify(title, url)
            except Exception as e:
                print(f"❌ فشل الإرسال: {e}")
                continue
        seen.add(url)
    save_seen(seen)
    if not new:
        print(time.strftime("%H:%M"), "لا جديد")


def main():
    if "--test" in sys.argv:
        url, title = fetch_episodes()[0]
        notify(title, url)
        return
    once = "--once" in sys.argv  # للتشغيل من Task Scheduler / cron
    while True:
        try:
            check_once()
        except Exception as e:
            print(f"❌ خطأ: {e}")
        if once:
            break
        time.sleep(CHECK_EVERY_MINUTES * 60)


if __name__ == "__main__":
    main()
