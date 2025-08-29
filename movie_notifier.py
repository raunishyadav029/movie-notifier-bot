
from flask import Flask
import threading
import telebot
import requests
from bs4 import BeautifulSoup
import time
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# Flask for Render free tier
app = Flask(__name__)

@app.route('/')
def home():
    return "Movie Notifier Bot Running!"

# Store user requests
user_requests = {}

# Check movie on website
def check_movie(movie_name):
    urls = [
        "https://hdhub4u.bio",       # Example site
        "https://bollyflix.town"     # Example site
    ]
    for url in urls:
        try:
            response = requests.get(url, timeout=10)
            if movie_name.lower() in response.text.lower():
                return True
        except:
            pass
    return False

# Background worker to check movie availability
def movie_checker(chat_id, movie_name):
    while True:
        if check_movie(movie_name):
            bot.send_message(chat_id, f"🎉 '{movie_name}' is now available!")
            user_requests.pop(chat_id, None)
            break
        time.sleep(300)  # check every 5 min

# Telegram command handler
@bot.message_handler(commands=['notify'])
def notify(message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "Usage: /notify <movie_name>")
        return

    movie_name = parts[1]
    bot.send_message(message.chat.id, f"🔍 Watching for '{movie_name}'...")
    user_requests[message.chat.id] = movie_name
    threading.Thread(target=movie_checker, args=(message.chat.id, movie_name)).start()

def run_bot():
    bot.polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
