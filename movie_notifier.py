import os
import time
import threading
import telebot
import requests
from bs4 import BeautifulSoup
from flask import Flask, request

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

WEBSITES = [
    "https://bollyflix.faith/search/",
    "https://hdhub4u.gs/?s=",
    "https://vegamovies.nagoya/?s=",
    "https://vegamovies.com.pk/?s="
]

# movie_name → { "chat_id": int, "found_sites": set() }
pending_movies = {}


def check_movie_availability(movie_name, already_found):
    new_links = []
    for site in WEBSITES:
        if site in already_found:
            continue  # skip sites already found

        search_url = site + movie_name.replace(" ", "+")
        try:
            response = requests.get(search_url, timeout=10)
            soup = BeautifulSoup(response.text, "html.parser")

            # Look for direct movie link
            result_link = soup.find("a", href=True, text=lambda t: t and movie_name.lower() in t.lower())
            if result_link:
                new_links.append((site, result_link["href"]))
        except Exception as e:
            print(f"Error checking {site}: {e}")
    return new_links


def background_checker():
    while True:
        time.sleep(120)  # check every 2 min
        for movie_name, movie_data in list(pending_movies.items()):
            chat_id = movie_data["chat_id"]
            already_found = movie_data["found_sites"]

            new_links = check_movie_availability(movie_name, already_found)

            if new_links:
                reply = f"🎉 *{movie_name}* new links found:\n"
                for site, link in new_links:
                    reply += f"🔗 [{site}]({link})\n"
                    movie_data["found_sites"].add(site)

                bot.send_message(chat_id, reply, parse_mode="Markdown")

            # stop checking if user removed it manually
            if movie_name not in pending_movies:
                continue

            # If all sites have been found, stop checking
            if movie_data["found_sites"] == set(WEBSITES):
                del pending_movies[movie_name]


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Send me a movie name, I'll notify you when it's available!\nType /stop <movie name> to stop searching.")


@bot.message_handler(commands=['stop'])
def stop_search(message):
    movie_name = message.text.replace("/stop", "").strip()
    if movie_name in pending_movies:
        del pending_movies[movie_name]
        bot.reply_to(message, f"🛑 Stopped searching for *{movie_name}*.", parse_mode="Markdown")
    else:
        bot.reply_to(message, f"⚠️ No active search found for *{movie_name}*.", parse_mode="Markdown")


@bot.message_handler(func=lambda m: True)
def handle_movie_search(message):
    movie_name = message.text.strip()
    links = check_movie_availability(movie_name, set())

    if links:
        reply = f"🎬 *{movie_name}* is available:\n"
        found_sites = set()
        for site, link in links:
            reply += f"🔗 [{site}]({link})\n"
            found_sites.add(site)

        bot.send_message(message.chat.id, reply, parse_mode="Markdown")

        # keep checking for other sites until user stops it
        if found_sites != set(WEBSITES):
            pending_movies[movie_name] = {"chat_id": message.chat.id, "found_sites": found_sites}

    else:
        bot.send_message(message.chat.id, f"⚠️ {movie_name} not available yet. I'll keep checking...")
        pending_movies[movie_name] = {"chat_id": message.chat.id, "found_sites": set()}


# Webhook route
@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = request.get_data().decode("utf-8")
    bot.process_new_updates([telebot.types.Update.de_json(update)])
    return "OK", 200


# Root route
@app.route("/", methods=["GET"])
def index():
    return "Bot is running!", 200


if __name__ == "__main__":
    # Start background checking
    threading.Thread(target=background_checker, daemon=True).start()

    # Set webhook for Telegram
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{TOKEN}")
    app.run(host="0.0.0.0", port=10000)
