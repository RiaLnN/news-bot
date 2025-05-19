import os
import json
import re
import time
import hashlib
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from telegram import Update, BotCommand
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.error import RetryAfter
from news import get_news, get_trending_news, get_news_summary
from keep_alive import keep_alive
import threading

# Keep the Replit container alive
keep_alive()

# Load environment variables
load_dotenv()
BOT_TOKEN = '7556572326:AAGb5DvdreWtkoGioo4qYjGv-2Q_5Q5vkxU'
REPLIT_URL = 'https://9a887443-df6f-4a7d-8e5b-31f75626055c-00-1isurzn4uiglb.kirk.replit.dev'  # e.g. https://project.username.repl.co

# JSON storage files
tmp_path = os.getcwd()
SUBSCRIPTIONS_FILE = os.path.join(tmp_path, "subscriptions.json")
INTERESTS_FILE = os.path.join(tmp_path, "interests.json")
CACHE_FILE = os.path.join(tmp_path, "news_cache.json")

# Cache configuration
CACHE_TTL = 300  # Cache time-to-live in seconds (5 minutes)
MAX_CACHE_SIZE = 100  # Maximum number of cached items


# Utility functions
def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r') as f:
        return json.load(f)


def save_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f)


def load_subscriptions():
    return load_json(SUBSCRIPTIONS_FILE)


def save_subscriptions(d):
    save_json(SUBSCRIPTIONS_FILE, d)


def load_interests():
    return load_json(INTERESTS_FILE)


def save_interests(d):
    save_json(INTERESTS_FILE, d)


# Cache management functions
def load_cache():
    return load_json(CACHE_FILE)


def save_cache(cache_data):
    save_json(CACHE_FILE, cache_data)


def get_cache_key(request_type, topic, language="en"):
    """Generate a unique cache key for the request"""
    key_string = f"{request_type}:{topic}:{language}"
    return hashlib.md5(key_string.encode()).hexdigest()


def is_cache_valid(cache_entry):
    """Check if cache entry is still valid based on TTL"""
    if not cache_entry:
        return False
    current_time = time.time()
    return (current_time - cache_entry.get('timestamp', 0)) < CACHE_TTL


def clean_expired_cache(cache_data):
    """Remove expired entries from cache"""
    current_time = time.time()
    expired_keys = []

    for key, entry in cache_data.items():
        if (current_time - entry.get('timestamp', 0)) >= CACHE_TTL:
            expired_keys.append(key)

    for key in expired_keys:
        del cache_data[key]

    return cache_data


def limit_cache_size(cache_data):
    """Limit cache size by removing oldest entries"""
    if len(cache_data) <= MAX_CACHE_SIZE:
        return cache_data

    # Sort by timestamp and keep only the most recent entries
    sorted_items = sorted(cache_data.items(),
                          key=lambda x: x[1].get('timestamp', 0),
                          reverse=True)

    # Keep only MAX_CACHE_SIZE most recent entries
    limited_cache = dict(sorted_items[:MAX_CACHE_SIZE])
    return limited_cache


def get_cached_news(request_type, topic, language="en"):
    """Get news from cache if available and valid"""
    cache_data = load_cache()
    cache_key = get_cache_key(request_type, topic, language)

    cache_entry = cache_data.get(cache_key)
    if cache_entry and is_cache_valid(cache_entry):
        print(f"Cache hit for {request_type}:{topic}:{language}")
        return cache_entry.get('data')

    print(f"Cache miss for {request_type}:{topic}:{language}")
    return None


def cache_news(request_type, topic, language, news_data):
    """Cache news data with timestamp"""
    cache_data = load_cache()
    cache_key = get_cache_key(request_type, topic, language)

    # Clean expired entries
    cache_data = clean_expired_cache(cache_data)

    # Add new entry
    cache_data[cache_key] = {
        'data': news_data,
        'timestamp': time.time(),
        'request_type': request_type,
        'topic': topic,
        'language': language
    }

    # Limit cache size
    cache_data = limit_cache_size(cache_data)

    # Save cache
    save_cache(cache_data)
    print(f"Cached {request_type}:{topic}:{language}")


# Cached news fetching functions
def get_cached_or_fresh_news(topic, language="en"):
    """Get news with caching"""
    # Try to get from cache first
    cached_data = get_cached_news("news", topic, language)
    if cached_data is not None:
        return cached_data

    # Fetch fresh data if not in cache
    fresh_data = get_news(topic, language)

    # Cache the fresh data
    if fresh_data:
        cache_news("news", topic, language, fresh_data)

    return fresh_data


def get_cached_or_fresh_trending():
    """Get trending news with caching"""
    # Try to get from cache first
    cached_data = get_cached_news("trending", "trending", "en")
    if cached_data is not None:
        return cached_data

    # Fetch fresh data if not in cache
    fresh_data = get_trending_news()

    # Cache the fresh data
    if fresh_data:
        cache_news("trending", "trending", "en", fresh_data)

    return fresh_data


def get_cached_or_fresh_summary(topic):
    """Get news summary with caching"""
    # Try to get from cache first
    cached_data = get_cached_news("summary", topic, "en")
    if cached_data is not None:
        return cached_data

    # Fetch fresh data if not in cache
    fresh_data = get_news_summary(topic)

    # Cache the fresh data
    if fresh_data:
        cache_news("summary", topic, "en", fresh_data)

    return fresh_data


def parse_topic_language(arg: str):
    m = re.match(r"^(.*)\((\w{2})\)$", arg) or re.match(
        r"^(.*)\.(\w{2})$", arg)
    if m:
        return m.group(1).strip(), m.group(2).lower()
    return arg.strip(), "en"


def escape_markdown(text: str) -> str:
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return ''.join(f"\\{c}" if c in escape_chars else c for c in text)


# Bot command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "📌 <b>🤖 Welcome to the News Bot!</b>\n\n"
        "👉 <code>/news &lt;topic&gt;</code> — Get the latest news on a specific topic.\n"
        "👉 <code>/trending</code> — View the most popular news right now.\n"
        "👉 <code>/summary &lt;topic&gt;</code> — Get a brief summary of a news article.\n"
        "👉 <code>/subscribe &lt;topic&gt;</code> — Subscribe to daily news updates on a topic.\n"
        "👉 <code>/unsubscribe</code> — Stop receiving daily news updates.\n"
        "👉 <code>/subscriptions</code> — View your current news subscriptions.\n"
        "👉 <code>/recommend</code> — Get personalized news based on your interests.\n"
        "👉 <code>/cache</code> — View cache statistics.\n"
        "👉 <code>/clearcache</code> — Clear cached news data.\n"
        "👉 <code>/start</code> — Get detailed bot information and instructions.\n"
        "👉 <code>/help</code> — Show this list of available commands.\n\n"
        "🌍 <b>Multi-Language Support!</b>\n"
        "Use <code>/news &lt;topic&gt;.&lt;language_code&gt;</code> or <code>/news &lt;topic&gt;(&lt;language_code&gt;)</code> to fetch news in different languages.\n"
        "Example: <code>/news AI es</code> → Fetches AI news in Spanish.\n\n"
        "💡 <b>How <code>/recommend</code> Works</b>\n"
        "The bot tracks topics you search for and suggests news you might like.\n"
        "Try <code>/recommend</code> and see what it finds based on your past searches!\n\n"
        "⚡ <b>Smart Caching System</b>\n"
        "News is cached for 5 minutes to provide faster responses and reduce redundant requests.\n"
        "Use <code>/cache</code> to see statistics and <code>/clearcache</code> to clear the cache.\n\n"
        "⚙️ <b>Features:</b>\n"
        "✔️ Fetch news summaries with relevant headlines.\n"
        "✔️ Subscribe for daily updates and manage subscriptions easily.\n"
        "✔️ Stay informed with trending news.\n"
        "✔️ Scheduled daily news delivery at 9 AM.\n"
        "✔️ Multi-language support for news queries.\n"
        "✔️ Personalized recommendations based on user searches.\n"
        "✔️ Smart caching system for faster responses.\n\n"
        "🚀 Type any command to get started!")
    await update.effective_message.reply_text(msg, parse_mode="HTML")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)


async def news_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        arg = " ".join(context.args)
        topic, language = parse_topic_language(arg)
        user_id = str(update.effective_chat.id)
        interests = load_interests()
        interests.setdefault(user_id, []).append(topic)
        save_interests(interests)

        # Use cached version
        articles = get_cached_or_fresh_news(topic, language)

        if articles:
            text = "\n\n".join(f"📰 *{escape_markdown(a['title'])}*\n{a['url']}"
                               for a in articles)
        else:
            text = f"❌ No news for '{escape_markdown(topic)}' in '{language}'"
    else:
        text = "Use /news <topic> to fetch news"
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def trending_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Use cached version
    articles = get_cached_or_fresh_trending()

    if articles:
        text = "\n\n".join(f"🔥 *{escape_markdown(a['title'])}*\n{a['url']}"
                           for a in articles)
    else:
        text = "No trending news available."
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def subscribe_handler(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    if context.args:
        topic = " ".join(context.args)
        subs = load_subscriptions()
        subs[user_id] = topic
        save_subscriptions(subs)
        await update.effective_message.reply_text(
            f"✅ Subscribed to {escape_markdown(topic)}")
    else:
        await update.effective_message.reply_text(
            "❌ Provide a topic: /subscribe <topic>")


async def unsubscribe_handler(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    subs = load_subscriptions()
    if user_id in subs:
        subs.pop(user_id)
        save_subscriptions(subs)
        await update.effective_message.reply_text("✅ Unsubscribed")
    else:
        await update.effective_message.reply_text("ℹ️ No active subscription.")


async def subscriptions_handler(update: Update,
                                context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    subs = load_subscriptions()
    topic = subs.get(user_id)
    text = f"📌 Subscribed to: {escape_markdown(topic)}" if topic else "ℹ️ No subscriptions."
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        topic = " ".join(context.args)
        # Use cached version
        summaries = get_cached_or_fresh_summary(topic)
        text = "\n\n".join(summaries) or "No summaries available."
    else:
        text = "Use /summary <topic> to fetch summaries"
    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def cache_stats_handler(update: Update,
                              context: ContextTypes.DEFAULT_TYPE):
    """Show cache statistics"""
    cache_data = load_cache()

    if not cache_data:
        text = "📊 Cache is empty."
    else:
        # Clean expired entries first
        cache_data = clean_expired_cache(cache_data)
        save_cache(cache_data)

        total_entries = len(cache_data)
        if total_entries == 0:
            text = "📊 Cache is empty (all entries expired)."
        else:
            # Calculate cache statistics
            cache_types = {}
            for entry in cache_data.values():
                req_type = entry.get('request_type', 'unknown')
                cache_types[req_type] = cache_types.get(req_type, 0) + 1

            stats_text = "\n".join([
                f"  • {type_name}: {count}"
                for type_name, count in cache_types.items()
            ])

            text = (f"📊 *Cache Statistics*\n\n"
                    f"Total entries: {total_entries}/{MAX_CACHE_SIZE}\n"
                    f"Cache TTL: {CACHE_TTL} seconds\n\n"
                    f"*By type:*\n{stats_text}")

    await update.effective_message.reply_text(text, parse_mode="Markdown")


async def recommend_handler(update: Update,
                            context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    interests = load_interests()
    user_topics = interests.get(user_id, [])
    if not user_topics:
        await update.effective_message.reply_text("ℹ️ Search with /news first."
                                                  )
        return
    topic = user_topics[-1]
    # Use cached version
    articles = get_cached_or_fresh_news(topic, "en")

    if articles:
        text = "🔍 Based on your interest: " + "\n\n".join(
            f"📰 *{escape_markdown(a['title'])}*\n{a['url']}" for a in articles)
    else:
        text = f"❌ No news for {escape_markdown(topic)}"
    await update.effective_message.reply_text(text, parse_mode="Markdown")


# Scheduler job
async def send_daily_news(app):
    subs = load_subscriptions()
    for uid, topic in subs.items():
        try:
            # Use cached version for daily news too
            articles = get_cached_or_fresh_news(topic, "en")
            text = "\n\n".join(f"📰 *{escape_markdown(a['title'])}*\n{a['url']}"
                               for a in articles) or "No news today."
            await app.bot.send_message(chat_id=int(uid),
                                       text=text,
                                       parse_mode="Markdown")
        except Exception as e:
            print(f"Error sending daily news to {uid}: {e}")


async def set_my_commands(app):
    cmds = [
        BotCommand(c, d)
        for c, d in [("start", "Start bot"), (
            "help",
            "Help"), ("news", "Latest news"), (
                "trending",
                "Trending news"), ("summary",
                                   "News summary"), ("subscribe", "Subscribe"),
                     ("unsubscribe",
                      "Unsubscribe"), ("subscriptions", "Your subscriptions"),
                     ("recommend",
                      "Recommendations"), (
                          "cache",
                          "Cache statistics"), ("clearcache", "Clear cache")]
    ]
    await app.bot.set_my_commands(cmds)


# Initialize application and handlers
application = ApplicationBuilder().token(BOT_TOKEN).build()
for handler in [("start", start), ("help", help_command),
                ("news", news_handler), ("trending", trending_handler),
                ("subscribe", subscribe_handler),
                ("unsubscribe", unsubscribe_handler),
                ("subscriptions", subscriptions_handler),
                ("summary", summary_handler), ("recommend", recommend_handler),
                ("cache", cache_stats_handler),
                ("clearcache", clean_expired_cache)]:
    application.add_handler(CommandHandler(handler[0], handler[1]))


# Alternative 1: Run polling in the same event loop
async def run_bot():
    """Run the bot with polling in the main event loop"""
    # Set commands
    await set_my_commands(application)

    # Initialize and start application
    await application.initialize()
    await application.start()

    # Setup scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_news, 'cron', hour=9, args=[application])
    scheduler.start()

    # Start polling
    await application.updater.start_polling()

    try:
        # Keep the bot running
        await asyncio.Event().wait()
    except KeyboardInterrupt:
        print("Bot stopped by user")
    finally:
        # Cleanup
        scheduler.shutdown()
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


# Alternative 2: Run with threading but proper event loop setup
def run_bot_in_thread():
    """Run the bot in a separate thread with its own event loop"""

    async def bot_main():
        try:
            await set_my_commands(application)

            # Initialize and start application
            await application.initialize()
            await application.start()

            scheduler = AsyncIOScheduler()
            scheduler.add_job(send_daily_news,
                              'cron',
                              hour=9,
                              args=[application])
            scheduler.start()

            # Start polling
            await application.updater.start_polling()

            # Keep the bot running
            await asyncio.Event().wait()

        except Exception as e:
            print(f"Error in bot_main: {e}")
        finally:
            # Cleanup
            if 'scheduler' in locals():
                scheduler.shutdown()
            await application.updater.stop()
            await application.stop()
            await application.shutdown()

    # Create new event loop for the thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(bot_main())
    except Exception as e:
        print(f"Error running bot in thread: {e}")
    finally:
        loop.close()


if __name__ == "__main__":

    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("Bot stopped by user")
