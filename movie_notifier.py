import os
import threading
import time
import requests
from bs4 import BeautifulSoup
from flask import Flask
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

WEBSITES = [
    ("Bollyflix", "https://bollyflix.faith/search/{}"),
    ("HDHub4u", "https://hdhub4u.gs/?s={}"),
    ("Vegamovies Nagoya", "https://vegamovies.nagoya/?s={}"),
    ("Vegamovies PK", "https://vegamovies.com.pk/?s={}")
]

movie_requests = {}

app = Flask(__name__)

@app.route('/')
def home():
    return "Movie Notifier Bot is running!"

def find_movie_links(movie_name):
    encoded = movie_name.replace(" ", "+")
    found = []
    for name, template in WEBSITES:
        try:
            url = template.format(encoded)
            resp = requests.get(url, timeout=10)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "html.parser")
            # Example heuristic: check for <a> elements whose text contains the movie title
            results = soup.find_all("a", text=lambda t: t and movie_name.lower() in t.lower())
            if results:
                found.append((name, url))
        except Exception as e:
            print(f"Error checking {name} at {url}: {e}")
    return found

def background_checker():
    while True:
        for chat_id, movie_name in list(movie_requests.items()):
            found = find_movie_links(movie_name)
            if found:
                msg = f"🎉 '{movie_name}' is now available on:\n"
                msg += "\n".join(f"{site}: {link}" for site, link in found)
                bot.send_message(chat_id, msg)
                del movie_requests[chat_id]
        time.sleep(300)

@bot.message_handler(commands=['notify'])
def handle_notify(message):
    chat_id = message.chat.id
    movie_name = message.text.split(" ", 1)
    if len(movie_name) < 2 or not movie_name[1].strip():
        bot.send_message(chat_id, "Usage: /notify <Movie Name>")
        return
    name = movie_name[1].strip()
    bot.send_message(chat_id, f"Searching for '{name}'... 😊")

    found = find_movie_links(name)
    if found:
        msg = f"🎉 '{name}' is already available on:\n"
        msg += "\n".join(f"{site}: {link}" for site, link in found)
        bot.send_message(chat_id, msg)
    else:
        movie_requests[chat_id] = name
        bot.send_message(chat_id, f"Not found yet — I’ll keep searching until it's available.")

def main():
    threading.Thread(target=lambda: app.run(host="0.0.0.0", port=10000), daemon=True).start()
    threading.Thread(target=background_checker, daemon=True).start()
    bot.infinity_polling()

if __name__ == "__main__":
    main()
