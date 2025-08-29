import os
import time
import threading
import urllib.parse
from flask import Flask, request

import requests
from bs4 import BeautifulSoup
import telebot

# --- config/env ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")   # e.g. https://movie-notifier-bot-1.onrender.com
CHECK_EVERY_SECONDS = 120

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN env var is required")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
app = Flask(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

# ---- sites (built from your HTML screenshots) ----
SITES = [
    {
        "name": "BollyFlix",
        "search": lambda q: f"https://bollyflix.faith/?s={q}",
        "selectors": ["h2.title.front-view-title a", "h2.entry-title a", "h2.post-title a"],
        "domain": "bollyflix"
    },
    {
        "name": "HDHub4u",
        "search": lambda q: f"https://hdhub4u.gs/?s={q}",
        # post links usually in entry/post titles; avoid ad/redirect anchors
        "selectors": ["h2.entry-title a", "h2.post-title a", "h3.entry-title a", ".post-title a", ".entry-title a"],
        "domain": "hdhub4u"
    },
    {
        "name": "VegaMovies (SU)",
        "search": lambda q: f"https://vegamovies.su/?s={q}",
        "selectors": ["h3.entry-title a", "h2.entry-title a"],
        "domain": "vegamovies"
    },
    {
        "name": "VegaMovies (Nagoya)",
        "search": lambda q: f"https://vegamovies.nagoya/?s={q}",
        "selectors": ["h3.entry-title a", "h2.entry-title a"],
        "domain": "vegamovies"
    },
    {
        "name": "VegaMovies (PK)",
        "search": lambda q: f"https://vegamovies.com.pk/?s={q}",
        "selectors": ["h3.entry-title a", "h2.entry-title a"],
        "domain": "vegamovies"
    },
]

# tracking: key=(chat_id, movie_lower)  ->  {"found_urls": set(), "active": True}
TRACKS = {}


def normalize(text: str) -> str:
    return " ".join(text.lower().split())


def scrape_one_site(site, movie_name):
    """Return list of (site_name, absolute_url, link_text) matches for one site."""
    q = urllib.parse.quote_plus(movie_name)
    url = site["search"](q)
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.text, "html.parser")

        matches = []
        for css in site["selectors"]:
            for a in soup.select(css):
                href = (a.get("href") or "").strip()
                text = (a.get_text(" ", strip=True) or "")
                if not href:
                    continue
                # basic relevance filter: movie name in anchor text
                if normalize(movie_name) in normalize(text):
                    abs_url = urllib.parse.urljoin(url, href)
                    matches.append((site["name"], abs_url, text))
            if matches:
                break  # we found from a selector; good enough

        # fallback: any anchor containing movie name in text
        if not matches:
            for a in soup.find_all("a", href=True):
                text = (a.get_text(" ", strip=True) or "")
                if normalize(movie_name) in normalize(text):
                    abs_url = urllib.parse.urljoin(url, a["href"])
                    matches.append((site["name"], abs_url, text))
                    break

        return matches
    except Exception as e:
        print(f"[scrape] {site['name']} error: {e}")
        return []


def check_all_sites_for_new_links(movie_name, already_found):
    """Return list of new links across sites, skipping URLs we already sent."""
    new_links = []
    for site in SITES:
        results = scrape_one_site(site, movie_name)
        for _, link, text in results:
            if link not in already_found:
                new_links.append((site["name"], link, text))
    return new_links


def background_checker():
    while True:
        time.sleep(CHECK_EVERY_SECONDS)
        for key in list(TRACKS.keys()):
            chat_id, movie_lower = key
            track = TRACKS.get(key)
            if not track or not track.get("active"):
                continue

            movie_name = track["movie_name"]
            already = track["found_urls"]
            new_links = check_all_sites_for_new_links(movie_name, already)

            if new_links:
                lines = [f"🎉 *{movie_name}* — new link(s) found:"]
                for site_name, url, text in new_links:
                    lines.append(f"• [{site_name}]({url}) — _{text}_")
                    already.add(url)
                bot.send_message(chat_id, "\n".join(lines))


# ----- telegram handlers -----

@bot.message_handler(commands=["start", "help"])
def start_cmd(msg):
    bot.reply_to(
        msg,
        "hi! send `/search <movie name>` to get the first working link.\n"
        "i’ll keep checking other sites and send new links as they appear.\n"
        "use `/stop <movie name>` to stop tracking that title (or just `/stop` to stop all).",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["search"])
def search_cmd(msg):
    text = (msg.text or "").strip()
    name = text[len("/search"):].strip()
    if not name:
        bot.reply_to(msg, "usage: `/search Movie Name`", parse_mode="Markdown")
        return

    movie_lower = normalize(name)
    key = (msg.chat.id, movie_lower)

    # instant pass: check now and send first links
    fresh_links = check_all_sites_for_new_links(name, already_found=set())
    if fresh_links:
        # send immediately the links we have right now
        lines = [f"🎬 *{name}* — found link(s):"]
        for site_name, url, text in fresh_links:
            lines.append(f"• [{site_name}]({url}) — _{text}_")
        bot.send_message(msg.chat.id, "\n".join(lines))
        # start tracking for further links unless user stops
        TRACKS[key] = {"movie_name": name, "found_urls": {u for _, u, _ in fresh_links}, "active": True}
    else:
        bot.send_message(msg.chat.id, f"⚠️ no confirmed link yet for *{name}*. i'll keep checking…", parse_mode="Markdown")
        TRACKS[key] = {"movie_name": name, "found_urls": set(), "active": True}


@bot.message_handler(commands=["stop"])
def stop_cmd(msg):
    text = (msg.text or "").strip()
    arg = text[len("/stop"):].strip().lower()

    stopped_any = False
    if arg:
        # stop a specific movie
        key = (msg.chat.id, arg)
        if key in TRACKS:
            TRACKS[key]["active"] = False
            del TRACKS[key]
            stopped_any = True
    else:
        # stop all for this chat
        keys = [k for k in TRACKS.keys() if k[0] == msg.chat.id]
        for k in keys:
            del TRACKS[k]
            stopped_any = True

    if stopped_any:
        bot.reply_to(msg, "🛑 stopped searching.")
    else:
        bot.reply_to(msg, "nothing to stop.")


# ----- webhook endpoints -----

@app.route("/" + BOT_TOKEN, methods=["POST"])
def telegram_webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "OK", 200


@app.route("/", methods=["GET"])
def health():
    return "Movie notifier is up ✅", 200


def setup_webhook():
    if not WEBHOOK_URL:
        raise RuntimeError("WEBHOOK_URL env var is required for webhook mode")
    bot.remove_webhook()
    bot.set_webhook(url=f"{WEBHOOK_URL}/{BOT_TOKEN}")


if __name__ == "__main__":
    # background watcher
    threading.Thread(target=background_checker, daemon=True).start()

    # set webhook once and start flask on the render-assigned port
    setup_webhook()
    port = int(os.environ.get("PORT", "10000"))   # <-- render will inject PORT
    app.run(host="0.0.0.0", port=port)
