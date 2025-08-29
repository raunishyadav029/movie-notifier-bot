import os
import threading
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
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

# Flask app for Render
app = Flask(__name__)

@app.route('/')
def home():
    return "Movie Notifier Bot with Webhook is Running!"

# Function to check if movie exists
def check_movie(movie_name):
    movie_name_encoded = movie_name.replace(" ", "+")
    for site in WEBSITES:
        url = site + movie_name_encoded
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200 and movie_name.lower() in response.text.lower():
                return url
        except:
            pass
    return None

# Background checker
def movie_checker():
    while True:
        for chat_id, movie_name in list(movie_requests.items()):
            result_url = check_movie(movie_name)
            if result_url:
                bot.send_message(chat_id, f"🎉 '{movie_name}' is now available!\nCheck here: {result_url}")
                del movie_requests[chat_id]
        time.sleep(300)

# Telegram command
@bot.message_handler(commands=['notify'])
def notify(message):
    chat_id = message.chat.id
    movie_name = message.text.replace("/notify", "").strip()
    if not movie_name:
        bot.send_message(chat_id, "❌ Please enter a movie name. Example: /notify Animal")
        return

    result_url = check_movie(movie_name)
    if result_url:
        bot.send_message(chat_id, f"🎉 '{movie_name}' is already available!\nCheck here: {result_url}")
    else:
        movie_requests[chat_id] = movie_name
        bot.send_message(chat_id, f"🔔 I will notify you when '{movie_name}' is available.")

# Webhook route for Telegram
@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    update = request.stream.read().decode("utf-8")
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return "OK", 200

if __name__ == "__main__":
    threading.Thread(target=movie_checker).start()
    
    # Set webhook for Telegram
    url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/{TOKEN}"
    bot.remove_webhook()
    bot.set_webhook(url=url)
    
    app.run(host="0.0.0.0", port=10000)
