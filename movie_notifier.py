import requests
from bs4 import BeautifulSoup
import telebot
import threading
import time
import os
from flask import Flask, request

# Telegram Bot Token and Webhook URL
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://movie-notifier-bot-1.onrender.com/")
bot = telebot.TeleBot(BOT_TOKEN)

# Flask app for webhook
app = Flask(__name__)

# Websites to search
WEBSITES = [
    "https://bollyflix.faith/search/",
    "https://hdhub4u.gs/?s=",
    "https://vegamovies.nagoya/?s=",
    "https://vegamovies.com.pk/?s="
]

# Global vars
searching = False
stop_search = False


def check_movie_availability(movie_name):
    """Check all websites for the movie and return list of valid links."""
    available_links = []
    for website in WEBSITES:
        search_url = website + movie_name.replace(" ", "+")
        try:
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                movie_links = soup.find_all("a", href=True)

                for link in movie_links:
                    href = link["href"]
                    if movie_name.lower() in href.lower():
                        available_links.append(href)
                        break
        except Exception as e:
            print(f"Error checking {website}: {e}")
    return available_links


def search_movie_periodically(chat_id, movie_name):
    """Keep searching until movie is found or /stop command is given."""
    global searching, stop_search
    searching = True
    stop_search = False

    while not stop_search:
        links = check_movie_availability(movie_name)
        if links:
            bot.send_message(chat_id, f"✅ Movie '{movie_name}' found:\n" + "\n".join(links))
            searching = False
            return
        else:
            bot.send_message(chat_id, f"❌ '{movie_name}' not available yet. I'll keep checking...")
            time.sleep(60)  # Wait 1 min before rechecking

    searching = False


@bot.message_handler(commands=['search'])
def handle_search(message):
    global searching
    if searching:
        bot.send_message(message.chat.id, "Already searching. Use /stop to cancel.")
        return

    movie_name = message.text.replace("/search", "").strip()
    if not movie_name:
        bot.send_message(message.chat.id, "Usage: /search MovieName")
        return

    bot.send_message(message.chat.id, f"Searching for '{movie_name}'...")
    threading.Thread(target=search_movie_periodically, args=(message.chat.id, movie_name)).start()


@bot.message_handler(commands=['stop'])
def handle_stop(message):
    global stop_search
    stop_search = True
    bot.send_message(message.chat.id, "🛑 Stopped searching.")


# --- Webhook routes ---
@app.route("/" + BOT_TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/", methods=['GET'])
def index():
    return "Bot is running!", 200


# Set webhook on startup
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL + BOT_TOKEN)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
