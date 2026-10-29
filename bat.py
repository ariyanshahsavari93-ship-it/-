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
data = {"next_update_id": None, "tickets": {}}


def load_data():
    global data

    try:
        if DATA_FILE.exists():
            loaded = json.loads(
                DATA_FILE.read_text(encoding="utf-8")
            )

            if isinstance(loaded, dict):
                data.update(loaded)

        if not isinstance(data.get("tickets"), dict):
            data["tickets"] = {}

    except (OSError, json.JSONDecodeError) as error:
        print("خطا در خواندن اطلاعات:", error)


def save_data():
    try:
        DATA_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except OSError as error:
        print("خطا در ذخیره اطلاعات:", error)


def api(method, payload=None):
    if not TOKEN:
        print("خطا: متغیر BALE_TOKEN تنظیم نشده است.")
        return {}

    try:
        response = requests.post(
            f"{API}/{method}",
            json=payload or {},
            timeout=40
        )
        response.raise_for_status()
        result = response.json()

        if not isinstance(result, dict):
            return {}

        if result.get("ok") is not True:
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
            [
                {"text": "🛠 خدمات"},
                {"text": "📝 ثبت سفارش"}
            ],
            [
                {"text": "📚 آموزش رایگان"},
                {"text": "📢 ورود به کانال"}
            ],
            [
                {"text": "🕵️ ارتباط ناشناس با پشتیبانی"}
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
        instruction = (
            "نوع خدمت و توضیحات سفارش خود را بنویس.\n"
            "پیام به پشتیبانی ارسال می‌شود."
        )
    else:
        title = "🕵️ ارتباط ناشناس با پشتیبانی"
        instruction = (
            "پیام خود را ارسال کنید؛ این پیام به پشتیبانی "
            "ارسال می‌شود.\n"
            "هویت شما در متن پیام نمایش داده نمی‌شود؛ "
            "ربات برای ارسال پاسخ باید شناسه گفت‌وگوی شما را نگه دارد."
        )

    send(
        chat_id,
        f"{title}\n\n{instruction}\n\n"
        "برای لغو، بنویسید «لغو».",
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

    keyboard = {
        "inline_keyboard": [[
            {
                "text": "↩️ پاسخ به کاربر",
                "callback_data": f"reply:{ticket_id}"
            }
        ]]
    }

    result = send(ADMIN_ID, admin_text, keyboard)

    if result.get("ok") is True:
        send(
            chat_id,
            "✅ پیام شما برای پشتیبانی ارسال شد.\n"
            f"شماره پیگیری: {ticket_id}\n"
            "پاسخ پشتیبانی در همین گفت‌وگو ارسال می‌شود.",
            main_menu()
        )
        sessions.pop(str(chat_id), None)
    else:
        data["tickets"].pop(ticket_id, None)
        save_data()
        send(
            chat_id,
            "❌ ارسال پیام موفق نبود. لطفاً کمی بعد دوباره تلاش کنید.",
            main_menu()
        )


def handle_callback(callback):
    callback_id = callback.get("id")
    callback_data = callback.get("data", "")
    message = callback.get("message") or {}
    chat_id = str((message.get("chat") or {}).get("id", ""))

    if callback_id:
        api(
            "answerCallbackQuery",
            {"callback_query_id": callback_id}
        )

    if not is_admin(chat_id):
        if chat_id:
            send(chat_id, "این دکمه فقط برای مدیر پشتیبانی است.")
        return

    if not callback_data.startswith("reply:"):
        return

    ticket_id = callback_data.split(":", 1)[1]
    ticket = data["tickets"].get(ticket_id)

    if not ticket:
        send(chat_id, "این درخواست پیدا نشد یا اطلاعات آن موجود نیست.")
        return

    sessions[chat_id] = {
        "mode": "admin_reply",
        "ticket_id": ticket_id
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
            "این شناسه را در متغیر ADMIN_CHAT_ID تنظیم کن."
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
            send(chat_id, "لطفاً پاسخ را به‌صورت متن ارسال کن.")
            return

        ticket_id = session.get("ticket_id")
        ticket = data["tickets"].get(ticket_id)

        if not ticket:
            sessions.pop(chat_id, None)
            send(chat_id, "درخواست پیدا نشد.")
            return

        user_id = ticket.get("user_id")

        result = send(
            user_id,
            "📬 پاسخ پشتیبانی:\n\n" + text,
            main_menu()
        )

        if result.get("ok") is True:
            ticket["status"] = "answered"
            save_data()
            send(chat_id, "✅ پاسخ ارسال شد.")
        else:
            send(
                chat_id,
                "❌ ارسال پاسخ موفق نبود. ممکن است کاربر ربات را مسدود کرده باشد."
            )

        sessions.pop(chat_id, None)
        return

    if text in (
        "🕵️ ارتباط ناشناس با پشتیبانی",
        "پشتیبانی",
        "support"
    ):
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
            "📢 کانال خز کده:\n" + CHANNEL_URL,
            main_menu()
        )
        return

    if text in ("ℹ️ راهنما", "راهنما", "/help"):
        send(
            chat_id,
            "ℹ️ راهنمای ربات\n\n"
            "از دکمه‌های منو استفاده کن.\n"
            "برای ارتباط با پشتیبانی، گزینه ارتباط ناشناس را بزن.\n"
            "برای لغو پیام پشتیبانی، بنویس «لغو».",
            main_menu()
        )
        return

    if text in ("👨‍💼 مدیریت", "مدیریت"):
        if is_admin(chat_id):
            send(
                chat_id,
                "👨‍💼 پنل مدیر\n\n"
                "پیام‌های پشتیبانی به این گفت‌وگو ارسال می‌شوند.\n"
                "برای پاسخ، دکمه «پاسخ به کاربر» را بزن.",
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
        print("خطا: متغیر BALE_TOKEN تنظیم نشده است.")
        return

    if not ADMIN_ID:
        print("هشدار: متغیر ADMIN_CHAT_ID تنظیم نشده است.")

    load_data()
    print("ربات خز کده شروع به کار کرد.")

    offset = data.get("next_update_id")

    while True:
        try:
            payload = {"timeout": 25}

            if offset is not None:
                payload["offset"] = offset

            response = requests.get(
                f"{API}/getUpdates",
                params=payload,
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
        except Exception as error:
            print("خطای پیش‌بینی‌نشده:", error)
            time.sleep(3)


if __name__ == "__main__":
    main()
