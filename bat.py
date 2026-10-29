
import os
import json
import time
import requests
from pathlib import Path

TOKEN = os.getenv("BALE_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_CHAT_ID", "").strip()
CHANNEL_URL = "https://ble.ir/khaz_kade1"

API = f"https://tapi.bale.ai/bot{TOKEN}"
DATA_FILE = Path("bot_data.json")

sessions = {}
data = {
    "last_update_id": 0,
    "tickets": {}
}

http = requests.Session()


def load_data():
    global data

    try:
        if DATA_FILE.exists():
            saved = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                data.update(saved)

        if not isinstance(data.get("tickets"), dict):
            data["tickets"] = {}

    except (OSError, ValueError) as error:
        print("خطا در خواندن اطلاعات:", error)


def save_data():
    try:
        temp = DATA_FILE.with_suffix(".tmp")
        temp.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        temp.replace(DATA_FILE)
    except OSError as error:
        print("خطا در ذخیره اطلاعات:", error)


def api(method, payload=None):
    if not TOKEN:
        return {"ok": False, "description": "BALE_TOKEN تنظیم نشده است"}

    try:
        response = http.post(
            f"{API}/{method}",
            json=payload or {},
            timeout=40
        )
        response.raise_for_status()
        result = response.json()

        if not isinstance(result, dict):
            return {"ok": False, "description": "پاسخ نامعتبر از API"}

        if result.get("ok") is not True:
            print("خطای API:", result)

        return result

    except (requests.RequestException, ValueError) as error:
        print("خطای ارتباط با بله:", error)
        return {"ok": False, "description": str(error)}


def send(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        payload["reply_markup"] = keyboard

    return api("sendMessage", payload)


def main_menu():
    return {
        "keyboard": [
            [
                {"text": "🛠 خدمات"},
                {"text": "📝 ثبت سفارش"}
            ],
            [
                {"text": "📚 آموزش رایگان"},
                {"text": "📢 ورود به کانال"}
            ],
            [
                {"text": "🕵️ ارتباط با پشتیبانی"}
            ],
            [
                {"text": "ℹ️ راهنما"},
                {"text": "👨‍💼 مدیریت"}
            ]
        ],
        "resize_keyboard": True
    }


def is_admin(chat_id):
    return bool(ADMIN_ID) and str(chat_id) == ADMIN_ID


def start_support(chat_id, mode="support"):
    sessions[str(chat_id)] = {"mode": mode}

    if mode == "order":
        title = "📝 ثبت سفارش"
        body = (
            "نوع خدمت و توضیحات سفارش خود را بنویس.\n"
            "پیامت برای پشتیبانی ارسال می‌شود."
        )
    else:
        title = "🕵️ ارتباط با پشتیبانی"
        body = (
            "پیامت را بنویس و ارسال کن.\n"
            "متن پیام برای مدیر ارسال می‌شود؛ "
            "برای پاسخ، ربات باید شناسه گفت‌وگوی تو را داشته باشد."
        )

    send(
        chat_id,
        f"{title}\n\n{body}\n\nبرای لغو بنویس «لغو».",
        main_menu()
    )


def handle_support_message(chat_id, text):
    if text.strip() == "لغو":
        sessions.pop(str(chat_id), None)
        send(chat_id, "ارسال پیام لغو شد.", main_menu())
        return

    if not ADMIN_ID:
        send(
            chat_id,
            "پشتیبانی هنوز راه‌اندازی نشده است.",
            main_menu()
        )
        return

    ticket_id = str(int(time.time() * 1000))

    data["tickets"][ticket_id] = {
        "user_id": str(chat_id),
        "status": "open"
    }
    save_data()

    keyboard = {
        "inline_keyboard": [[
            {
                "text": "↩️ پاسخ به کاربر",
                "callback_data": f"reply:{ticket_id}"
            }
        ]]
    }

    result = send(
        ADMIN_ID,
        "📩 پیام جدید پشتیبانی\n"
        f"شماره پیگیری: {ticket_id}\n\n"
        f"متن پیام:\n{text}",
        keyboard
    )

    if result.get("ok") is True:
        send(
            chat_id,
            "✅ پیام تو برای پشتیبانی ارسال شد.\n"
            f"شماره پیگیری: {ticket_id}",
            main_menu()
        )
    else:
        data["tickets"].pop(ticket_id, None)
        save_data()
        send(
            chat_id,
            "❌ ارسال پیام ناموفق بود. کمی بعد دوباره تلاش کن.",
            main_menu()
        )

    sessions.pop(str(chat_id), None)


def handle_callback(callback):
    callback_id = callback.get("id")
    callback_data = callback.get("data", "")
    message = callback.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))

    if callback_id:
        api("answerCallbackQuery", {"callback_query_id": callback_id})

    if not is_admin(chat_id):
        return

    if not callback_data.startswith("reply:"):
        return

    ticket_id = callback_data.split(":", 1)[1]
    ticket = data["tickets"].get(ticket_id)

    if not ticket:
        send(chat_id, "درخواست پیدا نشد یا اطلاعات آن موجود نیست.")
        return

    sessions[chat_id] = {
        "mode": "admin_reply",
        "ticket_id": ticket_id
    }

    send(
        chat_id,
        "✍️ پاسخ خود را به‌صورت متن ارسال کن.\n"
        "برای لغو بنویس «لغو»."
    )


def handle_message(message):
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    text = message.get("text", "").strip()

    if not chat_id:
        return

    if text == "/id":
        send(chat_id, f"شناسه این گفت‌وگو:\n{chat_id}")
        return

    if text == "/start":
        sessions.pop(chat_id, None)
        send(
            chat_id,
            "سلام! 👋 به ربات خز کده خوش آمدی.\n\n"
            "از منوی زیر یکی از گزینه‌ها را انتخاب کن.",
            main_menu()
        )
        return

    session = sessions.get(chat_id)

    if session and session.get("mode") in ("support", "order"):
        if text:
            handle_support_message(chat_id, text)
        else:
            send(chat_id, "لطفاً پیام خود را به‌صورت متن ارسال کن.")
        return

    if session and session.get("mode") == "admin_reply":
        if not is_admin(chat_id):
            sessions.pop(chat_id, None)
            return

        if text == "لغو":
            sessions.pop(chat_id, None)
            send(chat_id, "پاسخ لغو شد.")
            return

        if not text:
            send(chat_id, "لطفاً پاسخ را به‌صورت متن بفرست.")
            return

        ticket_id = session.get("ticket_id")
        ticket = data["tickets"].get(ticket_id)

        if not ticket:
            sessions.pop(chat_id, None)
            send(chat_id, "درخواست پیدا نشد.")
            return

        result = send(
            ticket["user_id"],
            "📬 پاسخ پشتیبانی:\n\n" + text,
            main_menu()
        )

        if result.get("ok") is True:
            ticket["status"] = "answered"
            save_data()
            send(chat_id, "✅ پاسخ برای کاربر ارسال شد.")
        else:
            send(chat_id, "❌ ارسال پاسخ ناموفق بود.")

        sessions.pop(chat_id, None)
        return

    if text in ("🕵️ ارتباط با پشتیبانی", "پشتیبانی"):
        start_support(chat_id)
        return

    if text in ("🛠 خدمات", "خدمات"):
        send(
            chat_id,
            "🛠 خدمات خز کده\n\n"
            "• ساخت تصویر با هوش مصنوعی\n"
            "• طراحی سایت\n"
            "• برنامه‌نویسی و ساخت ابزار\n"
            "• ساخت فونت و استیکر\n\n"
            "برای ثبت درخواست، «ثبت سفارش» را بزن.",
            main_menu()
        )
        return

    if text in ("📝 ثبت سفارش", "ثبت سفارش", "سفارش"):
        start_support(chat_id, "order")
        return

    if text in ("📚 آموزش رایگان", "آموزش رایگان"):
        send(
            chat_id,
            "📚 آموزش‌ها و مطالب رایگان خز کده:\n" + CHANNEL_URL,
            main_menu()
        )
        return

    if text in ("📢 ورود به کانال", "کانال"):
        send(
            chat_id,
            "📢 ورود به کانال خز کده:\n" + CHANNEL_URL,
            main_menu()
        )
        return

    if text in ("ℹ️ راهنما", "راهنما", "/help"):
        send(
            chat_id,
            "ℹ️ راهنمای ربات\n\n"
            "از دکمه‌های منو استفاده کن.\n"
            "برای ارسال پیام، «ارتباط با پشتیبانی» را انتخاب کن.\n"
            "برای لغو ارسال، بنویس «لغو».",
            main_menu()
        )
        return

    if text in ("👨‍💼 مدیریت", "مدیریت"):
        if is_admin(chat_id):
            send(
                chat_id,
                "👨‍💼 پنل مدیریت\n\n"
                "پیام‌های پشتیبانی به این گفت‌وگو می‌آیند.\n"
                "برای پاسخ، دکمه زیر پیام را بزن.",
                main_menu()
            )
        else:
            send(chat_id, "این بخش مخصوص مدیر ربات است.", main_menu())
        return

    send(
        chat_id,
        "متوجه درخواستت نشدم. از دکمه‌های منو استفاده کن.",
        main_menu()
    )


def main():
    if not TOKEN:
        print("خطا: متغیر BALE_TOKEN تنظیم نشده است.")
        return

    load_data()
    print("ربات خز کده اجرا شد.")

    offset = int(data.get("last_update_id", 0)) + 1

    while True:
        try:
            response = http.get(
                f"{API}/getUpdates",
                params={"timeout": 25, "offset": offset},
                timeout=35
            )
            response.raise_for_status()
            result = response.json()

            if not isinstance(result, dict) or result.get("ok") is not True:
                print("خطای دریافت پیام:", result)
                time.sleep(3)
                continue

            for update in result.get("result", []):
                update_id = update.get("update_id")

                if update_id is None or update_id < offset:
                    continue

                try:
                    if update.get("callback_query"):
                        handle_callback(update["callback_query"])
                    elif update.get("message"):
                        handle_message(update["message"])
                except Exception as error:
                    print("خطا در پردازش پیام:", error)

                offset = update_id + 1
                data["last_update_id"] = update_id
                save_data()

        except KeyboardInterrupt:
            print("ربات متوقف شد.")
            break
        except (requests.RequestException, ValueError) as error:
            print("خطای ارتباط:", error)
            time.sleep(3)


if __name__ == "__main__":
    main()
