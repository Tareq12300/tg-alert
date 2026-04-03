import os
import re
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

TARGET_CHAT = os.environ["TARGET_CHAT"]
SEND_TO = os.environ["SEND_TO"]
VOLUME_LIMIT = int(os.environ.get("VOLUME_LIMIT", "130000"))

if TARGET_CHAT.lstrip("-").isdigit():
    TARGET_CHAT = int(TARGET_CHAT)

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)


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


@client.on(events.NewMessage(chats=TARGET_CHAT))
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
        entity = await client.get_entity(int(SEND_TO))

        if event.media:
            await client.send_file(
                entity,
                event.media,
                caption=msg
            )
        else:
            await client.send_message(entity, msg)

        print("ALERT:", symbol, volume)

    except Exception as e:
        print("SEND ERROR:", e)


async def main():
    me = await client.get_me()
    print("Logged in as:", me.first_name)
    print("Listening to:", TARGET_CHAT)
    print("Volume filter:", VOLUME_LIMIT)


with client:
    client.loop.run_until_complete(main())
    client.run_until_disconnected()
