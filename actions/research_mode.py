import json
import requests
import warnings
from bs4 import BeautifulSoup
from newspaper import Article
from concurrent.futures import ThreadPoolExecutor

# Try to import DDGS exactly like web_search.py
def _ddg_search(query: str, max_results: int = 5) -> list:
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []
    
    results = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                url = r.get("href") or r.get("link")
                if url: results.append(url)
    except Exception as e:
        print(f"[ResearchMode] DDG search error: {e}")
    return results

def extract_article(url: str):
    """Robust extraction with Newspaper3k and BeautifulSoup fallbacks."""
    user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    headers = {"User-Agent": user_agent}
    try:
        article = Article(url, browser_user_agent=user_agent)
        article.download()
        article.parse()
        if len(article.text.strip()) > 300:
            return {"title": article.title, "text": article.text, "url": url, "success": True}
    except Exception: pass

    try:
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        title = soup.find('title').get_text() if soup.find('title') else url
        text = "\n".join([p.get_text() for p in soup.find_all('p') if len(p.get_text()) > 40])
        if len(text.strip()) > 200:
            return {"title": title, "text": text, "url": url, "success": True}
    except Exception: pass
    
    return {"url": url, "success": False}

def research_mode(parameters: dict, **kwargs) -> str:
    action = parameters.get("action", "research").lower()
    query = parameters.get("query", "")
    mode = parameters.get("research_mode", "general").lower()
    max_sites = parameters.get("max_sites", 3)
    
    if not query: return "Sir, please provide a research topic."

    print(f"[ResearchMode] Initiating {mode} research for: {query}")

    search_query = query
    if mode == "upsc": search_query += " UPSC IAS analysis"
    elif mode == "tech": search_query += " technical documentation"
    elif mode == "news": search_query += " news latest"

    # 1. Search for URLs
    urls = _ddg_search(search_query, max_results=max_sites)
    if not urls:
        return f"I couldn't find any sources for '{query}' Online, sir."

    # 2. Extract content in parallel
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(extract_article, urls))
        valid_articles = [r for r in results if r['success']]

    if not valid_articles:
        return f"I found the links, but I couldn't access their content, sir. Try searching manually for: {urls[0]}"

    if action == "research":
        report = [f"### Research Report: {query} ({mode.upper()})\n"]
        for i, a in enumerate(valid_articles, 1):
            report.append(f"**[{i}] {a['title']}**\nURL: {a['url']}\n{a['text'][:1000]}...\n")
        return "\n".join(report)

    # For summarize/compare, we return larger snippets for the AI to process
    return f"Gathered Research Data ({len(valid_articles)} sources):\n\n" + \
           "\n\n".join([f"SOURCE: {a['title']}\nTEXT: {a['text'][:3000]}" for a in valid_articles])
