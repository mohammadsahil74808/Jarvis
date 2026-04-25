# actions/daily_briefing.py

import sys
import os
import subprocess
import requests
import json
from datetime import datetime
from pathlib import Path

# Fix path for imports
from core.config import BASE_DIR
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
    
    # 1. Identity & Personalized Context
    from memory.profile_manager import get_manager
    pm = get_manager()
    profile = pm.get_profile()
    
    user_name = profile["personal_info"].get("name", "Sahil")
    age = profile["personal_info"].get("age")
    city = profile["personal_info"].get("location", "Delhi")
    specialization = profile["personal_info"].get("specialization", "AI / ML")
    
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

    # 3. News
    try:
        news_data = news_report({"category": "technology"}) # Focused on Tech for Sahil
        headlines = news_data.split("\n")[1:4]
        news_summary = "Latest tech headlines:\n" + "\n".join(headlines) if headlines else "No tech news today."
    except Exception:
        news_summary = "News updates are unavailable."

    # 4. Reminders
    reminders_list = []
    try:
        reminders_file = BASE_DIR / "memory" / "reminders.json"
        if reminders_file.exists():
            with open(reminders_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                now_dt = datetime.now()
                for r in data:
                    try:
                        r_dt = datetime.strptime(r['datetime'], "%Y-%m-%d %H:%M")
                        if r_dt > now_dt:
                            reminders_list.append(f"{r['message']} at {r_dt.strftime('%I:%M %p')}")
                    except Exception:
                        pass
    except Exception as e:
        print(f"[Briefing] Reminder read error: {e}")
    
    reminders_status = f"You have {len(reminders_list)} pending reminders." if reminders_list else "No pending reminders for today."

    # 5. Personalized Suggestion
    suggestion = f"As an {specialization} student, maybe we should work on a new AI project today?"
    if profile["routine"]["commute"]:
        suggestion += f" Also, don't forget your commute from {profile['routine']['commute']}."

    # 6. Formatting for JARVIS
    result = (
        f"DAILY BRIEFING DATA:\n"
        f"- Target User: {user_name} ({age} years old)\n"
        f"- Current Time: {time_str}\n"
        f"- Location: {city}\n"
        f"- Specialization: {specialization}\n"
        f"- Weather: {weather_summary}\n"
        f"- News: {news_summary}\n"
        f"- Reminders: {reminders_status}\n"
        f"- Suggestion: {suggestion}\n"
        f"\nJarvis, greet Sahil as a respectful friend + elite assistant. "
        f"Summarize this in short conversational Hinglish (3-5 lines). "
        f"Mention his age or specialization naturally."
    )
    
    if player:
        player.write_log(f"[Briefing] Data gathered for {user_name}.")
        
    return result

if __name__ == "__main__":
    print(get_daily_briefing())
