import os
import re
import sqlite3
from datetime import datetime, timedelta, time

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

# --- LOAD ENV ---
load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# --- DB SETUP ---
DB_PATH = "memory.db"

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    text TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()


# --- HELPERS ---

def log_event(text):
    c.execute("INSERT INTO events (text, timestamp) VALUES (?, ?)", (text, datetime.now()))
    conn.commit()


def get_today_summary():
    today = datetime.now().date()
    c.execute("SELECT text FROM events WHERE DATE(timestamp) = ?", (today,))
    rows = c.fetchall()
    if not rows:
        return "Nothing logged today."
    return "Today:\n" + "\n".join(f"- {r[0]}" for r in rows)


def parse_reminder(text):
    match = re.search(r"remind me in (\d+) minute[s]? to (.+)", text.lower())
    if match:
        return int(match.group(1)), match.group(2)
    return None, None


# --- REMINDER JOB ---
async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job = context.job
    await context.bot.send_message(
        chat_id=job.chat_id,
        text=f"⏰ Reminder: {job.data}"
    )


# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Ready. Try: log: turned compost")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    # --- LOG ---
    if text.lower().startswith("log:"):
        entry = text[4:].strip()
        log_event(entry)
        await update.message.reply_text(f"Logged: {entry}")
        return

    # --- SUMMARY ---
    if text.lower() == "summary today":
        summary = get_today_summary()
        await update.message.reply_text(summary)
        return

    # --- REMINDER ---
    minutes, task = parse_reminder(text)
    if minutes:
        context.job_queue.run_once(
            send_reminder,
            when=timedelta(minutes=minutes),
            chat_id=update.effective_chat.id,
            data=task
        )
        await update.message.reply_text(f"Reminder set for {minutes} min: {task}")
        return

    # --- DEFAULT ---
    await update.message.reply_text("Try: log:, remind me, summary today")


# --- MAIN ---

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
