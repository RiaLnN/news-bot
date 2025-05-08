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
        "q": topic,
        "sortBy": "publishedAt",
        "language": "en",
        "pageSize": 3,  # Fetch 3 articles
        "apiKey": NEWS_API_KEY
    }

    response = requests.get(url, params=params)
    data = response.json()

    if data["status"] != "ok":
        return []

    summaries = []
    for article in data["articles"]:
        title = article["title"]
        url = article["url"]
        description = article["description"]  # Short article description

        if not description:
            description = "No summary available."

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