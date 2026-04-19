import time
import os
import sys
from datetime import datetime
from actions.open_app import open_app, close_app_by_name
from actions.computer_settings import computer_settings
from actions.reminder import reminder
from actions.browser_control import browser_control

def workflow_chains(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None
) -> str:
    """
    Executes a chain of actions based on the selected mode.
    
    parameters:
        - mode: "study", "coding", "relax", "presentation"
    """
    mode = parameters.get("mode", "").lower().strip()
    results = []

    if mode == "study":
        results.append("Starting Study Mode...")
        # 1. Open notes (Obsidian)
        results.append(open_app({"app_name": "Obsidian"}, player=player))
        # 2. Open browser to educational site
        results.append(open_app({"app_name": "edge"}, player=player))
        # 3. Close distractions
        for app in ["Discord", "Spotify", "Steam"]:
            close_app_by_name(app)
        results.append("Minimized distractions.")
        # 4. Low volume
        results.append(computer_settings({"action": "volume_set", "value": "20"}, player=player))
        # 5. Start timer (25 mins)
        now = datetime.now()
        target_time = time.strftime("%H:%M", time.localtime(time.time() + 25*60))
        target_date = now.strftime("%Y-%m-%d")
        results.append(reminder({"date": target_date, "time": target_time, "message": "Study session complete! Take a break."}, player=player))
        
        return "Study mode ready. Notes open, distractions minimized, and 25-minute timer set."

    elif mode == "coding":
        results.append("Initializing Coding Mode...")
        # 1. Open VS Code
        results.append(open_app({"app_name": "Visual Studio Code"}, player=player))
        # 2. Open GitHub
        results.append(open_app({"app_name": "edge"}, player=player))
        # 3. Open Terminal
        results.append(open_app({"app_name": "cmd"}, player=player))
        
        return "Coding mode ready. VS Code, Terminal, and GitHub are open."

    elif mode == "relax":
        results.append("Activating Relax Mode...")
        # 1. Open Music
        results.append(open_app({"app_name": "Spotify"}, player=player))
        # 2. Dim brightness
        results.append(computer_settings({"action": "brightness_down"}, player=player))
        results.append(computer_settings({"action": "brightness_down"}, player=player))
        # 3. Notifications quiet (Focus mode if possible, else just mute sounds)
        results.append(computer_settings({"action": "mute"}, player=player))
        
        return "Relax mode ready. Music is playing and lights (brightness) dimmed."

    elif mode == "presentation":
        results.append("Preparing Presentation Mode...")
        # 1. Close popups/messengers
        for app in ["WhatsApp", "Telegram", "Discord", "Slack"]:
            close_app_by_name(app)
        # 2. Toggle Focus/DND via shortcut if possible (Win+N or similar, but let's just use mute)
        results.append(computer_settings({"action": "mute"}, player=player))
        # 3. Hide desktop icons (if supported via desktop tool)
        from actions.desktop import desktop_control
        results.append(desktop_control({"action": "organize"}, player=player))
        
        return "Presentation mode ready. Messaging apps closed and notifications muted."

    else:
        return f"Sir, I don't have a workflow defined for '{mode}' yet."
