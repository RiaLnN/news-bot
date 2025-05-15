import json
import asyncio
import os
import re

from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from dotenv import load_dotenv
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from news import get_news, get_trending_news, get_news_summary  
from keep_alive import keep_alive

keep_alive()

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

SUBSCRIPTIONS_FILE = "subscriptions.json"
INTERESTS_FILE = "interests.json"



def load_subscriptions():
    if not os.path.exists(SUBSCRIPTIONS_FILE):
        return {}
    with open(SUBSCRIPTIONS_FILE, "r") as file:
        return json.load(file)



def save_subscriptions(subscriptions):
    with open(SUBSCRIPTIONS_FILE, "w") as file:
        json.dump(subscriptions, file)



def load_interests():
    if not os.path.exists(INTERESTS_FILE):
        return {}
    with open(INTERESTS_FILE, "r") as file:
        return json.load(file)



def save_interests(interests):
    with open(INTERESTS_FILE, "w") as file:
        json.dump(interests, file)


def parse_topic_language(arg: str):
    """
    Разбор темы и языка из аргумента.
    Поддерживается формат topic(language_code) и topic.language_code
    """
    m = re.match(r"^(.*)\((\w{2})\)$", arg)
    if m:
        topic = m.group(1).strip()
        lang = m.group(2).lower()
        return topic, lang

    m = re.match(r"^(.*)\.(\w{2})$", arg)
    if m:
        topic = m.group(1).strip()
        lang = m.group(2).lower()
        return topic, lang

    return arg.strip(), "en"


def escape_markdown(text: str) -> str:
    """Простейшее экранирование спецсимволов Markdown для Telegram."""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in escape_chars else c for c in text)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Функция start вызвана")
    message = (
        "🤖 *Welcome to the News Bot!*\n"
        "I'm here to provide you with the latest news updates.\n\n"
        "📌 *Available Commands:*\n"
        "👉 `/news <topic>` — Get the latest news on a specific topic.\n"
        "👉 `/trending` — View the most popular news right now.\n"
        "👉 `/summary <topic>` — Get a brief summary of a news article.\n"
        "👉 `/subscribe <topic>` — Subscribe to daily news updates on a topic.\n"
        "👉 `/unsubscribe` — Stop receiving daily news updates.\n"
        "👉 `/subscriptions` — View your current news subscriptions.\n"
        "👉 `/recommend` — Get personalized news based on your interests.\n"
        "👉 `/start` — Get detailed bot information and instructions.\n"
        "👉 `/help` — Show this list of available commands.\n\n"
        "🌍 *New Feature: Multi-Language Support!*\n"
        "Use `/news <topic>.<language_code>` or `/news <topic>(<language_code>)` to fetch news in different languages.\n"
        "Example: `/news AI es` → Fetches AI news in Spanish.\n\n"
        "💡 *Personalized Recommendations!*\n"
        "Use `/recommend` to get news based on your interests.\n"
        "The bot learns which topics you engage with and suggests relevant articles!\n\n"
        "⚙️ *Features:*\n"
        "✔️ Fetch news summaries with relevant headlines.\n"
        "✔️ Subscribe for daily updates and manage subscriptions easily.\n"
        "✔️ Stay informed with trending news.\n"
        "✔️ Scheduled daily news delivery at 9 AM.\n"
        "✔️ Multi-language support for news queries.\n"
        "✔️ Personalized news recommendations based on your searches.\n\n"
        "🚀 Type any command to get started!"
    )
    await update.effective_message.reply_text(message, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "📌 *News Bot Commands:*\n"
        "👉 `/news <topic>` — Get the latest news on a specific topic.\n"
        "👉 `/trending` — View the most popular news right now.\n"
        "👉 `/summary <topic>` — Get a brief summary of a news article.\n"
        "👉 `/subscribe <topic>` — Subscribe to daily news updates on a topic.\n"
        "👉 `/unsubscribe` — Stop receiving daily news updates.\n"
        "👉 `/subscriptions` — View your current news subscriptions.\n"
        "👉 `/recommend` — Get personalized news based on your interests.\n"
        "👉 `/start` — Get detailed bot information and instructions.\n"
        "👉 `/help` — Show this list of available commands.\n\n"
        "🌍 *Multi-Language Support!*\n"
        "Use `/news <topic>.<language_code>` or `/news <topic>(<language_code>)` to fetch news in different languages.\n"
        "Example: `/news AI es` → Fetches AI news in Spanish.\n\n"
        "💡 *How `/recommend` Works*\n"
        "The bot tracks topics you search for and suggests news you might like.\n"
        "Try `/recommend` and see what it finds based on your past searches!\n\n"
        "⚙️ *Features:*\n"
        "✔️ Fetch news summaries with relevant headlines.\n"
        "✔️ Subscribe for daily updates and manage subscriptions easily.\n"
        "✔️ Stay informed with trending news.\n"
        "✔️ Scheduled daily news delivery at 9 AM.\n"
        "✔️ Multi-language support for news queries.\n"
        "✔️ Personalized recommendations based on user searches.\n\n"
        "🚀 Type any command to get started!"
    )
    await update.effective_message.reply_text(message, parse_mode="Markdown")


async def news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.args:
        arg = " ".join(context.args)
        topic, language = parse_topic_language(arg)

        user_id = str(update.effective_chat.id)
        interests = load_interests()
        interests[user_id] = interests.get(user_id, []) + [topic]
        save_interests(interests)

        articles = get_news(topic, language)
        if articles:
            response = "\n\n".join(
                [f"📰 *{escape_markdown(a['title'])}*\n{a['url']}" for a in articles]
            )
        else:
            response = f"❌ No news for '{escape_markdown(topic)}' in language '{escape_markdown(language)}'."
    else:
        response = "Use `/news <topic>` (optionally specify language as `(en)` or `.en`)"
    await update.effective_message.reply_text(response, parse_mode="Markdown")


async def trending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    articles = get_trending_news()
    if articles:
        response = "\n\n".join(
            [f"🔥 *{escape_markdown(a['title'])}*\n{a['url']}" for a in articles]
        )
    else:
        response = "No trending news available at the moment."
    await update.effective_message.reply_text(response, parse_mode="Markdown")


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    if context.args:
        topic = " ".join(context.args)
        subscriptions = load_subscriptions()
        subscriptions[user_id] = topic
        save_subscriptions(subscriptions)
        await update.effective_message.reply_text(
            f"✅ You have subscribed to daily news on *{escape_markdown(topic)}*.",
            parse_mode="Markdown"
        )
    else:
        await update.effective_message.reply_text(
            "❌ Please provide a topic! Example: `/subscribe AI`"
        )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_chat.id)
    subscriptions = load_subscriptions()

    if user_id in subscriptions:
        del subscriptions[user_id]
        save_subscriptions(subscriptions)
        await update.effective_message.reply_text("❌ You have unsubscribed from news updates.")
    else:
        await update.effective_message.reply_text("ℹ️ You are not subscribed to any news topics.")


async def send_daily_news(app):
    subscriptions = load_subscriptions()
    for user_id, topic in subscriptions.items():
        articles = get_news(topic, "en")
        if articles:
            response = "\n\n".join(
                [f"📰 *{escape_markdown(a['title'])}*\n{a['url']}" for a in articles]
            )
        else:
            response = "No relevant news today."

        try:
            await app.bot.send_message(chat_id=int(user_id), text=response, parse_mode="Markdown")
        except Exception as e:
            print(f"Failed to send news to {user_id}: {e}")
async def schedule_news_delivery(app):
    """Schedules daily news delivery for subscribed users."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(send_daily_news, "cron", hour=9,
                      args=[app])  # Send at 9 AM
    scheduler.start()


async def view_subscriptions(update: Update,
                             context: ContextTypes.DEFAULT_TYPE):
    """Displays the user's subscribed topics."""
    user_id = str(update.effective_chat.id)
    subscriptions = load_subscriptions()

    if user_id in subscriptions:
        topic = subscriptions[user_id]
        await update.effective_message.reply_text(
            f"📌 You are subscribed to news on: **{topic}**")
    else:
        await update.effective_message.reply_text(
            "ℹ️ You are not subscribed to any news topics.")


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fetches summarized news articles on a topic."""
    if context.args:
        topic = " ".join(context.args)
        articles = get_news_summary(topic)

        if articles:
            response = "\n\n".join(articles)
        else:
            response = "No news summaries available for this topic."

    else:
        response = "Use `/summary <topic>` to get a quick breakdown of news stories."

    await update.message.reply_text(response, parse_mode="Markdown")


async def recommend(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Suggests news articles based on user interests."""
    user_id = str(update.message.chat.id)
    interests = load_interests()

    if user_id not in interests or not interests[user_id]:
        await update.message.reply_text(
            "ℹ️ You haven't searched for news yet. Try `/news AI` first!")
        return

    preferred_topic = interests[user_id][
        -1]  # Get the last topic they searched
    articles = get_news(preferred_topic,
                        "en")  # Fetch news in English by default

    if articles:
        response = (
            f"🔍 Based on your recent searches, you might like news on **{preferred_topic}**:\n\n"
            + "\n\n".join([f"📰 *{a['title']}*\n{a['url']}" for a in articles]))
    else:
        response = "❌ No new articles for your preferred topic."

    await update.message.reply_text(response, parse_mode="Markdown")


async def set_my_commands(application):
    commands = [
        BotCommand("start", "Start the bot and show info"),
        BotCommand("help", "Show help message"),
        BotCommand("news", "Get latest news on topic"),
        BotCommand("trending", "Show trending news"),
        BotCommand("summary", "Get news summary"),
        BotCommand("subscribe", "Subscribe to daily news"),
        BotCommand("unsubscribe", "Unsubscribe from news"),
        BotCommand("subscriptions", "View your subscriptions"),
        BotCommand("recommend", "Get personalized news"),
    ]
    await application.bot.set_my_commands(commands)


def main():
    """Starts the bot and schedules tasks."""
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("news", news))
    app.add_handler(CommandHandler("trending", trending))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("subscriptions", view_subscriptions))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("recommend", recommend))

    print("Bot is running...")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(schedule_news_delivery(app))

    loop.run_until_complete(set_my_commands(app))

    loop.create_task(schedule_news_delivery(app))

    app.run_polling()


if __name__ == '__main__':
    main()
