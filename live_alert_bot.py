import os
import re
import io
import mimetypes
import asyncio
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
HOLDERS_LIMIT = int(os.environ.get("HOLDERS_LIMIT", "600"))
MC_LIMIT = int(os.environ.get("MC_LIMIT", "90000"))
TRACK_HOURS = int(os.environ.get("TRACK_HOURS", "8760"))

# وقت التقرير اليومي بتوقيت UTC
REPORT_HOUR_UTC = int(os.environ.get("REPORT_HOUR_UTC", "21"))
REPORT_MINUTE_UTC = int(os.environ.get("REPORT_MINUTE_UTC", "0"))

if TARGET_CHAT.lstrip("-").isdigit():
    TARGET_CHAT = int(TARGET_CHAT)

telethon_client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
bot_client = TelegramClient("bot_sender_session", API_ID, API_HASH)

# العملات التي تم إرسالها سابقًا لمتابعة is up
alerted_tokens = {}

# إحصائيات اليوم
daily_stats = {
    "date": None,
    "entries": {},   # symbol -> {volume, holders, mc, entry_time}
    "updates": {},   # symbol -> best_x
    "best_symbol": None,
    "best_x": 0.0
}


def utc_now():
    return datetime.now(timezone.utc)


def ensure_daily_reset():
    today = utc_now().date().isoformat()
    if daily_stats["date"] != today:
        daily_stats["date"] = today
        daily_stats["entries"] = {}
        daily_stats["updates"] = {}
        daily_stats["best_symbol"] = None
        daily_stats["best_x"] = 0.0


def parse_money(x):
    if not x:
        return None

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


def parse_mc(text):
    patterns = [
        r"MC:\s*\$?([0-9\.,]+[KMB]?)",
        r"Market Cap:\s*\$?([0-9\.,]+[KMB]?)"
    ]

    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return parse_money(m.group(1))

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
    m = re.search(
        r"\b([A-Z0-9]{2,20})\s+is\s+up\s+([0-9\.]+)\s*(%|X)\b",
        text,
        re.IGNORECASE
    )
    if not m:
        return None

    return {
        "symbol": m.group(1).upper(),
        "value": float(m.group(2)),
        "unit": m.group(3).upper()
    }


def up_to_x(value, unit):
    if unit == "X":
        return float(value)
    if unit == "%":
        return 1 + (float(value) / 100.0)
    return 0.0


def parse_mc_range(text):
    m = re.search(r"\$([0-9\.,]+[KMB]?)\s*[—\-–>]+\s*\$([0-9\.,]+[KMB]?)", text)
    if not m:
        return None

    return m.group(1), m.group(2)


def cleanup_old_tokens():
    now = utc_now()
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


def register_entry(symbol, volume, holders, mc):
    ensure_daily_reset()

    if symbol not in daily_stats["entries"]:
        daily_stats["entries"][symbol] = {
            "volume": volume,
            "holders": holders,
            "mc": mc,
            "entry_time": utc_now().isoformat()
        }


def register_update(symbol, x_value):
    ensure_daily_reset()

    current_best = daily_stats["updates"].get(symbol, 0.0)
    if x_value > current_best:
        daily_stats["updates"][symbol] = x_value

    if x_value > daily_stats["best_x"]:
        daily_stats["best_x"] = x_value
        daily_stats["best_symbol"] = symbol


def build_daily_report():
    ensure_daily_reset()

    total_entries = len(daily_stats["entries"])
    total_updates = len(daily_stats["updates"])

    x_values = list(daily_stats["updates"].values())
    avg_x = sum(x_values) / len(x_values) if x_values else 0.0

    x2_count = sum(1 for x in x_values if x >= 2.0)
    x3_count = sum(1 for x in x_values if x >= 3.0)
    x5_count = sum(1 for x in x_values if x >= 5.0)
    x10_count = sum(1 for x in x_values if x >= 10.0)

    best_symbol = daily_stats["best_symbol"] or "-"
    best_x = daily_stats["best_x"]

    report = f"""📊 Daily Report

Date: {daily_stats["date"]}

Total alerted tokens: {total_entries}
Tokens with updates: {total_updates}
Average result: {avg_x:.2f}X

Best token: {best_symbol}
Best result: {best_x:.2f}X

2X+ tokens: {x2_count}
3X+ tokens: {x3_count}
5X+ tokens: {x5_count}
10X+ tokens: {x10_count}
"""
    return report


async def daily_report_loop():
    while True:
        now = utc_now()
        target_time = now.replace(
            hour=REPORT_HOUR_UTC,
            minute=REPORT_MINUTE_UTC,
            second=0,
            microsecond=0
        )

        if now >= target_time:
            target_time += timedelta(days=1)

        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)

        try:
            target = int(SEND_TO) if SEND_TO.lstrip("-").isdigit() else SEND_TO
            report = build_daily_report()
            await bot_client.send_message(target, report)
            print("DAILY REPORT SENT")
        except Exception as e:
            print("DAILY REPORT ERROR:", e)

        daily_stats["date"] = None
        ensure_daily_reset()


@telethon_client.on(events.NewMessage(chats=TARGET_CHAT))
async def handler(event):
    ensure_daily_reset()
    cleanup_old_tokens()

    text = event.raw_text or ""
    target = int(SEND_TO) if SEND_TO.lstrip("-").isdigit() else SEND_TO

    try:
        volume = parse_volume(text)
        symbol = get_symbol(text)
        holders = parse_holders(text)
        mc = parse_mc(text)

        # Entry alert
        if (
            volume
            and volume >= VOLUME_LIMIT
            and symbol
            and holders is not None
            and holders <= HOLDERS_LIMIT
            and mc is not None
            and mc <= MC_LIMIT
        ):
            msg = f"""🚨 Whale Alert

Token: {symbol}
Volume 1h: ${volume:,.0f}
Holders: {holders}
MC: ${mc:,.0f}

{text}
"""

            if event.media:
                await resend_media(event, target, msg)
            else:
                await bot_client.send_message(target, msg)

            alerted_tokens[symbol] = utc_now()
            register_entry(symbol, volume, holders, mc)

            print("ENTRY ALERT:", symbol, volume, "holders=", holders, "mc=", mc)
            return

        # Follow-up alert
        up_data = parse_up_signal(text)
        if up_data:
            up_symbol = up_data["symbol"]

            if up_symbol in alerted_tokens:
                mc_range = parse_mc_range(text)
                x_value = up_to_x(up_data["value"], up_data["unit"])
                register_update(up_symbol, x_value)

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
    print("MC max:", MC_LIMIT)
    print("Track hours:", TRACK_HOURS)
    print("Daily report UTC:", f"{REPORT_HOUR_UTC:02d}:{REPORT_MINUTE_UTC:02d}")
    print("Bot sender started")

    telethon_client.loop.create_task(daily_report_loop())


with telethon_client:
    telethon_client.loop.run_until_complete(main())
    telethon_client.run_until_disconnected()
