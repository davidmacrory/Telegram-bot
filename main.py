from dotenv import load_dotenv
load_dotenv()
import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# --- Logging ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# --- Env vars ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("Missing TELEGRAM_BOT_TOKEN or OPENAI_API_KEY")

# --- OpenAI client ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is running. Ask me anything.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    logging.info(f"Received: {user_message}")

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=user_message,
            timeout=15
        )

        reply = response.output_text

        if not reply:
            reply = "I didn’t get a proper response. Try again."

    except Exception as e:
        logging.error(f"OpenAI error: {e}")
        reply = "Something went wrong — try again."

    # Telegram message limit safeguard
    if len(reply) > 4000:
        reply = reply[:4000]

    await update.message.reply_text(reply)

# --- App ---
app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Run ---
if __name__ == "__main__":
    logging.info("Starting bot...")
    app.run_polling(drop_pending_updates=True)
