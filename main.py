import os
import requests
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

# Load environment variables
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

print("Telegram Token Loaded:", TELEGRAM_BOT_TOKEN is not None)
print("OpenAI Key Loaded:", OPENAI_API_KEY is not None)


# 🔥 OpenAI function (NO silent failures)
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

    try:
        response = requests.post(url, headers=headers, json=data)

        print("STATUS:", response.status_code)
        print("RAW RESPONSE:", response.text)

        if response.status_code != 200:
            return f"❌ OpenAI Error:\n{response.text}"

        result = response.json()

        return result["output"][0]["content"][0]["text"]

    except Exception as e:
        return f"❌ Exception: {str(e)}"


# 📩 Telegram message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text

    print("User:", user_text)

    reply = ask_openai(user_text)

    print("Bot:", reply)

    await update.message.reply_text(reply)


# 🚀 Main entry point
def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("Missing TELEGRAM_BOT_TOKEN")

    if not OPENAI_API_KEY:
        raise ValueError("Missing OPENAI_API_KEY")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Bot running...")

    app.run_polling()


if __name__ == "__main__":
    main()
