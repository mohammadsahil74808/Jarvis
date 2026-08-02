# actions/web_search.py
# MARK XXV — Web Search
# Primary: Gemini google_search (yeni google.genai SDK)
# Fallback: DuckDuckGo (ddgs)



import warnings
warnings.simplefilter("ignore")
warnings.showwarning = lambda *args, **kwargs: None

from core.config import get_gemini_client



from google.genai import types

def _gemini_search(query: str) -> str:
    client = get_gemini_client()
    response = None
    config = types.GenerateContentConfig(
        tools=[types.Tool(google_search=types.GoogleSearch())]
    )
    for model_name in ["models/gemini-2.5-flash", "gemini-2.0-flash"]:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=query,
                config=config,
            )
            if response and response.text:
                break
        except Exception:
            response = None

    if not response or not response.text:
        raise ValueError("Gemini search unavailable")

    return response.text.strip()



def _ddg_search(query: str, max_results: int = 6) -> list:
    DDGSClass = None
    import importlib
    try:
        ddgs_mod = importlib.import_module("ddgs")
        DDGSClass = getattr(ddgs_mod, "DDGS")
    except ImportError:
        try:
            ddgs_mod = importlib.import_module("duckduckgo_search")
            DDGSClass = getattr(ddgs_mod, "DDGS")
        except ImportError:
            return []
    
    results = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            # Try context manager first, fallback to direct instance
            try:
                with DDGSClass() as ddgs:
                    for r in ddgs.text(query, max_results=max_results):
                        results.append({
                            "title":   r.get("title", ""),
                            "snippet": r.get("body", ""),
                            "url":     r.get("href", ""),
                        })
            except TypeError:
                ddgs = DDGSClass()
                for r in ddgs.text(query, max_results=max_results):
                    results.append({
                        "title":   r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url":     r.get("href", ""),
                    })
    except Exception as e:
        print(f"[WebSearch] [WARNING] DDG error: {e}")
    return results

def _format_ddg(query: str, results: list) -> str:
    if not results:
        return f"No results found for: {query}"
    lines = [f"Search results for: {query}\n"]
    for i, r in enumerate(results, 1):
        if r.get("title"):   lines.append(f"{i}. {r['title']}")
        if r.get("snippet"): lines.append(f"   {r['snippet']}")
        if r.get("url"):     lines.append(f"   {r['url']}")
        lines.append("")
    return "\n".join(lines).strip()


def _compare(items: list, aspect: str) -> str:
    query = f"Compare {', '.join(items)} in terms of {aspect}. Give specific facts and data."
    try:
        return _gemini_search(query)
    except Exception as e:
        print(f"[WebSearch] [WARNING] Gemini compare failed: {e}")
        all_results = {}
        for item in items:
            try:
                all_results[item] = _ddg_search(f"{item} {aspect}", max_results=3)
            except Exception:
                all_results[item] = []
        lines = [f"Comparison — {aspect.upper()}\n{'─'*40}"]
        for item in items:
            lines.append(f"\n▸ {item}")
            for r in all_results.get(item, [])[:2]:
                if r.get("snippet"):
                    lines.append(f"  • {r['snippet']}")
        return "\n".join(lines)


def web_search(
    parameters:     dict,
    response=None,
    player=None,
    session_memory=None,
) -> str:
    params = parameters or {}
    query  = params.get("query", "").strip()
    mode   = params.get("mode", "search").lower()
    items  = params.get("items", [])
    aspect = params.get("aspect", "general")

    if not query and not items:
        return "Please provide a search query, sir."

    if items and mode != "compare":
        mode = "compare"

    if player:
        player.write_log(f"[Search] {query or ', '.join(items)}")

    print(f"[WebSearch] [SEARCH] Query: {query!r}  Mode: {mode}")

    try:
        if mode == "compare" and items:
            print(f"[WebSearch] [STATS] Comparing: {items}")
            result = _compare(items, aspect)
            print("[WebSearch] [OK] Compare done.")
            return result

        print("[WebSearch] [WEB] Gemini search...")
        try:
            result = _gemini_search(query)
            print("[WebSearch] [OK] Gemini OK.")
            return result
        except Exception as e:
            print(f"[WebSearch] [WARNING] Gemini failed ({e}), trying DDG...")
            results = _ddg_search(query)
            result  = _format_ddg(query, results)
            print(f"[WebSearch] [OK] DDG: {len(results)} results.")
            return result

    except Exception as e:
        print(f"[WebSearch] [ERROR] Failed: {e}")
        return f"Search failed, sir: {e}"
