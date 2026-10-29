
import os
import json
import time
import requests
from pathlib import Path

TOKEN = os.getenv("BALE_TOKEN", "").strip()
ADMIN_ID = os.getenv("ADMIN_CHAT_ID", "").strip()

CHANNEL = "@khaz_kade1"
CHANNEL_URL = "https://ble.ir/khaz_kade1"

API = f"https://tapi.bale.ai/bot{TOKEN}"
DATA_FILE = Path("bot_data.json")

sessions = {}
data = {"next_update_id": None, "tickets": {}}


def load_data():
    global data
    try:
        if DATA_FILE.exists():
            loaded = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                data.update(loaded)
    except (OSError, json.JSONDecodeError):
        print("هشدار: فایل اطلاعات خوانده نشد؛ اطلاعات تازه ساخته می‌شود.")


def save_data():
    try:
        DATA_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except OSError as error:
        print("خطا در ذخیره اطلاعات:", error)


def api(method, payload=None):
    try:
        response = requests.post(
            f"{API}/{method}",
            json=payload or {},
            timeout=40
        )
        response.raise_for_status()
        result = response.json()
        if not result.get("ok", True):
            print("خطای API:", result)
        return result
    except (requests.RequestException, ValueError) as error:
        print("خطای ارتباط با بله:", error)
        return {}


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
            [{"text": "🛠 خدمات"}, {"text": "📝 ثبت سفارش"}],
            [{"text": "📚 آموزش رایگان"}, {"text": "📢 ورود به کانال"}],
            [{"text": "🕵️ ارتباط ناشناس با پشتیبانی"}],
            [{"text": "ℹ️ راهنما"}, {"text": "👨‍💼 مدیریت"}]
        ],
        "resize_keyboard": True
    }


def support_button(user_id):
    return {
        "inline_keyboard": [[
            {
                "text": "↩️ پاسخ به کاربر",
                "callback_data": f"reply:{user_id}"
            }]
        ]
    }


def is_admin(chat_id):
    return bool(ADMIN_ID) and str(chat_id) == ADMIN_ID


def start_support(chat_id):
    sessions[str(chat_id)] = {"mode": "support"}
    send(
        chat_id,
        "🕵️ ارتباط ناشناس با پشتیبانی\n\n"
        "پیام خود را ارسال کنید؛ این پیام به پشتیبانی ارسال می‌شود.\n"
        "هویت شما در متن ارسالی به مدیر نمایش داده نمی‌شود. "
        "با این حال، ربات برای رساندن پاسخ باید شناسه گفت‌وگوی شما را نگه دارد.\n\n"
        "برای لغو، بنویسید «لغو».",
        main_menu()
    )


def handle_support_message(message, chat_id, text):
    if text.strip() == "لغو":
        sessions.pop(str(chat_id), None)
        send(chat_id, "ارسال پیام لغو شد.", main_menu())
        return

    if not ADMIN_ID:
        send(
            chat_id,
            "پشتیبانی هنوز راه‌اندازی نشده است. لطفاً بعداً تلاش کنید.",
            main_menu()
        )
        print("ADMIN_CHAT_ID تنظیم نشده است.")
        return

    ticket_id = str(int(time.time() * 1000))
    data["tickets"][ticket_id] = {
        "user_id": str(chat_id),
        "status": "open"
    }
    save_data()

    admin_text = (
        "📩 پیام جدید پشتیبانی\n"
        f"شماره پیگیری: {ticket_id}\n\n"
        f"متن پیام:\n{text}"
    )

    result = send(
        ADMIN_ID,
        admin_text,
        support_button(chat_id)
    )

    if result.get("ok", True):
        send(
            chat_id,
            "✅ پیام شما برای پشتیبانی ارسال شد.\n"
            f"شماره پیگیری: {ticket_id}\n"
            "پس از دریافت پاسخ، آن را همین‌جا دریافت می‌کنید.",
            main_menu()
        )
    else:
        send(
            chat_id,
            "ارسال پیام با مشکل روبه‌رو شد. لطفاً کمی بعد دوباره تلاش کنید.",
            main_menu()
        )
        data["tickets"].pop(ticket_id, None)
        save_data()

    sessions.pop(str(chat_id), None)


def handle_callback(callback):
    callback_id = callback.get("id")
    callback_data = callback.get("data", "")
    message = callback.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))

    if callback_id:
        api("answerCallbackQuery", {"callback_query_id": callback_id})

    if not is_admin(chat_id):
        if chat_id:
            send(chat_id, "این دکمه فقط برای مدیر پشتیبانی است.")
        return

    if callback_data.startswith("reply:"):
        user_id = callback_data.split(":", 1)[1]
        sessions[chat_id] = {
            "mode": "admin_reply",
            "user_id": user_id
        }
        send(
            chat_id,
            "✍️ پاسخ به کاربر\n\n"
            "متن پاسخ خود را در همین گفت‌وگو بفرست.\n"
            "برای لغو، بنویسید «لغو»."
        )


def handle_message(message):
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    text = message.get("text", "").strip()

    if not chat_id:
        return

    if text == "/id":
        send(
            chat_id,
            f"شناسه این گفت‌وگو:\n{chat_id}\n\n"
            "برای تنظیم مدیر، این شناسه را در متغیر "
            "ADMIN_CHAT_ID قرار بده."
        )
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

    if session and session.get("mode") == "support":
        if text:
            handle_support_message(message, chat_id, text)
        else:
            send(
                chat_id,
                "فعلاً لطفاً پیام پشتیبانی را به‌صورت متن ارسال کن."
            )
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

        user_id = session["user_id"]
        result = send(
            user_id,
            "📬 پاسخ پشتیبانی:\n\n" + text,
            main_menu()
        )

        if result.get("ok", True):
            send(chat_id, "✅ پاسخ ارسال شد.")
        else:
            send(
                chat_id,
                "❌ ارسال پاسخ موفق نبود. ممکن است کاربر ربات را مسدود کرده باشد."
            )

        sessions.pop(chat_id, None)
        return

    if text in ("🕵️ ارتباط ناشناس با پشتیبانی", "پشتیبانی", "support"):
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
            "برای سفارش، گزینه «ثبت سفارش» را انتخاب کن.",
            main_menu()
        )
        return

    if text in ("📝 ثبت سفارش", "ثبت سفارش", "سفارش"):
        sessions[chat_id] = {"mode": "support"}
        send(
            chat_id,
            "📝 برای ثبت سفارش، نوع خدمت و توضیحات موردنظرت را بنویس.\n"
            "پیام به پشتیبانی ارسال می‌شود.\n"
            "برای لغو، بنویس «لغو».",
            main_menu()
        )
        return

    if text in ("📚 آموزش رایگان", "آموزش رایگان"):
        send(
            chat_id,
            "📚 برای دیدن آموزش‌ها و مطالب رایگان، وارد کانال خز کده شو:\n"
            + CHANNEL_URL,
            main_menu()
        )
        return

    if text in ("📢 ورود به کانال", "کانال"):
        send(
            chat_id,
            "📢 کانال خز کده:\n" + CHANNEL_URL,
            main_menu()
        )
        return

    if text in ("ℹ️ راهنما", "راهنما", "/help"):
        send(
            chat_id,
            "ℹ️ راهنمای ربات\n\n"
            "از دکمه‌های منو برای مشاهده خدمات و آموزش‌ها استفاده کن.\n"
            "برای ارسال پیام خصوصی به پشتیبانی، دکمه «ارتباط ناشناس با پشتیبانی» را بزن.\n"
            "پیام شما برای مدیر ارسال می‌شود و پاسخ از همین ربات به شما می‌رسد.",
            main_menu()
        )
        return

    if text in ("👨‍💼 مدیریت", "مدیریت"):
        if is_admin(chat_id):
            send(
                chat_id,
                "👨‍💼 پنل مدیر\n\n"
                "پیام‌های پشتیبانی به همین گفت‌وگو ارسال می‌شوند.\n"
                "برای پاسخ، دکمه «پاسخ به کاربر» زیر پیام را بزن.",
                main_menu()
            )
        else:
            send(chat_id, "این بخش مخصوص مدیر ربات است.", main_menu())
        return

    send(
        chat_id,
        "متوجه درخواستت نشدم. از دکمه‌های منو استفاده کن یا «راهنما» را بزن.",
        main_menu()
    )


def main():
    if not TOKEN:
        print("ابتدا متغیر محیطی BALE_TOKEN را تنظیم کن.")
        return

    load_data()
    print("ربات خز کده شروع به کار کرد.")

    offset = data.get("next_update_id")

    while True:
        try:
            payload = {"timeout": 25}
            if offset is not None:
                payload["offset"] = offset

            result = requests.get(
                f"{API}/getUpdates",
                params=payload,
                timeout=35
            )
            result.raise_for_status()
            response = result.json()

            if not response.get("ok", True):
                print("خطای دریافت پیام:", response)
                time.sleep(3)
                continue

            for update in response.get("result", []):
                update_id = update.get("update_id")
                if update_id is not None:
                    offset = update_id + 1
                    data["next_update_id"] = offset
                    save_data()

                if update.get("callback_query"):
                    handle_callback(update["callback_query"])
                elif update.get("message"):
                    handle_message(update["message"])

        except KeyboardInterrupt:
            print("ربات متوقف شد.")
            break
        except (requests.RequestException, ValueError, KeyError) as error:
            print("خطا:", error)
            time.sleep(3)


if __name__ == "__main__":
    main()
