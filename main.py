import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TELEGRAM_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

def ask_openai(message):
    url = "https://api.openai.com/v1/responses"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    json_data = {
        "model": "gpt-5.3",
        "input": message
    }

    response = requests.post(url, headers=headers, json=json_data)
    return response.json()["output"][0]["content"][0]["text"]

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.text:
        reply = ask_openai(update.message.text)
        await update.message.reply_text(reply)

app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
