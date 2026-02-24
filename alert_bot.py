import os
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from flask import Flask
import threading

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

SOURCE_CHAT = os.environ.get("SOURCE_CHAT", "solwhaletrending").lstrip("@")
DEST_CHAT = int(os.environ["DEST_CHAT"])
KEYWORD = os.environ.get("KEYWORD", "+75")

# 🔥 Web server for Railway
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is alive!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

async def run_bot():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    @client.on(events.NewMessage(chats=SOURCE_CHAT))
    async def handler(event):
        text = event.raw_text or ""
        if KEYWORD not in text:
            return
        await client.send_message(DEST_CHAT, f"🚀 ALERT from @{SOURCE_CHAT}\n\n{text}")
        print("Sent alert.")

    await client.start()
    print(f"Bot is running... Watching: {SOURCE_CHAT} | Filter: {KEYWORD}")
    await client.run_until_disconnected()

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    asyncio.run(run_bot())
