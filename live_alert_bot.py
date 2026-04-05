import os
import re
import io
import mimetypes
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

TARGET_CHAT = os.environ["TARGET_CHAT"]
SEND_TO = os.environ["SEND_TO"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

VOLUME_LIMIT = int(os.environ.get("VOLUME_LIMIT", "130000"))
TRACK_HOURS = int(os.environ.get("TRACK_HOURS", "24"))
HOLDERS_LIMIT = int(os.environ.get("HOLDERS_LIMIT", "600"))

if TARGET_CHAT.lstrip("-").isdigit():
    TARGET_CHAT = int(TARGET_CHAT)

telethon_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient("bot_sender_session", API_ID, API_HASH)

# نخزن العملات التي تم إرسال تنبيه دخول لها
alerted_tokens = {}


def parse_money(x):
    x = x.replace(",", "").replace("$", "").strip().upper()

    mult = 1
    if x.endswith("K"):
        mult = 1000
        x = x[:-1]
    elif x.endswith("M"):
        mult = 1000000
        x = x[:-1]
    elif x.endswith("B"):
        mult = 1000000000
        x = x[:-1]

    try:
        return float(x) * mult
    except:
        return None


def parse_volume(text):
    patterns = [
        r"Vol:\s*\$?([0-9\.,]+[KMB]?)\s*\[1h\]",
        r"Volume:\s*\$?([0-9\.,]+[KMB]?)",
        r"Vol:\s*\$?([0-9\.,]+[KMB]?)"
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return parse_money(m.group(1))

    return None


def parse_holders(text):
    patterns = [
        r"Hodls:\s*([0-9,]+)",
        r"Holds:\s*([0-9,]+)"
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return int(m.group(1).replace(",", ""))

    return None


def get_symbol(text):
    patterns = [
        r"\$([A-Z0-9]{2,20})\b",
        r"\b([A-Z0-9]{2,20})\s+is\s+up\b"
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()

    return None


def parse_up_signal(text):
    m = re.search(r"\b([A-Z0-9]{2,20})\s+is\s+up\s+([0-9\.]+)\s*(%|X)\b", text, re.IGNORECASE)
    if not m:
        return None

    symbol = m.group(1).upper()
    value = m.group(2)
    unit = m.group(3).upper()

    return {
        "symbol": symbol,
        "value": value,
        "unit": unit
    }


def parse_mc_range(text):
    m = re.search(r"\$([0-9\.,]+[KMB]?)\s*[—\-–>]+\s*\$([0-9\.,]+[KMB]?)", text)
    if not m:
        return None

    start_mc = m.group(1)
    end_mc = m.group(2)
    return start_mc, end_mc


def cleanup_old_tokens():
    now = datetime.now(timezone.utc)
    expired = []

    for symbol, dt in alerted_tokens.items():
        if now - dt > timedelta(hours=TRACK_HOURS):
            expired.append(symbol)

    for symbol in expired:
        del alerted_tokens[symbol]


def get_document_filename(document):
    if not document:
        return None

    for attr in getattr(document, "attributes", []):
        if hasattr(attr, "file_name") and attr.file_name:
            return attr.file_name

    return None


def build_upload_file(file_bytes, filename):
    bio = io.BytesIO(file_bytes)
    bio.name = filename
    return bio


async def resend_media(event, target, caption):
    if event.photo:
        file_bytes = await event.download_media(file=bytes)
        if not file_bytes:
            await bot_client.send_message(target, caption)
            return

        photo_file = build_upload_file(file_bytes, "image.jpg")
        await bot_client.send_file(
            target,
            photo_file,
            caption=caption,
            force_document=False
        )
        return

    if event.document:
        document = event.document
        mime_type = getattr(document, "mime_type", "") or ""
        filename = get_document_filename(document)

        file_bytes = await event.download_media(file=bytes)
        if not file_bytes:
            await bot_client.send_message(target, caption)
            return

        if mime_type.startswith("image/"):
            ext = mimetypes.guess_extension(mime_type) or ".jpg"
            image_name = filename or f"image{ext}"
            image_file = build_upload_file(file_bytes, image_name)

            await bot_client.send_file(
                target,
                image_file,
                caption=caption,
                force_document=False
            )
            return

        if mime_type.startswith("video/"):
            ext = mimetypes.guess_extension(mime_type) or ".mp4"
            video_name = filename or f"video{ext}"
            video_file = build_upload_file(file_bytes, video_name)

            await bot_client.send_file(
                target,
                video_file,
                caption=caption,
                supports_streaming=True,
                force_document=False
            )
            return

        generic_name = filename or "media.bin"
        generic_file = build_upload_file(file_bytes, generic_name)

        await bot_client.send_file(
            target,
            generic_file,
            caption=caption,
            force_document=True
        )
        return

    await bot_client.send_message(target, caption)


@telethon_client.on(events.NewMessage(chats=TARGET_CHAT))
async def handler(event):
    cleanup_old_tokens()

    text = event.raw_text or ""
    target = int(SEND_TO) if SEND_TO.lstrip("-").isdigit() else SEND_TO

    try:
        # 1) تنبيه الدخول الأساسي
        volume = parse_volume(text)
        symbol = get_symbol(text)
        holders = parse_holders(text)

        if volume and volume >= VOLUME_LIMIT and symbol and holders is not None and holders <= HOLDERS_LIMIT:
            msg = f"""🚨 Whale Alert

Token: {symbol}
Volume 1h: ${volume:,.0f}
Holders: {holders}

{text}
"""

            if event.media:
                await resend_media(event, target, msg)
            else:
                await bot_client.send_message(target, msg)

            alerted_tokens[symbol] = datetime.now(timezone.utc)
            print("ENTRY ALERT:", symbol, volume, "holders=", holders)
            return

        # 2) تنبيه الارتفاع لنفس العملة إذا كانت أرسلت سابقًا
        up_data = parse_up_signal(text)
        if up_data:
            up_symbol = up_data["symbol"]

            if up_symbol in alerted_tokens:
                mc_range = parse_mc_range(text)

                extra_line = ""
                if mc_range:
                    extra_line = f"\nMC: ${mc_range[0]} -> ${mc_range[1]}\n"

                growth_msg = f"""📈 Follow-Up Alert

Token: {up_symbol}
Move: {up_data["value"]}{up_data["unit"]}{extra_line}
{text}
"""

                if event.media:
                    await resend_media(event, target, growth_msg)
                else:
                    await bot_client.send_message(target, growth_msg)

                print("UP ALERT:", up_symbol, up_data["value"], up_data["unit"])
                return

    except Exception as e:
        print("SEND ERROR:", e)


async def main():
    await bot_client.start(bot_token=BOT_TOKEN)

    me = await telethon_client.get_me()
    print("Logged in as:", me.first_name)
    print("Listening to:", TARGET_CHAT)
    print("Volume filter:", VOLUME_LIMIT)
    print("Holders max:", HOLDERS_LIMIT)
    print("Track hours:", TRACK_HOURS)
    print("Bot sender started")


with telethon_client:
    telethon_client.loop.run_until_complete(main())
    telethon_client.run_until_disconnected()
