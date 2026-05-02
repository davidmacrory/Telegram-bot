from dotenv import load_dotenv
load_dotenv()
import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def ask_openai(prompt):
    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "gpt-4.1-mini",
        "input": prompt
    }

    response = requests.post(url, headers=headers, json=data)
    result = response.json()

    # Safe parsing (prevents your earlier crash)
    try:
        return result["output"][0]["content"][0]["text"]
    except Exception:
        return f"Error: {result}"

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    reply = ask_openai(update.message.text)
    await update.message.reply_text(reply)

def main():
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    print("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
