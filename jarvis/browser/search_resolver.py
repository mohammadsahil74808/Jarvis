# jarvis/browser/search_resolver.py
"""
Structured Google search result identification, filtering, and target selection resolution.
Maintains pure architecture compatibility with existing Google Chrome DevTools/IPC sessions
without modifying browser instances, profiles, or lifecycles.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

ORDINAL_MAP = {
    "pehla": 1, "pehli": 1, "first": 1, "1st": 1, "ek": 1, "one": 1,
    "doosra": 2, "dusra": 2, "second": 2, "2nd": 2, "two": 2,
    "teesra": 3, "tisra": 3, "third": 3, "3rd": 3, "three": 3, "teen": 3,
    "chautha": 4, "chauthi": 4, "fourth": 4, "4th": 4, "four": 4, "chaar": 4,
    "panchva": 5, "panchvi": 5, "fifth": 5, "5th": 5, "five": 5, "paanch": 5,
    "chathha": 6, "chatha": 6, "sixth": 6, "6th": 6, "six": 6, "che": 6,
    "saatva": 7, "saatvi": 7, "seventh": 7, "7th": 7, "seven": 7, "saat": 7,
    "aathva": 8, "aathvi": 8, "eighth": 8, "8th": 8, "eight": 8, "aath": 8,
    "navma": 9, "navmi": 9, "ninth": 9, "9th": 9, "nine": 9, "nau": 9,
    "dasva": 10, "dasvi": 10, "tenth": 10, "10th": 10, "ten": 10, "das": 10,
}


def build_structured_search_results(raw_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filters raw search links to isolate pure organic web-search results.
    Ignores Google navigation, ads/sponsored content, 'People also ask', related searches, and footer links.
    """
    structured_results = []
    seen_urls = set()
    rank = 1

    for item in raw_items:
        url = str(item.get("url") or item.get("href") or "").strip()
        title = str(item.get("title") or "").strip()
        snippet = str(item.get("snippet") or item.get("body") or item.get("description") or "").strip()
        element_ref = str(item.get("element_ref") or item.get("target") or item.get("selector") or f'a[href="{url}"]')

        if not url or not url.startswith(("http://", "https://")):
            continue

        # Clean tracking params or anchors for deduping
        clean_url = url.split("#")[0].strip().rstrip("/")
        if clean_url in seen_urls:
            continue

        combined_text = f"{title} {snippet} {element_ref} {url}".lower()

        # 1. Ignore Google navigation links & internal services
        if any(domain in url.lower() for domain in [
            "google.com/search", "google.com/url", "google.com/preferences",
            "support.google.", "accounts.google.", "policies.google.", "myactivity.google.",
            "maps.google.", "google.co.in/search", "google.co.uk/search", "gstatic.com",
            "googleusercontent.com", "google.com/imghy", "google.com/news", "google.com/videos"
        ]):
            continue

        # 2. Ignore sponsored/ad sections
        if any(ad_kw in combined_text for ad_kw in [
            "sponsored", "advertisement", "why this ad", "data-text-ad", "ad· ", " ad "
        ]) or title.lower().startswith("ad ") or title.lower().endswith(" ad") or item.get("is_ad"):
            continue

        # 3. Ignore "People also ask" and related searches
        if any(paa_kw in combined_text for paa_kw in [
            "people also ask", "related searches", "people search for",
            "people also search for", "more to ask", "accordion"
        ]) or item.get("is_paa"):
            continue

        # 4. Ignore footer and settings links
        if any(ft_kw in combined_text for ft_kw in [
            "privacy policy", "terms of service", "send feedback",
            "search settings", "advanced search", "google account", "footer"
        ]):
            continue

        result_entry = {
            "rank": rank,
            "number": rank,
            "title": title or url,
            "url": url,
            "snippet": snippet,
            "target": element_ref,
            "element_ref": element_ref,
            "clickable_target": element_ref
        }
        structured_results.append(result_entry)
        seen_urls.add(clean_url)
        rank += 1

        if rank > 20:
            break

    return structured_results


def is_search_result_request(target: str) -> bool:
    """
    Determines if a target string is requesting to select or open a stored search result
    (e.g., 'pehla result kholo', 'first result', 'result number 2').
    """
    if not target or target.startswith(("http://", "https://", "www.")):
        return False
    t_lower = target.lower().strip()

    # Explicit mention of 'result' or ordinals with common action words
    if "result" in t_lower:
        return True
    if re.search(r'\b(pehla|pehli|doosra|dusra|teesra|tisra|chautha|panchva|first|second|third|fourth|fifth|1st|2nd|3rd|4th|5th)\b', t_lower):
        if any(w in t_lower for w in ["kholo", "open", "click", "select", "chuno", "show"]):
            return True

    # Simple number references when context expects a choice
    if re.match(r'^#?[1-9][0-9]*$', t_lower):
        return True

    return False


def resolve_search_result_target(target: str, results: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Resolves the user's requested target against the structured search-result list.
    Supports ordinals (first, second, pehla, doosra), explicit numbering (result number 2, #2),
    and title/content-based queries ('Open the result about OpenAI').
    """
    if not results:
        return None

    t_lower = target.lower().strip()

    # Check if the query indicates explicit content/title matching (e.g., 'about', 'contains', 'whose title', 'named')
    is_explicit_title_query = any(kw in t_lower for kw in ["about", "contains", "whose", "title", "named", "titled", "regarding"])

    # Stage 1: Attempt Ordinal / Numerical resolution (if not an explicit title query)
    if not is_explicit_title_query:
        target_rank = None

        # Check explicit digit patterns like 'result number 2', 'result 2', '#2', '2nd result'
        num_match = re.search(r'(?:result|no\.?|number|rank|nambar|#)\s*([1-9][0-9]*)', t_lower)
        if not num_match:
            num_match = re.search(r'\b([1-9][0-9]*)(?:st|nd|rd|th)\b', t_lower)
        if not num_match:
            num_match = re.match(r'^#?([1-9][0-9]*)$', t_lower)
        if not num_match and "result" in t_lower:
            # Catch trailing number in phrases like 'open result 4' or 'result 4 kholo'
            num_match = re.search(r'result\s+([1-9][0-9]*)', t_lower)

        if num_match:
            try:
                target_rank = int(num_match.group(1))
            except ValueError:
                target_rank = None

        # Check ordinal words in map if no digit matched
        if target_rank is None:
            # Sort words by length descending so longer compound words match first
            sorted_words = sorted(ORDINAL_MAP.keys(), key=len, reverse=True)
            for word in sorted_words:
                if re.search(r'\b' + word + r'\b', t_lower):
                    # For simple words like 'one', 'do', ensure 'result' or rank context is present to avoid false positives
                    if word in ("one", "do", "ek", "teen", "four", "five", "six", "seven", "eight", "nine", "ten") and "result" not in t_lower and "number" not in t_lower:
                        continue
                    target_rank = ORDINAL_MAP[word]
                    break

        if target_rank is not None:
            for r in results:
                if r.get("rank") == target_rank or r.get("number") == target_rank:
                    return r
            # Fallback index if rank key differed
            if 1 <= target_rank <= len(results):
                return results[target_rank - 1]

    # Stage 2: Title & Content resolution
    # Remove conversational fillers to isolate keyword(s)
    filler_words = [
        "open", "the", "search", "result", "about", "whose", "title", "contains", "named", "titled",
        "kholo", "click", "on", "karo", "pe", "par", "me", "mein", "for", "link", "web", "page",
        "regarding", "show", "navigate", "to"
    ]
    cleaned = t_lower
    for fw in filler_words:
        cleaned = re.sub(r'\b' + fw + r'\b', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    if not cleaned:
        # If nothing remained after cleaning and we didn't match ordinals, default to rank 1 only if 'result' was explicitly requested
        if "result" in t_lower and len(results) >= 1:
            return results[0]
        return None

    # Try exact word/substring match against title, url, or snippet
    keywords = [w for w in cleaned.split() if len(w) > 1]
    best_match = None
    best_score = -1

    for r in results:
        title_text = str(r.get("title") or "").lower()
        url_text = str(r.get("url") or "").lower()
        snippet_text = str(r.get("snippet") or "").lower()
        combined = f"{title_text} {url_text} {snippet_text}"

        score = 0
        if cleaned in title_text:
            score += 10
        elif cleaned in url_text:
            score += 8
        elif cleaned in snippet_text:
            score += 5

        for kw in keywords:
            if kw in title_text:
                score += 3
            elif kw in url_text:
                score += 2
            elif kw in snippet_text:
                score += 1

        if score > 0 and score > best_score:
            best_score = score
            best_match = r

    return best_match


def extract_organic_search_results(query: str, dom_items: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """
    Extracts organic search results using DOM inspection items if available,
    falling back to clean HTML search structure scraping without requiring external API libraries.
    """
    raw_items = []

    # 1. Use direct live DOM inspection items from Chrome session if provided
    if dom_items:
        raw_items.extend(dom_items)

    structured = build_structured_search_results(raw_items)
    if structured:
        return structured

    # 2. Direct HTML scraping fallback using standard HTTP library with full browser headers (No external APIs or keys)
    import urllib.parse
    try:
        import bs4
        import requests
    except ImportError:
        return structured

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    # Try Google HTML search first
    try:
        r = requests.get(
            f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}&gbv=1",
            headers=headers,
            timeout=5
        )
        if r.status_code == 200 and "enablejs" not in r.url:
            soup = bs4.BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if "/url?q=" in href:
                    clean_url = urllib.parse.unquote(href.split("/url?q=")[1].split("&")[0])
                elif href.startswith(("http://", "https://")) and "google." not in href:
                    clean_url = href
                else:
                    continue

                if "enablejs" in clean_url or not clean_url.startswith(("http://", "https://")):
                    continue

                heading = a.find(["h3", "h4", "h2"]) or (a.parent and a.parent.find(["h3", "h4", "h2"]))
                title = heading.get_text(separator=" ", strip=True) if heading else a.get_text(separator=" ", strip=True)
                if not title or title.startswith("http") or len(title) < 2:
                    continue

                container = a.find_parent(["div", "article", "li", "section"])
                snippet = container.get_text(separator=" ", strip=True) if container else ""
                snippet = snippet.replace(title, "").replace(clean_url, "").strip()

                raw_items.append({
                    "title": title,
                    "url": clean_url,
                    "snippet": snippet,
                    "element_ref": f'a[href="{clean_url}"]'
                })
    except Exception as e:
        print(f"[DOM HTML EXTRACTION WARNING] Google direct fetch failed: {e}")

    structured = build_structured_search_results(raw_items)
    if structured:
        return structured

    # 3. Clean HTML search extraction fallback (When Google returns enablejs challenge in scriptless HTTP mode)
    try:
        r = requests.get(
            f"https://html.duckduckgo.com/html/?q={urllib.parse.quote_plus(query)}",
            headers=headers,
            timeout=6
        )
        if r.status_code == 200:
            soup = bs4.BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", class_="result__a", href=True):
                href = a["href"]
                if "y.js?" in href or "ad_" in href or "bing.com/aclick" in href:
                    continue
                if "uddg=" in href:
                    clean_url = urllib.parse.unquote(href.split("uddg=")[1].split("&")[0])
                elif href.startswith(("http://", "https://")):
                    clean_url = href
                else:
                    continue

                if not clean_url or "duckduckgo.com" in clean_url or "wix.com/lp" in clean_url:
                    continue

                title = a.get_text(strip=True)
                container = a.find_parent(["div", "li", "article"]) or a.parent
                snippet_el = container.find(["a", "div", "span"], class_="result__snippet") if container else None
                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                raw_items.append({
                    "title": title or clean_url,
                    "url": clean_url,
                    "snippet": snippet,
                    "element_ref": f'a[href="{clean_url}"]'
                })
    except Exception as e:
        print(f"[DOM HTML EXTRACTION WARNING] Fallback HTML search extraction failed: {e}")

    return build_structured_search_results(raw_items)
