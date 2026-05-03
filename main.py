import os
import json
import sqlite3
import re
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
# REMINDER PARSER
# -----------------------
def parse_reminder(text):
    match = re.search(r"remind me in (\d+) (minute|minutes|hour|hours)", text.lower())
    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    seconds = value * 60 if "minute" in unit else value * 3600
    return seconds

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(
        chat_id=context.job.chat_id,
        text=context.job.data
    )

# -----------------------
# OPENAI INTENT
# -----------------------
def interpret(text):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": """
Classify:
- log
- summary
- chat

Return JSON:
{"type":"log","text":"..."}
"""
            },
            {"role": "user", "content": text}
        ],
        temperature=0
    )

    return json.loads(response.choices[0].message.content)

# -----------------------
# HANDLER
# -----------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # 🔔 Reminder first (no AI needed)
    seconds = parse_reminder(text)
    if seconds:
        context.job_queue.run_once(
            send_reminder,
            seconds,
            chat_id=update.effective_chat.id,
            data=text
        )
        await update.message.reply_text("Reminder set ⏰")
        return

    # 🤖 AI interpretation
    try:
        result = interpret(text)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return

    if result["type"] == "log":
        log_event(result.get("text", text))
        await update.message.reply_text(f"Logged: {result.get('text', text)}")
        return

    if result["type"] == "summary":
        events = get_today_events()

        if not events:
            await update.message.reply_text("Nothing logged today.")
            return

        msg = "Today:\n" + "\n".join(f"- {e}" for e in events)
        await update.message.reply_text(msg)
        return

    await update.message.reply_text("👍")

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
