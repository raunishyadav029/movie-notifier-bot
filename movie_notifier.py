import os
import time
import requests
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import Updater, CommandHandler, CallbackContext
import threading

# Get the Telegram bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")

# List of websites to check
WEBSITES = [
    "https://hdhub4u.gs/",
    "https://bollyflix.faith/",
    "https://vegamovies.nagoya/",
    "https://vegamovies.com.pk/"
]

CHECK_INTERVAL = 300  # 5 minutes

# Function to search movie on all websites
def search_movie(movie_name):
    headers = {"User-Agent": "Mozilla/5.0"}
    for site in WEBSITES:
        search_url = site + "search/" + movie_name.replace(" ", "+")
        try:
            resp = requests.get(search_url, headers=headers, timeout=10)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                # Check if movie name exists on the page
                if movie_name.lower() in soup.get_text().lower():
                    return site
        except Exception as e:
            print(f"Error checking {site}: {e}")
    return None

# Function to check periodically until movie is found
def periodic_check(movie_name, chat_id, bot):
    while True:
        site = search_movie(movie_name)
        if site:
            bot.send_message(chat_id, f"🎉 '{movie_name}' is now available on {site}")
            break
        time.sleep(CHECK_INTERVAL)

# Command handler for /notify
def notify(update: Update, context: CallbackContext):
    if len(context.args) == 0:
        update.message.reply_text("Please provide a movie name. Example: /notify Animal")
        return
    movie_name = " ".join(context.args)

    # Check instantly first
    site = search_movie(movie_name)
    if site:
        update.message.reply_text(f"🎉 '{movie_name}' is already available on {site}")
    else:
        update.message.reply_text(f"🔍 '{movie_name}' not found yet. Will notify when available.")
        # Start background thread for periodic checks
        threading.Thread(target=periodic_check, args=(movie_name, update.message.chat_id, context.bot)).start()

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("notify", notify))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
