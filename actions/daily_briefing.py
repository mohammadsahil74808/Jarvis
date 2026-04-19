# actions/daily_briefing.py

import sys
import os
import subprocess
import requests
from datetime import datetime
from pathlib import Path

# Fix path for imports
def get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = get_base_dir()
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from memory.memory_manager import load_memory
from actions.news import news_report

def get_daily_briefing(
    parameters:     dict = None,
    player          = None,
    session_memory  = None,
) -> str:
    """
    Gathers data for a daily briefing: time, weather, news, and reminders.
    """
    now = datetime.now()
    time_str = now.strftime("%A, %B %d, %I:%M %p")
    
    # 1. Identity
    memory = load_memory()
    user_name = memory.get("identity", {}).get("name", {}).get("value", "Sahil")
    city = memory.get("identity", {}).get("city", {}).get("value")
    
    if not city:
        from core.geo import get_current_location
        city = get_current_location()
        print(f"[Briefing] No city in memory, detected: {city}")

    # 2. Weather (Open-Meteo Free API)
    weather_summary = f"Weather info for {city} is currently unavailable."
    try:
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=en&format=json"
        geo_res = requests.get(geo_url, timeout=5).json()
        if geo_res.get("results"):
            lat = geo_res["results"][0]["latitude"]
            lon = geo_res["results"][0]["longitude"]
            w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            w_res = requests.get(w_url, timeout=5).json()
            if "current_weather" in w_res:
                temp = w_res["current_weather"]["temperature"]
                weather_summary = f"The current temperature in {city} is {temp}°C."
    except Exception as e:
        print(f"[Briefing] Weather error: {e}")

    # 3. News (Top 3 from our news tool)
    try:
        news_data = news_report({"category": "world"})
        # Extract just the top 3 headlines if possible
        headlines = news_data.split("\n")[1:4] # Skip header, take 3
        news_summary = "Latest updates:\n" + "\n".join(headlines) if headlines else "No news updates found."
    except Exception:
        news_summary = "News updates are unavailable right now."

    # 4. Reminders (Query schtasks)
    reminders = []
    try:
        # Querying schtasks for MARKReminder tasks
        res = subprocess.run('schtasks /Query /FO CSV /NH', shell=True, capture_output=True, text=True)
        if res.returncode == 0:
            lines = res.stdout.strip().split('\n')
            for line in lines:
                if "MARKReminder_" in line:
                    parts = line.split(',')
                    if len(parts) >= 2:
                        name = parts[0].strip('"').replace("MARKReminder_", "")
                        # Task name usually has timestamp, we can't easily get the message here 
                        # without reading the XML, but we can report that reminders exist.
                        reminders.append(f"Scheduled reminder detected.")
    except Exception:
        pass
    
    reminders_status = f"You have {len(reminders)} pending reminder(s)." if reminders else "You have no pending reminders for today."

    # 5. Personality/Dynamic Suggestion
    # Check if there's a project to suggest
    projects = memory.get("projects", {})
    suggestion = ""
    if projects:
        proj_name = list(projects.keys())[0]
        suggestion = f"By the way, you were working on {proj_name.replace('_', ' ')} recently. Should we continue that?"

    # 6. Formatting for JARVIS
    # The return string will be processed by the Hinglish persona
    result = (
        f"DAILY BRIEFING DATA:\n"
        f"- Target User: {user_name}\n"
        f"- Current Time: {time_str}\n"
        f"- Location: {city}\n"
        f"- Weather: {weather_summary}\n"
        f"- News: {news_summary}\n"
        f"- Reminders: {reminders_status}\n"
        f"- Suggestion: {suggestion}\n"
        f"\nJarvis, please summarize this for Sahil in short conversational Hinglish (3-5 lines)."
    )
    
    if player:
        player.write_log(f"[Briefing] Data gathered for {user_name}.")
        
    return result

if __name__ == "__main__":
    print(get_daily_briefing())
