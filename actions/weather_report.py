# actions/weather_report.py
# Weather via wttr.in (no API key, no browser needed)
# Fallback: opens Google weather in browser if API unreachable

import requests
from urllib.parse import quote_plus


# ── wttr.in format codes ──────────────────────────────────────────
# %l = location, %C = condition, %t = temperature, %h = humidity, %w = wind
_WTTR_URL       = "https://wttr.in/{city}?format=%l:+%C+%t,+Humidity:+%h,+Wind:+%w"
_WTTR_SIMPLE    = "https://wttr.in/{city}?format=3"   # shortest: "Delhi: ⛅ +32°C"
_WTTR_TIMEOUT   = 6   # seconds


def _fetch_wttr(city: str) -> str | None:
    """
    Fetch weather from wttr.in — completely free, no API key.
    Returns a spoken-ready string or None if unreachable.
    """
    try:
        url  = _WTTR_SIMPLE.format(city=quote_plus(city))
        resp = requests.get(url, timeout=_WTTR_TIMEOUT)
        if resp.status_code == 200:
            text = resp.text.strip()
            # wttr sometimes returns HTML on error
            if text and "<html" not in text.lower() and len(text) < 200:
                return text
    except Exception as e:
        print(f"[Weather] wttr.in error: {e}")
    return None


def weather_action(
    parameters: dict,
    player=None,
    session_memory=None
):
    """
    Weather report action.
    Primary  : wttr.in API — returns spoken temperature directly (no browser).
    Fallback : Opens Google weather in browser if API is unreachable.
    """
    city = parameters.get("city")
    time = parameters.get("time", "today")

    if not city or not isinstance(city, str):
        try:
            from core.geo import get_current_location
            city = get_current_location()
            print(f"[Weather] No city in parameters, detected: {city}")
        except Exception:
            city = None

    if not city:
        msg = "Sir, the city is missing for the weather report."
        _speak_and_log(msg, player)
        return msg

    city = city.strip()
    time = (time or "today").strip()

    # ── Primary: wttr.in (no browser, spoken data) ────────────────
    weather_data = _fetch_wttr(city)
    if weather_data:
        msg = f"Sir, the current weather: {weather_data}."
        _speak_and_log(msg, player)
        if session_memory:
            try:
                session_memory.set_last_search(query=f"weather {city}", response=msg)
            except Exception:
                pass
        return msg

    # ── Fallback: open browser (original behavior) ─────────────────
    print("[Weather] wttr.in unreachable — falling back to browser.")
    search_query  = f"weather in {city} {time}"
    encoded_query = quote_plus(search_query)
    url           = f"https://www.google.com/search?q={encoded_query}"

    from core.utils import open_browser
    if not open_browser(url):
        msg = "Sir, I couldn't reach weather data or open the browser."
        _speak_and_log(msg, player)
        return msg

    msg = f"Showing the weather for {city}, {time}, sir."
    _speak_and_log(msg, player)

    if session_memory:
        try:
            session_memory.set_last_search(query=search_query, response=msg)
        except Exception:
            pass

    return msg


def _speak_and_log(message: str, player=None):
    if player:
        try:
            player.write_log(f"JARVIS: {message}")
        except Exception:
            pass
