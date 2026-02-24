import os
import re
import asyncio
import threading
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from flask import Flask

# ==============================
# 🔹 ENV VARIABLES
# ==============================

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_STRING = os.environ["SESSION_STRING"]

SOURCE_CHAT = os.environ["SOURCE_CHAT"].lstrip("@")
DEST_CHAT = int(os.environ["DEST_CHAT"])

STRONG_THRESHOLD = int(os.environ.get("STRONG_THRESHOLD", 75))
ELITE_THRESHOLD = int(os.environ.get("ELITE_THRESHOLD", 80))

# ==============================
# 🔹 FLASK APP (For gunicorn)
# ==============================

app = Flask(__name__)

@app.route("/")
def home():
    return "alive", 200

# ==============================
# 🔹 UTILS
# ==============================

def extract_number(pattern, text):
    match = re.search(pattern, text)
    if match:
        return float(match.group(1).replace(",", ""))
    return None

already_sent = set()

# ==============================
# 🔹 TELEGRAM BOT
# ==============================

async def run_bot():

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    @client.on(events.NewMessage(chats=SOURCE_CHAT))
    async def handler(event):

        text = event.raw_text or ""

        if event.id in already_sent:
            return

        mc = extract_number(r'MC:\s*\$([\d,]+)', text)
        vol = extract_number(r'Vol:\s*\$([\d,]+)', text)
        holders = extract_number(r'Hodls?:\s*(\d+)', text)
        fake = extract_number(r'Fake:.*?\[(\d+)', text)
        bundles = extract_number(r'Bundles:.*?•\s*(\d+)', text)
        dev = extract_number(r'Dev:.*?\|\s*(\d+)', text)

        score = 0

        if mc and 70000 <= mc <= 130000:
            score += 20

        if vol and vol > 100000:
            score += 25

        if holders and holders > 500:
            score += 15

        if fake is not None and fake <= 2:
            score += 15

        if bundles is not None and bundles < 20:
            score += 15

        if dev is not None and dev == 0:
            score += 10

        if score >= ELITE_THRESHOLD:
            label = "🔥 ELITE SETUP"
        elif score >= STRONG_THRESHOLD:
            label = "🟢 STRONG SETUP"
        else:
            return

        already_sent.add(event.id)

        await client.send_message(
            DEST_CHAT,
            f"{label} ({score}/100)\n\n{text}"
        )

        print(f"Sent {label} ({score})")

    await client.start()
    print("Telegram connected successfully")
    print(f"Bot running | Watching: {SOURCE_CHAT}")

    await client.run_until_disconnected()

# ==============================
# 🔹 BACKGROUND THREAD
# ==============================

def start_bot():
    while True:
        try:
            asyncio.run(run_bot())
        except Exception as e:
            print("Bot crashed. Restarting in 10 seconds...")
            print("Error:", e)
            asyncio.sleep(10)

# ==============================
# 🔹 START BOT THREAD
# ==============================

threading.Thread(target=start_bot, daemon=True).start()
