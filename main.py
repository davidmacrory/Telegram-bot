from dotenv import load_dotenv
load_dotenv()
import os
import re
import sqlite3
from datetime import datetime

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# =========================
# ENV VARIABLES (LOCKED)
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # not used yet, but valid

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set")

# =========================
# DATABASE
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
        ORDER BY timestamp ASC
    """, (today,))

    rows = c.fetchall()
    conn.close()

    return [r[0] for r in rows]

# =========================
# REMINDER CALLBACK
# =========================
async def reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"⏰ Reminder: {job.data}"
    )

def parse_reminder(text):
    match = re.search(r"in (\d+) minute", text.lower())
    if not match:
        return None, None

    minutes = int(match.group(1))
    message = text.lower().split("to", 1)[-1].strip()

    return minutes * 60, message

# =========================
# HANDLERS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Ready.\n"
        "Try:\n"
        "- log: turned compost\n"
        "- remind me in 1 minute to check compost\n"
        "- summary today"
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # LOG
    if text.lower().startswith("log:"):
        entry = text.split("log:", 1)[1].strip()
        log_event(entry)
        await update.message.reply_text(f"Logged: {entry}")
        return

    # SUMMARY
    if "summary today" in text.lower():
        events = get_today_events()

        if not events:
            await update.message.reply_text("Nothing logged today.")
        else:
            msg = "Today:\n" + "\n".join(f"- {e}" for e in events)
            await update.message.reply_text(msg)

        return

    # REMINDER
    if "remind me" in text.lower():
        try:
            delay, message = parse_reminder(text)

            if delay is None:
                await update.message.reply_text(
                    "Format: remind me in X minutes to do something"
                )
                return

            job_queue = context.application.job_queue

            if job_queue is None:
                print("ERROR: JobQueue missing")
                await update.message.reply_text("Reminder system unavailable ❌")
                return

            job_queue.run_once(
                reminder_callback,
                delay,
                chat_id=update.effective_chat.id,
                data=message,
            )

            await update.message.reply_text("Reminder set 👍")

        except Exception as e:
            print(f"REMINDER ERROR: {e}")
            await update.message.reply_text(f"Error: {e}")

        return

    # DEFAULT
    await update.message.reply_text("Try: log:, remind me, summary today")

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
