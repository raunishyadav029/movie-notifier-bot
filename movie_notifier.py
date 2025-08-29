import os
import threading
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask
import telebot

# Load Telegram Bot Token from environment variables
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

# List of websites to check
WEBSITES = [
    "https://bollyflix.faith/search/",
    "https://hdhub4u.gs/?s=",
    "https://vegamovies.nagoya/?s=",
    "https://vegamovies.com.pk/?s="
]

# Movie tracking dictionary
movie_requests = {}

# Flask app to keep the service alive on Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Movie Notifier Bot is Running!"

# Function to check if movie exists on any website
def check_movie(movie_name):
    movie_name_encoded = movie_name.replace(" ", "+")
    for site in WEBSITES:
        url = site + movie_name_encoded
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200 and movie_name.lower() in response.text.lower():
                return url
        except Exception as e:
            print(f"Error checking {site}: {e}")
    return None

# Background process to keep checking movie availability
def movie_checker():
    while True:
        for chat_id, movie_name in list(movie_requests.items()):
            result_url = check_movie(movie_name)
            if result_url:
                bot.send_message(chat_id, f"🎉 '{movie_name}' is now available!\nCheck here: {result_url}")
                del movie_requests[chat_id]  # Stop checking once found
        time.sleep(300)  # Check every 5 minutes

# Telegram command to start notifications
@bot.message_handler(commands=['notify'])
def notify(message):
    chat_id = message.chat.id
    movie_name = message.text.replace("/notify", "").strip()
    if not movie_name:
        bot.send_message(chat_id, "❌ Please enter a movie name. Example: /notify Animal")
        return

    # Instant check
    result_url = check_movie(movie_name)
    if result_url:
        bot.send_message(chat_id, f"🎉 '{movie_name}' is already available!\nCheck here: {result_url}")
    else:
        movie_requests[chat_id] = movie_name
        bot.send_message(chat_id, f"🔔 I will notify you when '{movie_name}' is available.")

# Start Telegram bot in a separate thread
def start_bot():
    bot.infinity_polling()

if __name__ == "__main__":
    threading.Thread(target=start_bot).start()
    threading.Thread(target=movie_checker).start()
    app.run(host="0.0.0.0", port=10000)
