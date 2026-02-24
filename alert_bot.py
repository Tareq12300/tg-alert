import os
import time
from telethon import TelegramClient
from telethon.sessions import StringSession

# اقرأ المتغيرات من Railway Variables
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
SOURCE_CHAT = os.getenv("SOURCE_CHAT", "")     # مثال: soul_scanner_official أو رابط/ID
DEST_CHAT = os.getenv("DEST_CHAT", "")         # مثال: @mychannel أو ID

if API_ID == 0 or not API_HASH or not SESSION_STRING:
    raise SystemExit("Missing API_ID / API_HASH / SESSION_STRING in environment variables")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

@client.on_new_message(chats=lambda e: True)
async def handler(event):
    # فلترة بسيطة: إذا حددت SOURCE_CHAT نراقبه فقط
    if SOURCE_CHAT and str(event.chat_id) != str(SOURCE_CHAT) and (getattr(event.chat, "username", "") != SOURCE_CHAT.lstrip("@")):
        return

    text = event.raw_text or ""
    if not text:
        return

    # فلترة +75 (اختياري)
    if "+75" not in text:
        return

    if not DEST_CHAT:
        print("DEST_CHAT not set. Message:", text[:100])
        return

    await client.send_message(DEST_CHAT, text)
    print("Forwarded message to DEST_CHAT")

async def main():
    await client.start()
    print("Bot is running...")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
