# core/tool_registry.py
import importlib

# Map of tool_name -> (module_path, function_name)
TOOL_REGISTRY = {
    "open_app": ("actions.open_app", "open_app"),
    "web_search": ("actions.web_search", "web_search"),
    "game_updater": ("actions.game_updater", "game_updater"),
    "browser_control": ("actions.browser_control", "browser_control"),
    "file_controller": ("actions.file_controller", "file_controller"),
    "cmd_control": ("actions.cmd_control", "cmd_control"),
    "code_helper": ("actions.code_helper", "code_helper"),
    "dev_agent": ("actions.dev_agent", "dev_agent"),
    "send_message": ("actions.send_message", "send_message"),
    "reminder": ("actions.reminder", "reminder"),
    "youtube_video": ("actions.youtube_video", "youtube_video"),
    "weather_report": ("actions.weather_report", "weather_action"),
    "computer_settings": ("actions.computer_settings", "computer_settings"),
    "desktop_control": ("actions.desktop", "desktop_control"),
    "computer_control": ("actions.computer_control", "computer_control"),
    "flight_finder": ("actions.flight_finder", "flight_finder"),
    "news_report": ("actions.news", "news_report"),
    "daily_briefing": ("actions.daily_briefing", "get_daily_briefing"),
    "system_doctor": ("actions.doctor", "run_doctor"),
    "file_manager": ("actions.file_manager", "file_manager"),
    # Old ones for compatibility during transition
    "screen_process": ("actions.screen_processor", "screen_process"),
    "screen_vision": ("actions.screen_vision", "screen_vision"),
    # New vision action to replace the old screen tools
    "vision_action": ("actions.vision_action", "vision_action")
}

def get_tool_callable(tool_name: str):
    """
    Returns the callable function for a given tool name from the registry.
    Returns None if not found or if import fails.
    """
    if tool_name not in TOOL_REGISTRY:
        return None
        
    module_path, func_name = TOOL_REGISTRY[tool_name]
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, func_name, None)
    except Exception as e:
        print(f"[TOOL REGISTRY ERROR] Failed to load '{tool_name}': {e}")
        return None
