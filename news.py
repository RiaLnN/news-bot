import os
import requests
from dotenv import load_dotenv

load_dotenv()
NEWS_API_KEY = os.getenv("NEWS_API_KEY")

def get_news(topic, language="en"):
    """Fetches relevant news for a given topic and language."""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": f'"{topic}"',  # Forces exact match
        "sortBy": "relevancy",  # Prioritizes relevant articles
        "language": language,
        "pageSize": 5,
        "apiKey": NEWS_API_KEY
    }

    response = requests.get(url, params=params)
    data = response.json()

    if data["status"] != "ok":
        return []

    return [{"title": a["title"], "url": a["url"]} for a in data["articles"]]
def get_news_summary(topic):
    """Fetches and summarizes news articles on a given topic."""
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": f'"{topic}"',    # Точное совпадение фразы
        "qInTitle": topic,      # Поиск ключевого слова в заголовках
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 3,
        "apiKey": NEWS_API_KEY
    }
    response = requests.get(url, params=params)
    # Для отладки можно раскомментировать:
    # print(f"DEBUG summary URL: {response.url}")
    data = response.json()
    if data.get("status") != "ok":
        return []
    summaries = []
    for article in data.get("articles", []):
        title = article.get("title")
        url = article.get("url")
        description = article.get("description") or "No summary available."
        summaries.append(f"📰 *{title}*\n_{description}_\n🔗 {url}")
    return summaries

def get_trending_news():
    """Fetch trending news headlines."""
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "country": "us",  # Trending news from the U.S.
        "pageSize": 5,
        "apiKey": NEWS_API_KEY
    }

    response = requests.get(url, params=params)
    data = response.json()

    if data["status"] != "ok":
        return []

    return [{"title": a["title"], "url": a["url"]} for a in data["articles"]]