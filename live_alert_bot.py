import os
import re
import io
import mimetypes
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

TARGET_CHAT = os.environ["TARGET_CHAT"]
SEND_TO = os.environ["SEND_TO"]
BOT_TOKEN = os.environ["BOT_TOKEN"]

VOLUME_LIMIT = int(os.environ.get("VOLUME_LIMIT", "130000"))

if TARGET_CHAT.lstrip("-").isdigit():
    TARGET_CHAT = int(TARGET_CHAT)

telethon_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient("bot_sender_session", API_ID, API_HASH)


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


def get_symbol(text):
    patterns = [
        r"\$([A-Z0-9]{2,15})",
        r"\b([A-Z0-9]{2,15})\s+is\s+up"
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return m.group(1).upper()

    return "UNKNOWN"


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
    # صورة تيليجرام العادية
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

    # ملفات أو صور مرفوعة كـ document
    if event.document:
        document = event.document
        mime_type = getattr(document, "mime_type", "") or ""
        filename = get_document_filename(document)

        file_bytes = await event.download_media(file=bytes)
        if not file_bytes:
            await bot_client.send_message(target, caption)
            return

        # إذا كان الملف صورة، نعيد رفعه كصورة وليس Download
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

        # إذا كان فيديو
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

        # أي ملف آخر
        generic_name = filename or "media.bin"
        generic_file = build_upload_file(file_bytes, generic_name)

        await bot_client.send_file(
            target,
            generic_file,
            caption=caption,
            force_document=True
        )
        return

    # لو ما فيه ميديا
    await bot_client.send_message(target, caption)


@telethon_client.on(events.NewMessage(chats=TARGET_CHAT))
async def handler(event):
    text = event.raw_text or ""

    volume = parse_volume(text)
    if not volume or volume < VOLUME_LIMIT:
        return

    symbol = get_symbol(text)

    msg = f"""🚨 Whale Alert

Token: {symbol}
Volume 1h: ${volume:,.0f}

{text}
"""

    try:
        target = int(SEND_TO) if SEND_TO.lstrip("-").isdigit() else SEND_TO

        if event.media:
            await resend_media(event, target, msg)
        else:
            await bot_client.send_message(target, msg)

        print("ALERT:", symbol, volume)

    except Exception as e:
        print("SEND ERROR:", e)


async def main():
    await bot_client.start(bot_token=BOT_TOKEN)

    me = await telethon_client.get_me()
    print("Logged in as:", me.first_name)
    print("Listening to:", TARGET_CHAT)
    print("Volume filter:", VOLUME_LIMIT)
    print("Bot sender started")


with telethon_client:
    telethon_client.loop.run_until_complete(main())
    telethon_client.run_until_disconnected()
