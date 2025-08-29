import telebot
import requests
from bs4 import BeautifulSoup
import time
import os

# Get bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# List of websites to check
websites = [
    "https://bollyflix.faith",
    "https://hdhub4u.gs",
    "https://vegamovies.nagoya",
    "https://vegamovies.com.pk"
]

# To store ongoing searches
active_searches = {}

def movie_available(movie_name):
    """Check all websites for the movie."""
    for site in websites:
        try:
            search_url = f"{site}/search/{movie_name.replace(' ', '%20')}"
            response = requests.get(search_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                if movie_name.lower() in soup.get_text().lower():
                    return site  # Return the site where it's found
        except Exception:
            continue
    return None


@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Welcome! Use /notify <movie_name> to get notified when the movie is available.")


@bot.message_handler(commands=['notify'])
def notify_movie(message):
    chat_id = message.chat.id
    try:
        movie_name = message.text.split(" ", 1)[1].strip()
    except IndexError:
        bot.reply_to(chat_id, "Please provide a movie name. Example: /notify Animal")
        return

    bot.reply_to(chat_id, f"Searching for '{movie_name}'... I'll notify you when it's available!")

    # Instant check first
    site_found = movie_available(movie_name)
    if site_found:
        bot.send_message(chat_id, f"✅ '{movie_name}' is available now on {site_found}!")
        return

    # If not found, keep checking every 5 minutes until found
    active_searches[chat_id] = movie_name
    while chat_id in active_searches:
        site_found = movie_available(movie_name)
        if site_found:
            bot.send_message(chat_id, f"✅ '{movie_name}' is available now on {site_found}!")
            del active_searches[chat_id]  # Stop checking after notification
            break
        time.sleep(300)  # Check every 5 minutes


@bot.message_handler(commands=['stop'])
def stop_search(message):
    chat_id = message.chat.id
    if chat_id in active_searches:
        del active_searches[chat_id]
        bot.reply_to(chat_id, "Stopped searching for your movie.")
    else:
        bot.reply_to(chat_id, "You have no active searches.")


print("Bot is running...")
bot.polling()
