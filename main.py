import os
import sqlite3
from datetime import datetime, timedelta

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

# -----------------------
# ENV
# -----------------------
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# -----------------------
# DB SETUP
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

init_db()

# -----------------------
# COMMANDS
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ready. Try:\n"
        "- log: turned compost\n"
        "- remind me in 1 minute to check compost\n"
        "- summary today"
    )

# -----------------------
# LOG EVENT
# -----------------------
def log_event(text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (text, timestamp) VALUES (?, ?)",
        (text, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# -----------------------
# GET TODAY EVENTS
# -----------------------
def get_today_events():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    today = datetime.now().date().isoformat()

    c.execute("""
        SELECT text FROM events
        WHERE date(timestamp) = ?
        ORDER BY timestamp DESC
    """, (today,))

    rows = c.fetchall()
    conn.close()

    return [r[0] for r in rows]

# -----------------------
# REMINDER CALLBACK
# -----------------------
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.chat_id
    text = context.job.data
    await context.bot.send_message(chat_id=chat_id, text=f"⏰ Reminder: {text}")

# -----------------------
# PARSE REMINDER
# -----------------------
def parse_reminder(text):
    try:
        if "in" in text and "minute" in text:
            parts = text.split("in")[1].strip()
            minutes = int(parts.split("minute")[0].strip())
            message = text.split("to", 1)[1].strip()
            return minutes * 60, message
    except:
        return None, None

    return None, None

# -----------------------
# OPENAI RESPONSE
# -----------------------
def ask_openai(prompt):
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content

# -----------------------
# MAIN MESSAGE HANDLER
# -----------------------
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()

    # --- LOG ---
    if text.startswith("log:"):
        entry = text.replace("log:", "").strip()
        log_event(entry)
        await update.message.reply_text(f"Logged: {entry}")
        return

    # --- SUMMARY ---
    if "summary today" in text:
        events = get_today_events()
        if not events:
            await update.message.reply_text("Nothing logged today.")
        else:
            msg = "Today:\n" + "\n".join(f"- {e}" for e in events)
            await update.message.reply_text(msg)
        return

    # --- REMINDER ---
    if "remind me" in text:
        delay, message = parse_reminder(text)

        if delay and context.job_queue:
            context.job_queue.run_once(
                send_reminder,
                delay,
                chat_id=update.effective_chat.id,
                data=message
            )
            await update.message.reply_text(f"Reminder set: {message}")
        else:
            await update.message.reply_text("Couldn't set reminder.")
        return

    # --- DEFAULT → OPENAI ---
    try:
        reply = ask_openai(text)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# -----------------------
# MAIN
# -----------------------
def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    # handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # ✅ CRITICAL FIX (your bug)
    app.job_queue.start()

    print("Bot running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
