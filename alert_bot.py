import os
import re
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

# القروب/القناة العامة اللي تراقبها (بدون @)
SOURCE_CHAT = os.environ.get("SOURCE_CHAT", "inspiring-stillness")

# الخاص حقك (ID من @userinfobot)
DEST_CHAT = os.environ["DEST_CHAT"]

# فلترة بسيطة (تقدر تغيرها لاحقاً)
KEYWORD = os.environ.get("KEYWORD", "+75")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on(events.NewMessage(chats=SOURCE_CHAT))
async def handler(event):
    text = event.raw_text or ""
    if not text:
        return

    # فلترة: فقط الرسائل اللي تحتوي +75
    if KEYWORD not in text:
        return

    await client.send_message(int(DEST_CHAT), f"🚀 ALERT from {SOURCE_CHAT}\n\n{text}")
    print("Sent alert to private.")

async def main():
    await client.start()
    print("Bot is running... Watching:", SOURCE_CHAT)
    await client.run_until_disconnected()

asyncio.run(main())
