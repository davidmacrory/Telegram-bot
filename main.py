import os
import json
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    ContextTypes,
    filters,
)

# -----------------------
# ENV
# -----------------------
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not set")

client = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------
# DB
# -----------------------
DB_PATH = "data.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            timestamp TEXT
        )
    """)

    conn.commit()
    conn.close()

def log_event(text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "INSERT INTO events (text, timestamp) VALUES (?, ?)",
        (text, datetime.now().isoformat())
    )

    conn.commit()
    conn.close()

def get_today_events():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    today = datetime.now().date().isoformat()

    c.execute("SELECT text FROM events WHERE date(timestamp)=?", (today,))
    rows = c.fetchall()

    conn.close()
    return [r[0] for r in rows]

# -----------------------
# OPENAI INTENT PARSER
# -----------------------
def interpret(text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
You are a personal assistant.

Classify the user's message into ONE of:
- log (user did something)
- summary (user wants today's summary)
- chat (normal conversation)

Return ONLY valid JSON like:
{"type":"log","text":"turned compost"}

Rules:
- If user says they did something → log
- If asking about today → summary
- Otherwise → chat
"""
            },
            {"role": "user", "content": text}
        ],
        temperature=0
    )

    return response.choices[0].message.content

# -----------------------
# TELEGRAM HANDLER
# -----------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    try:
        result = interpret(text)
        data = json.loads(result)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    if data["type"] == "log":
        log_event(data.get("text", text))
        await update.message.reply_text(f"Logged: {data.get('text', text)}")
        return

    if data["type"] == "summary":
        events = get_today_events()

        if not events:
            await update.message.reply_text("Nothing logged today.")
            return

        msg = "Today:\n" + "\n".join(f"- {e}" for e in events)
        await update.message.reply_text(msg)
        return

    # fallback chat
    await update.message.reply_text("Got it 👍")

# -----------------------
# MAIN
# -----------------------
def main():
    init_db()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
