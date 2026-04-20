
# actions/news.py

import sys
import json
import requests
import xml.etree.ElementTree as ET
from pathlib import Path

def news_report(
    parameters:     dict,
    player          = None,
    session_memory  = None,
) -> str:
    """
    Fetches top news headlines from Google News RSS.
    """
    category = parameters.get("category", "world").lower()
    
    # Mapping friendly names to Google News TOPIC IDs
    topic_map = {
        "world":         "WORLD",
        "india":         "NATION",
        "technology":    "TECHNOLOGY",
        "tech":          "TECHNOLOGY",
        "business":      "BUSINESS",
        "entertainment": "ENTERTAINMENT",
        "sports":        "SPORTS",
        "science":       "SCIENCE",
        "health":        "HEALTH"
    }
    
    topic_id = topic_map.get(category, "WORLD")
    
    # Base RSS URL
    if topic_id == "WORLD" and category != "world":
        # General top stories if category not explicitly mapped
        url = "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"
    elif category == "world":
         url = "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-IN&gl=IN&ceid=IN:en"
    else:
        url = f"https://news.google.com/rss/headlines/section/topic/{topic_id}?hl=en-IN&gl=IN&ceid=IN:en"

    print(f"[News] 🗞️ Fetching {category} news from: {url}")
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        root = ET.fromstring(response.content)
        items = root.findall("./channel/item")
        
        if not items:
            return "Sir, I couldn't find any recent news updates at the moment."
        
        headlines = []
        for i, item in enumerate(items[:5]):
            title = item.find("title").text
            # Clean headline: "Headline - Source" -> "Headline"
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
            headlines.append(f"{i+1}. {title}")
            
        header = f"Top {category.capitalize()} News Headlines:\n"
        result = header + "\n".join(headlines)
        
        if player:
            player.write_log(f"[News] {category} headlines fetched.")
            
        return result

    except Exception as e:
        print(f"[News] ❌ Error: {e}")
        return f"Sir, I encountered an error while fetching the news: {e}"

if __name__ == "__main__":
    # Test
    print(news_report({"category": "india"}))
