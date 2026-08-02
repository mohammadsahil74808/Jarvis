"""
memory_manager.py — MARK XXV Persistent Memory Layer (SQLite-Backed)
====================================================================
Architecture Note:
  This module implements the structured persistent memory layer for JARVIS using
  SQLite (C:\\Projects\\Jarvis\\data\\jarvis.db). It replaces static JSON dumps with
  unique UUIDs, ISO timestamps, clear category tracking, safe relevant retrieval,
  sensitive information filtering, and graceful non-fatal fallback.
"""

import os, sqlite3, json, uuid, re, difflib
from datetime import datetime, timezone
from threading import RLock
from pathlib import Path
from core.config import BASE_DIR, get_gemini_client

_lock = RLock()
MAX_VALUE_LENGTH = 500

# Database Target (Shared with SQLite MCP Server)
DB_DIR = BASE_DIR / "data"
DB_PATH = DB_DIR / "jarvis.db"
LEGACY_JSON_PATH = BASE_DIR / "memory" / "long_term.json"

# Standardized Categories
CATEGORIES = ("user_preference", "project_context", "important_fact", "task_context")

# Legacy mapping for backward compatibility
CATEGORY_MAP = {
    "preferences":   "user_preference",
    "patterns":      "user_preference",
    "wishes":        "user_preference",
    "projects":      "project_context",
    "identity":      "important_fact",
    "relationships": "important_fact",
    "notes":         "task_context",
}

_SQLITE_AVAILABLE = True
_FALLBACK_MEMORY = None

def _empty_memory() -> dict:
    base = {cat: {} for cat in CATEGORIES}
    for old_cat in CATEGORY_MAP.keys():
        if old_cat not in base:
            base[old_cat] = {}
    return base

def normalize_category(category: str) -> str:
    cat_lower = (category or "task_context").lower().strip()
    if cat_lower in CATEGORIES:
        return cat_lower
    return CATEGORY_MAP.get(cat_lower, "task_context")

def contains_sensitive_data(text: str) -> bool:
    """
    Regex checks to prevent automatic or tool storage of sensitive secrets
    (credit cards, passwords, API keys, PINs, SSN/IDs, financial credentials).
    """
    if not text or not isinstance(text, str):
        return False
    
    patterns = [
        r'\b(?:\d[ -]*?){13,16}\b',
        r'\b(?:sk-[A-Za-z0-9]{20,}|AIza[0-9A-Za-z-_]{35}|ghp_[A-Za-z0-9]{36}|ey[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+)\b',
        r'(?:password|passwd|secret|api_key|token|access_key|private_key)\s*[:=]\s*\S+',
        r'\b\d{3}-\d{2}-\d{4}\b',
        r'(?:cvv|cvc|routing number|bank account|card expiry|pin number)\s*[:=]\s*\S+',
        r'\b(?:my pin is|password is|secret is)\s+\S+'
    ]
    
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False

def _get_db_connection() -> sqlite3.Connection | None:
    global _SQLITE_AVAILABLE
    if not _SQLITE_AVAILABLE:
        return None
    try:
        DB_DIR.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False, timeout=5.0)
        conn.row_factory = sqlite3.Row
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    created_at DATETIME NOT NULL,
                    updated_at DATETIME NOT NULL,
                    UNIQUE(category, key)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_category ON memories(category)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_updated ON memories(updated_at)")
        return conn
    except Exception as e:
        print(f"[Memory] [WARN]: SQLite DB initialization/connection failed ({e}). Falling back to in-memory non-fatal mode.")
        _SQLITE_AVAILABLE = False
        return None

def _migrate_legacy_json_if_needed():
    """Migrates older long_term.json memories into SQLite DB once upon startup."""
    if not LEGACY_JSON_PATH.exists():
        return
    conn = _get_db_connection()
    if not conn:
        return
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM memories")
        if cursor.fetchone()["cnt"] > 0:
            return  # Already has records in SQLite
        
        data = json.loads(LEGACY_JSON_PATH.read_text(encoding="utf-8"))
        for cat, entries in data.items():
            norm_cat = normalize_category(cat)
            if isinstance(entries, dict):
                for k, v in entries.items():
                    val_str = str(v.get("value") if isinstance(v, dict) and "value" in v else v)
                    if not val_str.strip() or contains_sensitive_data(val_str):
                        continue
                    now_str = datetime.now(timezone.utc).isoformat()
                    mem_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT OR IGNORE INTO memories (id, category, key, value, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (mem_id, norm_cat, k.lower().strip(), val_str[:MAX_VALUE_LENGTH], now_str, now_str))
        conn.commit()
        print("[Memory] [OK] Successfully migrated legacy long_term.json entries into SQLite DB.")
    except Exception as e:
        print(f"[Memory] Notice during legacy migration: {e}")
    finally:
        conn.close()

_migrate_legacy_json_if_needed()

def load_memory() -> dict:
    """
    Loads all current memories into a structured dictionary grouped by category.
    Returns format compatible with legacy JARVIS inspection routines.
    """
    global _FALLBACK_MEMORY
    with _lock:
        conn = _get_db_connection()
        if not conn:
            if _FALLBACK_MEMORY is None:
                _FALLBACK_MEMORY = _empty_memory()
            return _FALLBACK_MEMORY

        try:
            res = _empty_memory()
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, key, value, created_at, updated_at FROM memories ORDER BY updated_at DESC")
            for row in cursor.fetchall():
                cat = row["category"]
                k = row["key"]
                entry = {
                    "id": row["id"],
                    "value": row["value"],
                    "created": row["created_at"],
                    "updated": row["updated_at"]
                }
                if cat not in res:
                    res[cat] = {}
                res[cat][k] = entry
            return res
        except Exception as e:
            print(f"[Memory] [WARN] load_memory error: {e}")
            if _FALLBACK_MEMORY is None:
                _FALLBACK_MEMORY = _empty_memory()
            return _FALLBACK_MEMORY
        finally:
            conn.close()

def save_memory(memory: dict) -> None:
    """
    Synchronizes a full dictionary structure back into SQLite memories table.
    Used mainly when legacy tools or tests call save_memory directly.
    """
    if not isinstance(memory, dict):
        return
    with _lock:
        conn = _get_db_connection()
        if not conn:
            global _FALLBACK_MEMORY
            _FALLBACK_MEMORY = memory
            return
        
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            with conn:
                for cat, items in memory.items():
                    norm_cat = normalize_category(cat)
                    if not isinstance(items, dict):
                        continue
                    for k, val_obj in items.items():
                        if val_obj is None:
                            continue
                        val_str = str(val_obj.get("value") if isinstance(val_obj, dict) and "value" in val_obj else val_obj)
                        if not val_str.strip() or contains_sensitive_data(val_str):
                            continue
                        val_trunc = val_str[:MAX_VALUE_LENGTH]
                        
                        cursor = conn.cursor()
                        cursor.execute("SELECT id FROM memories WHERE category = ? AND key = ?", (norm_cat, k))
                        row = cursor.fetchone()
                        if row:
                            cursor.execute("""
                                UPDATE memories SET value = ?, updated_at = ? WHERE category = ? AND key = ?
                            """, (val_trunc, now_str, norm_cat, k))
                        else:
                            mem_id = str(uuid.uuid4())
                            cursor.execute("""
                                INSERT INTO memories (id, category, key, value, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (mem_id, norm_cat, k, val_trunc, now_str, now_str))
        except Exception as e:
            print(f"[Memory] [WARN] save_memory sync error: {e}")
        finally:
            conn.close()

def _truncate_value(val: str) -> str:
    if isinstance(val, str) and len(val) > MAX_VALUE_LENGTH:
        return val[:MAX_VALUE_LENGTH].rstrip() + "..."
    return val

def _find_similar_key(new_key: str, existing_keys: list) -> str:
    matches = difflib.get_close_matches(new_key, existing_keys, n=1, cutoff=0.85)
    if matches:
        return matches[0]
    return new_key

def update_memory(memory_update: dict) -> dict:
    """
    Updates memory entries cleanly with SQLite atomic persistence, UUIDs, and timestamps.
    """
    if not isinstance(memory_update, dict) or not memory_update:
        return load_memory()

    with _lock:
        conn = _get_db_connection()
        now_str = datetime.now(timezone.utc).isoformat()
        saved_keys = []
        
        if not conn:
            mem = load_memory()
            for cat, items in memory_update.items():
                norm_cat = normalize_category(cat)
                if norm_cat not in mem:
                    mem[norm_cat] = {}
                if isinstance(items, dict):
                    for k, v_obj in items.items():
                        v_str = str(v_obj.get("value") if isinstance(v_obj, dict) and "value" in v_obj else v_obj)
                        if not v_str.strip() or contains_sensitive_data(v_str):
                            continue
                        mem[norm_cat][k] = {"id": str(uuid.uuid4()), "value": v_str[:MAX_VALUE_LENGTH], "updated": now_str}
                        saved_keys.append(k)
            print(f"[Memory (Fallback)] [SAVE] Saved: {saved_keys}")
            return mem

        try:
            with conn:
                cursor = conn.cursor()
                for cat, items in memory_update.items():
                    norm_cat = normalize_category(cat)
                    if not isinstance(items, dict):
                        continue
                    for k, val_obj in items.items():
                        if val_obj is None:
                            continue
                        val_str = str(val_obj.get("value") if isinstance(val_obj, dict) and "value" in val_obj else val_obj)
                        if not val_str.strip():
                            continue
                        
                        if contains_sensitive_data(val_str):
                            print(f"[Memory Security] Blocked storing sensitive content for key: '{k}'")
                            continue

                        val_trunc = _truncate_value(val_str)
                        
                        cursor.execute("SELECT key FROM memories WHERE category = ?", (norm_cat,))
                        existing = [r["key"] for r in cursor.fetchall()]
                        actual_key = _find_similar_key(k.lower().strip(), existing)
                        
                        cursor.execute("SELECT id FROM memories WHERE category = ? AND key = ?", (norm_cat, actual_key))
                        row = cursor.fetchone()
                        if row:
                            cursor.execute("""
                                UPDATE memories SET value = ?, updated_at = ? WHERE category = ? AND key = ?
                            """, (val_trunc, now_str, norm_cat, actual_key))
                        else:
                            mem_id = str(uuid.uuid4())
                            cursor.execute("""
                                INSERT INTO memories (id, category, key, value, created_at, updated_at)
                                VALUES (?, ?, ?, ?, ?, ?)
                            """, (mem_id, norm_cat, actual_key, val_trunc, now_str, now_str))
                        saved_keys.append(actual_key)
            if saved_keys:
                print(f"[Memory] [SAVE] Saved to SQLite: {saved_keys}")
        except Exception as e:
            print(f"[Memory] [WARN] update_memory error: {e}")
        finally:
            conn.close()
        
        return load_memory()

def retrieve_relevant_memories(query: str = "", category: str = None, limit: int = 5) -> list[dict]:
    """
    Safe Contextual Memory Retrieval:
    Retrieves memories relevant to the query or category without dumping unrelated facts.
    """
    with _lock:
        conn = _get_db_connection()
        results = []
        if not conn:
            mem = load_memory()
            for cat_key, items in mem.items():
                if category and normalize_category(category) != cat_key:
                    continue
                for k, v in items.items():
                    if query and query.lower() not in k.lower() and query.lower() not in str(v.get("value", "")).lower():
                        continue
                    results.append({
                        "id": v.get("id", str(uuid.uuid4())),
                        "category": cat_key,
                        "key": k,
                        "value": v.get("value", str(v)),
                        "updated_at": v.get("updated", "")
                    })
            return results[:limit]

        try:
            cursor = conn.cursor()
            sql = "SELECT id, category, key, value, created_at, updated_at FROM memories WHERE 1=1"
            params = []
            if category:
                sql += " AND category = ?"
                params.append(normalize_category(category))
            
            if query and query.strip():
                keywords = [w.strip() for w in query.lower().split() if len(w) > 2]
                if keywords:
                    clauses = []
                    for kw in keywords:
                        clauses.append("(LOWER(key) LIKE ? OR LOWER(value) LIKE ?)")
                        params.extend([f"%{kw}%", f"%{kw}%"])
                    sql += " AND (" + " OR ".join(clauses) + ")"
            
            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "category": row["category"],
                    "key": row["key"],
                    "value": row["value"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"]
                })
        except Exception as e:
            print(f"[Memory] [WARN] retrieve_relevant_memories error: {e}")
        finally:
            conn.close()
        
        return results

def format_memory_for_prompt(memory: dict | None = None) -> str:
    """
    Generates a concise, safe background memory snippet for initial prompt injection.
    Filters out noisy task/project histories to avoid context bloating, presenting only
    core important facts and user preferences.
    """
    if memory is None:
        memory = load_memory()
    if not memory:
        return ""

    lines = []
    
    facts = memory.get("important_fact", {})
    facts.update(memory.get("identity", {}))
    facts.update(memory.get("relationships", {}))
    if facts:
        for k, entry in list(facts.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"{k.replace('_', ' ').title()}: {val}")

    prefs = memory.get("user_preference", {})
    prefs.update(memory.get("preferences", {}))
    prefs.update(memory.get("patterns", {}))
    if prefs:
        lines.append("\nKey Preferences:")
        for k, entry in list(prefs.items())[:8]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {k.replace('_', ' ').title()}: {val}")

    projects = memory.get("project_context", {})
    projects.update(memory.get("projects", {}))
    if projects:
        lines.append("\nActive Projects (Summary):")
        for k, entry in list(projects.items())[:4]:
            val = entry.get("value") if isinstance(entry, dict) else entry
            if val:
                lines.append(f"  - {k.replace('_', ' ').title()}: {val}")

    if not lines:
        return ""

    header = "[WHAT YOU KNOW ABOUT THIS PERSON — use naturally, never recite like a list]\n"
    result = header + "\n".join(lines)
    if len(result) > 1500:
        result = result[:1497] + "..."
    return result + "\n"

def remember(key: str, value: str, category: str = "task_context") -> str:
    if contains_sensitive_data(value):
        print(f"[Memory Security] Blocked remember attempt for sensitive key: '{key}'")
        return f"Denied: Cannot store sensitive information under {category}/{key}."
    norm_cat = normalize_category(category)
    update_memory({norm_cat: {key: {"value": value}}})
    return f"Remembered: {norm_cat}/{key} = {value}"

def forget(key: str, category: str = None) -> str:
    with _lock:
        conn = _get_db_connection()
        if not conn:
            mem = load_memory()
            found = False
            for cat in (mem.keys() if not category else [normalize_category(category)]):
                if cat in mem and key in mem[cat]:
                    del mem[cat][key]
                    found = True
            save_memory(mem)
            return f"Forgotten: {key}" if found else f"Not found: {key}"

        try:
            with conn:
                cursor = conn.cursor()
                if category:
                    norm_cat = normalize_category(category)
                    cursor.execute("DELETE FROM memories WHERE category = ? AND key = ?", (norm_cat, key))
                else:
                    cursor.execute("DELETE FROM memories WHERE key = ?", (key,))
                if cursor.rowcount > 0:
                    print(f"[Memory] [DEL] Forgot key: {key}")
                    return f"Forgotten: {key}"
                else:
                    return f"Not found in memory: {key}"
        except Exception as e:
            print(f"[Memory] [WARN] forget error: {e}")
            return f"Error forgetting {key}: {e}"
        finally:
            conn.close()

forget_memory = forget

def should_extract_memory_local(user_text: str) -> bool:
    if len(user_text.strip()) < 8 or contains_sensitive_data(user_text):
        return False
    name_patterns = [r'\bmy name is\b', r'\bi am called\b', r'\bcall me\b', r'\bmera naam\b', r'\bmujhe .+ bulao\b']
    pref_patterns = [r'\bi (always )?(like|love|prefer|enjoy|hate|dislike)\b', r'\bmy favorite\b', r'\bmujhe .+ pasand\b', r'\bmera favorite\b']
    info_patterns = [r'\bi (work (at|for|as)|live (in|at)|study (at|in))\b', r'\bmy (job|city|age|birthday)\b', r'\bi\'m from\b', r'\bmain .+ hun\b']
    text_lower = user_text.lower()
    all_patterns = name_patterns + pref_patterns + info_patterns
    return any(re.search(p, text_lower) for p in all_patterns)

def should_extract_memory(user_text: str, jarvis_text: str, api_key: str) -> bool:
    return should_extract_memory_local(user_text)

def extract_memory(user_text: str, jarvis_text: str, api_key: str) -> dict:
    if contains_sensitive_data(user_text):
        print("[Memory Security] Skipped extraction due to presence of sensitive data.")
        return {}
    try:
        client = get_gemini_client()
        combined = f"User: {user_text[:500]}\nJarvis: {jarvis_text[:300]}"
        response = None
        for model_name in ["models/gemini-2.5-flash", "gemini-2.0-flash"]:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=(
                        f"Extract ONLY important enduring personal facts or preferences from this conversation.\n"
                        f"Return ONLY valid JSON. Use {{}} if nothing is enduringly worth saving.\n"
                        f"Do NOT record credit cards, passwords, API keys, PINs, IDs, or transient tasks.\n\n"
                        f"Categories:\n"
                        f"  important_fact  → identity, name, age, city, job, school, relationship details\n"
                        f"  user_preference → favorite things, likes, dislikes, communication style, routines\n"
                        f"  project_context → long-term active coding or work projects, technology goals\n"
                        f"  task_context    → ongoing multi-day instructions or recurring operational rules\n\n"
                        f"Format:\n"
                        f'{{"important_fact":{{"name":{{"value":"Sahil"}}}},\n'
                        f' "user_preference":{{"favorite_editor":{{"value":"VS Code"}}}},\n'
                        f' "project_context":{{"jarvis_mcp":{{"value":"AI Assistant using MCP with SQLite and Playwright"}}}}}}\n\n'
                        f"{combined}"
                    )
                )
                if response and response.text:
                    break
            except Exception:
                response = None

        if not response or not response.text:
            return {}
        raw = response.text.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        if not raw or raw == "{}":
            return {}
        data = json.loads(raw)
        clean_data = {}
        for cat, items in data.items():
            if not isinstance(items, dict): continue
            norm_cat = normalize_category(cat)
            clean_data[norm_cat] = {}
            for k, val_obj in items.items():
                val_str = str(val_obj.get("value") if isinstance(val_obj, dict) and "value" in val_obj else val_obj)
                if not contains_sensitive_data(val_str):
                    clean_data[norm_cat][k] = {"value": val_str}
            if not clean_data[norm_cat]:
                del clean_data[norm_cat]
        return clean_data
    except Exception as e:
        if "429" not in str(e):
            print(f"[Memory] [WARN] Extract failed: {e}")
        return {}

def _get_sorted_items(memory_dict: dict, limit: int) -> list:
    items = list(memory_dict.items())
    def get_date(item):
        val = item[1]
        if isinstance(val, dict) and "updated" in val:
            return val["updated"]
        return "1970-01-01"
    items.sort(key=get_date, reverse=True)
    return items[:limit]
