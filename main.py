import os
import json
import re
import sqlite3
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# ENV
# =========================
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# =========================
# DB
# =========================
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
        (text, datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()

def get_today_events():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    today = datetime.now().date().isoformat()

    c.execute("""
        SELECT text FROM events
        WHERE date(timestamp) = ?
    """, (today,))

    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

# =========================
# OPENAI INTENT PARSER
# =========================
def interpret(text):
    prompt = f"""
Classify this message into JSON:

Possible intents:
- log
- reminder
- summary
- chat

Respond ONLY with JSON like:
{{"intent": "...", "content": "..."}}

Message: {text}
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )

    raw = response.choices[0].message.content

    try:
        return json.loads(raw)
    except:
        return {"intent": "chat", "content": text}

# =========================
# REMINDER
# =========================
async def reminder_callback(context):
    job = context.job
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"⏰ Reminder: {job.data}"
    )

def extract_minutes(text):
    match = re.search(r"(\d+)\s*minute", text.lower())
    if match:
        return int(match.group(1))
    return 1

# =========================
# HANDLER
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    result = interpret(text)
    intent = result.get("intent")
    content = result.get("content", text)

    # LOG
    if intent == "log":
        log_event(content)
        await update.message.reply_text(f"Logged: {content}")
        return

    # SUMMARY
    if intent == "summary":
        events = get_today_events()
        if not events:
            await update.message.reply_text("Nothing today.")
        else:
            msg = "Today:\n" + "\n".join(f"- {e}" for e in events)
            await update.message.reply_text(msg)
        return

    # REMINDER
    if intent == "reminder":
        minutes = extract_minutes(text)

        job_queue = context.application.job_queue

        if job_queue is None:
            await update.message.reply_text("Reminder system unavailable ❌")
            return

        job_queue.run_once(
            reminder_callback,
            minutes * 60,
            chat_id=update.effective_chat.id,
            data=content,
        )

        await update.message.reply_text(f"Reminder set for {minutes} min 👍")
        return

    # DEFAULT CHAT (OpenAI)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": text}],
    )

    reply = response.choices[0].message.content
    await update.message.reply_text(reply)

# =========================
# START
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ready. Just talk normally 👍")

# =========================
# MAIN
# =========================
def main():
    init_db()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
