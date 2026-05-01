"""
memory_manager.py — MARK XXV Hafıza Sistemi
============================================
Düzeltmeler:
  - _MEMORY_EVERY_N_TURNS: 3 → 1 (her turda kontrol)
  - Stage 1 YES/NO check daha geniş kriterlere sahip
  - Extraction prompt daha kapsamlı ve agresif
  - Projeleri, favori şeyleri, arkadaşları daha iyi yakalar
"""

import json, os, re
from datetime import datetime
from threading import RLock
from pathlib import Path
import sys


from core.config import BASE_DIR, get_gemini_client
MEMORY_PATH      = BASE_DIR / "memory" / "long_term.json"
_lock            = RLock()
MAX_VALUE_LENGTH = 400


def _empty_memory() -> dict:
    return {
        "identity":      {},
        "preferences":   {},
        "projects":      {},
        "patterns":      {},
        "relationships": {},
        "wishes":        {},
        "notes":         {}
    }


def load_memory() -> dict:
    if not MEMORY_PATH.exists():
        return _empty_memory()

    with _lock:
        try:
            data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                base = _empty_memory()
                for key in base:
                    if key not in data:
                        data[key] = {}
                return data
            return _empty_memory()
        except Exception as e:
            print(f"[Memory] ⚠️ Load error: {e}")
            return _empty_memory()


def save_memory(memory: dict) -> None:
    if not isinstance(memory, dict):
        return
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        MEMORY_PATH.write_text(
            json.dumps(memory, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )


def _truncate_value(val: str) -> str:
    if isinstance(val, str) and len(val) > MAX_VALUE_LENGTH:
        return val[:MAX_VALUE_LENGTH].rstrip() + "…"
    return val


def _recursive_update(target: dict, updates: dict) -> bool:
    changed = False
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue

        if isinstance(value, dict) and "value" not in value:
            if key not in target or not isinstance(target[key], dict):
                target[key] = {}
                changed = True
            if _recursive_update(target[key], value):
                changed = True
        else:
            if isinstance(value, dict) and "value" in value:
                new_val = _truncate_value(str(value["value"]))
            else:
                new_val = _truncate_value(str(value))

            entry    = {"value": new_val, "updated": datetime.now().strftime("%Y-%m-%d")}
            existing = target.get(key, {})
            if not isinstance(existing, dict) or existing.get("value") != new_val:
                target[key] = entry
                changed = True

    return changed


def update_memory(memory_update: dict) -> dict:
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory()

    with _lock:
        memory = load_memory()
        if _recursive_update(memory, memory_update):
            save_memory(memory)
            print(f"[Memory] 💾 Saved: {list(memory_update.keys())}")
        return memory



def should_extract_memory_local(user_text: str) -> bool:
    """
    Local regex check to avoid Gemini calls for every turn.
    Returns True if the text likely contains memorable facts.
    """
    # Patterns for names
    name_patterns = [
        r'\bmy name is\b', r'\bi am called\b', r'\bcall me\b',
        r'\bmera naam\b', r'\bmujhe .+ bulao\b'
    ]
    
    # Preferences and favorites
    pref_patterns = [
        r'\bi (like|love|prefer|enjoy|hate|dislike)\b',
        r'\bmy favorite\b', r'\bmujhe .+ pasand\b',
        r'\bmera favorite\b'
    ]
    
    # Personal information and status
    info_patterns = [
        r'\bi (work|live|study)\b', r'\bmy (job|city|age|birthday)\b',
        r'\bi\'m (from|a|an)\b', r'\bmain .+ hun\b',
        r'\bi want to\b', r'\bi need to\b'
    ]
    
    text_lower = user_text.lower()
    all_patterns = name_patterns + pref_patterns + info_patterns
    
    return any(re.search(p, text_lower) for p in all_patterns)


def should_extract_memory(user_text: str, jarvis_text: str, api_key: str) -> bool:
    """
    Stage 1: Pre-check (local only). API confirmation removed for speed.
    """
    # Local regex (Fast & Free)
    return should_extract_memory_local(user_text)


def extract_memory(user_text: str, jarvis_text: str, api_key: str) -> dict:
    """
    Stage 2: Detaylı çıkarım. Her iki tarafı da analiz eder.
    """
    try:
        client = get_gemini_client()

        combined = f"User: {user_text[:500]}\nJarvis: {jarvis_text[:300]}"

        response = client.models.generate_content(
            model="gemini-1.5-flash",
            contents=(
            f"Extract ALL memorable personal facts from this conversation. Any language.\n"
            f"Return ONLY valid JSON. Use {{}} if truly nothing is worth saving.\n\n"
            f"Category guide:\n"
            f"  identity      → name, age, birthday, city, country, job, school, nationality, language\n"
            f"  preferences   → ANY favorite or preferred thing:\n"
            f"                  favorite_food, favorite_color, favorite_music, favorite_film,\n"
            f"                  favorite_game, favorite_sport, favorite_book, favorite_artist,\n"
            f"                  favorite_country, hobbies, interests, dislikes, etc.\n"
            f"  projects      → projects being built, ongoing work, goals, ideas in progress\n"
            f"                  (e.g. mark_xxv: 'Building a JARVIS-like AI assistant')\n"
            f"  patterns      → recurring habits, routines, schedule, usual behavior\n"
            f"                  (e.g. coding_time: 'Usually codes late at night')\n"
            f"  relationships → people mentioned: friends, family, partner, colleagues\n"
            f"                  (e.g. best_friend_ali: 'Best friend, met in university')\n"
            f"  wishes        → future plans, things to buy, travel plans, dreams\n"
            f"  notes         → anything else worth remembering\n\n"
            f"IMPORTANT:\n"
            f"- Be LIBERAL: if something MIGHT be worth remembering, include it.\n"
            f"- Extract from BOTH user and Jarvis turns.\n"
            f"- Skip: weather, reminders, search results, one-time commands.\n"
            f"- Use concise English values regardless of conversation language.\n\n"
            f"Format:\n"
            f'{{"identity":{{"name":{{"value":"Ali"}}}},\n'
            f' "preferences":{{"favorite_color":{{"value":"blue"}}, "hobby":{{"value":"gaming"}}}},\n'
            f' "projects":{{"mark_xxv":{{"value":"JARVIS-like AI assistant on Windows"}}}},\n'
            f' "patterns":{{"coding_habit":{{"value":"Always listens to lo-fi while coding"}}}},\n'
            f' "relationships":{{"friend_yusuf":{{"value":"close friend"}}}},\n'
            f' "wishes":{{"buy_guitar":{{"value":"wants an acoustic guitar"}}}},\n'
            f' "notes":{{"special_info":{{"value":"Some other detail"}}}}}}\n\n'
            )
        )
        raw = response.text.strip()

        import re
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        if not raw or raw == "{}":
            return {}

        return json.loads(raw)

    except json.JSONDecodeError:
        return {}
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] ⚠️ Extract failed: {e}")
        return {}


def format_memory_for_prompt(memory: dict | None) -> str:
    if not memory:
        return ""

    lines = []

    identity  = memory.get("identity", {})
    id_fields = ["name", "age", "birthday", "city", "job", "language", "school", "nationality"]
    for field in id_fields:
        entry = identity.get(field)
        if entry:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"{field.title()}: {val}")
    for key, entry in identity.items():
        if key in id_fields:
            continue
        val = entry.get("value") if isinstance(entry, dict) else entry
        if val:
            lines.append(f"{key.replace('_', ' ').title()}: {val}")

    prefs = memory.get("preferences", {})
    if prefs:
        lines.append("")
        lines.append("Preferences:")
        for key, entry in list(prefs.items())[:15]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    projects = memory.get("projects", {})
    if projects:
        lines.append("")
        lines.append("Active Projects / Goals:")
        for key, entry in list(projects.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")
    
    patterns = memory.get("patterns", {})
    if patterns:
        lines.append("")
        lines.append("Patterns & Habits:")
        for key, entry in list(patterns.items())[:10]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    rels = memory.get("relationships", {})
    if rels:
        lines.append("")
        lines.append("People in their life:")
        for key, entry in list(rels.items())[:10]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    wishes = memory.get("wishes", {})
    if wishes:
        lines.append("")
        lines.append("Wishes / Plans / Wants:")
        for key, entry in list(wishes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key.replace('_', ' ').title()}: {val}")

    notes = memory.get("notes", {})
    if notes:
        lines.append("")
        lines.append("Other notes:")
        for key, entry in list(notes.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {key}: {val}")

    if not lines:
        return ""

    header = "[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]\n"
    result = header + "\n".join(lines)
    if len(result) > 2000:
        result = result[:1997] + "…"

    return result + "\n"


def remember(key: str, value: str, category: str = "notes") -> str:
    valid = {"identity", "preferences", "projects", "patterns", "relationships", "wishes", "notes"}
    if category not in valid:
        category = "notes"
    update_memory({category: {key: {"value": value}}})
    return f"Remembered: {category}/{key} = {value}"


def forget(key: str, category: str = "notes") -> str:
    memory = load_memory()
    cat    = memory.get(category, {})
    if key in cat:
        del cat[key]
        memory[category] = cat
        save_memory(memory)
        return f"Forgotten: {category}/{key}"
    return f"Not found: {category}/{key}"

# Alias — eski import'larla uyumluluk için
forget_memory = forget
