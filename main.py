import os
import re
import sqlite3
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# -----------------------
# ENV SETUP
# -----------------------
BASE_DIR = Path("/config/Telegram-bot")
ENV_PATH = BASE_DIR / ".env"

if not ENV_PATH.exists():
    raise FileNotFoundError(f".env file not found at {ENV_PATH}")

load_dotenv(dotenv_path=ENV_PATH)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN in .env")

DB_PATH = BASE_DIR / "data.db"


# -----------------------
# DATABASE
# -----------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT,
        timestamp DATETIME
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        text TEXT,
        due DATETIME,
        sent INTEGER DEFAULT 0
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY
    )
    """)

    conn.commit()
    conn.close()


def save_user(chat_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (chat_id) VALUES (?)", (chat_id,))
    conn.commit()
    conn.close()


def get_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT chat_id FROM users")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users


def add_event(text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO events (text, timestamp) VALUES (?, ?)",
              (text, datetime.now()))
    conn.commit()
    conn.close()


def get_last_event(keyword):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT text, timestamp FROM events
        WHERE text LIKE ?
        ORDER BY timestamp DESC
        LIMIT 1
    """, (f"%{keyword}%",))
    row = c.fetchone()
    conn.close()
    return row


def get_events_since(hours):
    since = datetime.now() - timedelta(hours=hours)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT text FROM events
        WHERE timestamp >= ?
        ORDER BY timestamp DESC
    """, (since,))
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows


def add_reminder(text, due):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO reminders (text, due) VALUES (?, ?)", (text, due))
    conn.commit()
    conn.close()


def get_due_reminders():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, text FROM reminders
        WHERE due <= ? AND sent = 0
    """, (datetime.now(),))
    rows = c.fetchall()
    conn.close()
    return rows


def mark_reminder_sent(reminder_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE reminders SET sent = 1 WHERE id = ?", (reminder_id,))
    conn.commit()
    conn.close()


# -----------------------
# HANDLERS
# -----------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_user(chat_id)
    await update.message.reply_text("Ready. Try: log: turned compost")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_user(chat_id)

    text = update.message.text.lower()

    # LOG
    if text.startswith("log:"):
        entry = text.replace("log:", "").strip()
        add_event(entry)
        await update.message.reply_text(f"Logged: {entry}")
        return

    # LAST EVENT
    if text.startswith("when did i last"):
        keyword = text.replace("when did i last", "").strip()
        result = get_last_event(keyword)

        if result:
            await update.message.reply_text(f"{result[1]}")
        else:
            await update.message.reply_text("No record found")
        return

    # REMINDER
    match = re.search(r"remind me in (\d+) (day|days|hour|hours) to (.+)", text)
    if match:
        amount = int(match.group(1))
        unit = match.group(2)
        reminder_text = match.group(3)

        due = datetime.now() + (
            timedelta(days=amount) if "day" in unit else timedelta(hours=amount)
        )

        add_reminder(reminder_text, due)
        await update.message.reply_text(f"Reminder set: {reminder_text}")
        return

    # SUMMARY TODAY
    if "summary today" in text:
        events = get_events_since(24)
        msg = "Today:\n" + "\n".join(f"- {e}" for e in events) if events else "No activity"
        await update.message.reply_text(msg)
        return

    # SUMMARY WEEK
    if "summary week" in text:
        events = get_events_since(168)
        msg = "This week:\n" + "\n".join(f"- {e}" for e in events) if events else "No activity"
        await update.message.reply_text(msg)
        return

    await update.message.reply_text("Try: log:, remind me, summary today")


# -----------------------
# BACKGROUND TASKS
# -----------------------
async def reminder_loop(app):
    while True:
        reminders = get_due_reminders()
        users = get_users()

        for rid, text in reminders:
            for user in users:
                await app.bot.send_message(chat_id=user, text=f"Reminder: {text}")
            mark_reminder_sent(rid)

        await asyncio.sleep(60)


async def summary_loop(app):
    while True:
        now = datetime.now()
        users = get_users()

        # DAILY 19:00
        if now.hour == 19 and now.minute == 0:
            events = get_events_since(24)
            if events:
                msg = "Daily summary:\n" + "\n".join(f"- {e}" for e in events)
                for u in users:
                    await app.bot.send_message(chat_id=u, text=msg)

        # WEEKLY Sunday 19:00
        if now.weekday() == 6 and now.hour == 19 and now.minute == 0:
            events = get_events_since(168)
            if events:
                msg = "Weekly summary:\n" + "\n".join(f"- {e}" for e in events)
                for u in users:
                    await app.bot.send_message(chat_id=u, text=msg)

        await asyncio.sleep(60)


# -----------------------
# MAIN
# -----------------------
def main():
    init_db()

    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    loop = asyncio.get_event_loop()
    loop.create_task(reminder_loop(app))
    loop.create_task(summary_loop(app))

    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
