
import os
import time
import requests

TOKEN = os.getenv("BALE_TOKEN", "").strip()
API = f"https://tapi.bale.ai/bot{TOKEN}"

CHANNEL_URL = "https://ble.ir/hamegikade1"

KEYBOARD = {
    "keyboard": [
        [{"text": "🛍 خدمات"}, {"text": "📝 ثبت سفارش"}],
        [{"text": "📚 آموزش رایگان"}, {"text": "📢 کانال ما"}],
        [{"text": "👨‍💻 ارتباط با مدیر"}, {"text": "ℹ️ راهنما"}]
    ],
    "resize_keyboard": True
}

def call_api(method, data=None, timeout=40):
    response = requests.post(
        f"{API}/{method}",
        json=data or {},
        timeout=timeout
    )
    response.raise_for_status()
    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(result.get("description", "API error"))

    return result.get("result")

def send(chat_id, text, keyboard=True):
    data = {"chat_id": chat_id, "text": text}
    if keyboard:
        data["reply_markup"] = KEYBOARD
    call_api("sendMessage", data)

def handle(message):
    chat_id = message.get("chat", {}).get("id")
    text = (message.get("text") or "").strip()

    if not chat_id or not text:
        return

    if text in ("/start", "/start@HamegiKadeBot"):
        send(
            chat_id,
            "سلام! 👋 به ربات همه چی کده خوش اومدی.\n\n"
            "اینجا می‌تونی خدمات رو ببینی، درخواست ثبت کنی "
            "و به کانال ما سر بزنی."
        )

    elif text == "🛍 خدمات":
        send(
            chat_id,
            "🛍 خدمات همه چی کده\n\n"
            "💻 طراحی سایت\n"
            "⌨️ برنامه‌نویسی و کدنویسی\n"
            "🎨 ساخت تصویر با هوش مصنوعی\n"
            "✨ تولید محتوا و ابزارهای کاربردی\n\n"
            "برای ثبت درخواست، دکمه ثبت سفارش رو بزن."
        )

    elif text == "📝 ثبت سفارش":
        send(
            chat_id,
            "📝 برای ثبت درخواست، نوع خدمت و توضیحات "
            "پروژه‌ات رو در یک پیام بنویس.\n\n"
            "این نسخه درخواست رو خودکار به مدیر ارسال نمی‌کنه؛ "
            "فعلاً می‌تونی متن رو آماده کنی و از طریق کانال "
            "با مدیر هماهنگ بشی."
        )

    elif text == "📚 آموزش رایگان":
        send(
            chat_id,
            "📚 آموزش‌ها و مطالب رایگان رو در کانال ببین:\n"
            + CHANNEL_URL
        )

    elif text == "📢 کانال ما":
        send(chat_id, "📢 کانال همه چی کده:\n" + CHANNEL_URL)

    elif text == "👨‍💻 ارتباط با مدیر":
        send(
            chat_id,
            "برای ارتباط با مدیر، وارد کانال همه چی کده شو:\n"
            + CHANNEL_URL
        )

    elif text == "ℹ️ راهنما" or text == "/help":
        send(
            chat_id,
            "ℹ️ راهنمای ربات\n\n"
            "از دکمه‌های منو برای دیدن خدمات، آموزش‌ها "
            "و ثبت درخواست استفاده کن."
        )

    else:
        send(
            chat_id,
            "پیامت دریافت شد! برای استفاده از امکانات "
            "ربات، یکی از دکمه‌های منو رو انتخاب کن."
        )

def main():
    if not TOKEN:
        raise SystemExit(
            "ابتدا متغیر محیطی BALE_TOKEN را تنظیم کن."
        )

    print("در حال اتصال به بله...")
    me = call_api("getMe")
    print("ربات آماده است:", me.get("username", "OK"))

    offset = 0

    while True:
        try:
            updates = call_api(
                "getUpdates",
                {"offset": offset, "timeout": 25},
                timeout=35
            )

            for update in updates or []:
                offset = update["update_id"] + 1
                message = update.get("message")

                if message:
                    try:
                        handle(message)
                    except Exception as error:
                        print("خطای پاسخ:", error)

        except KeyboardInterrupt:
            print("ربات متوقف شد.")
            break
        except Exception as error:
            print("خطای اتصال:", error)
            time.sleep(5)

if __name__ == "__main__":
    main()
