
import os
import shutil
import hashlib
import subprocess
import string
from collections import deque
from pathlib import Path
from datetime import datetime, timedelta

import send2trash
import PyPDF2
from docx import Document

from core.config import (
    BASE_DIR, get_desktop_path, get_downloads_path,
    get_documents_path, get_gemini_client
)

# ── Path helpers ───────────────────────────────────────────────────

def _get_desktop()   -> Path: return get_desktop_path()
def _get_downloads() -> Path: return get_downloads_path()
def _get_documents() -> Path: return get_documents_path()

_SHORTCUTS = {
    "desktop":   _get_desktop,
    "downloads": _get_downloads,
    "documents": _get_documents,
    "pictures":  lambda: Path.home() / "Pictures",
    "music":     lambda: Path.home() / "Music",
    "videos":    lambda: Path.home() / "Videos",
    "home":      Path.home,
}

def _resolve_path(raw: str) -> Path:
    if not raw or not str(raw).strip():
        raise ValueError("File path cannot be empty.")
    raw = raw.strip().strip("'\"")
    lower = raw.strip().lower()
    if lower in _SHORTCUTS:
        fn = _SHORTCUTS[lower]
        return fn() if callable(fn) else fn
    return Path(raw).expanduser()

def _format_size(b: int) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if b < 1024:
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"

# ── BUG 3 FIX: Active drive detection ─────────────────────────────

def _get_active_drives() -> list[Path]:
    """
    Windows pe saari accessible drives return karta hai (C: D: E: etc).
    IRIS jaisa — sirf home nahi, sab drives scan karta hai.
    """
    drives = []
    if os.name == "nt":
        for letter in string.ascii_uppercase:
            drive = Path(f"{letter}:\\")
            try:
                drive.stat()
                drives.append(drive)
            except (OSError, PermissionError):
                continue
    if not drives:
        drives = [Path.home()]
    return drives

# ── BUG 1+2 FIX: Smart keyword extraction + unlimited BFS search ──

# Folders to always skip (speed + safety)
_SKIP_DIRS = {
    "windows", "system32", "syswow64", "program files",
    "program files (x86)", "programdata", "appdata",
    "node_modules", "$recycle.bin", "system volume information",
    ".git", "dist", "build", "__pycache__", "venv", ".venv",
    "site-packages", "winsxs", "servicing", "assembly",
}

def _extract_keywords_gemini(query: str) -> tuple[list[str], str]:
    """
    BUG 2 FIX: Gemini se smart keywords nikalo.
    Returns: (keywords_list, root_hint)
    
    Example:
      "mera resume dhundho desktop pe" 
      → (["resume"], "desktop")
      
      "project wali python file" 
      → (["project", ".py"], "")
    """
    try:
        client = get_gemini_client()
        prompt = f"""Extract search keywords from this file search query: "{query}"

Rules:
1. Extract actual file/folder name keywords only
2. Remove words like: "dhundho", "find", "search", "mera", "meri", "file", "folder", "document", "wala", "wali"
3. Fix spelling mistakes (e.g. "resme" → "resume")  
4. If user mentions a location (desktop, downloads, documents, D drive, etc), put it in root_hint
5. If user mentions file type (.py, .pdf, .docx, .mp4 etc), include the extension keyword
6. Return ONLY this JSON, nothing else:
{{"keywords": ["word1", "word2"], "root_hint": "desktop"}}

Examples:
"mera resume dhundho" → {{"keywords": ["resume"], "root_hint": ""}}
"desktop pe project folder" → {{"keywords": ["project"], "root_hint": "desktop"}}
"D drive mein python files" → {{"keywords": [".py"], "root_hint": "D"}}
"jarvis ka main.py dhundho" → {{"keywords": ["main.py"], "root_hint": ""}}"""

        import json
        resp = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        text = resp.text.strip()
        # Strip markdown fences if present
        text = text.replace("```json", "").replace("```", "").strip()
        data = json.loads(text)
        keywords = [str(k).lower().strip() for k in data.get("keywords", []) if k]
        root_hint = str(data.get("root_hint", "")).strip().lower()
        if keywords:
            return keywords, root_hint
    except Exception as e:
        print(f"[FileManager] Keyword extraction failed: {e}")

    # Fallback: use original query words
    stop_words = {
        "dhundho", "find", "search", "mera", "meri", "mere", "mujhe",
        "file", "folder", "document", "wala", "wali", "pe", "mein",
        "ka", "ki", "ke", "karo", "please", "the", "a", "an", "my",
        "for", "on", "in", "at", "is", "are", "do"
    }
    words = [w.lower().strip(".,?!") for w in query.split()]
    keywords = [w for w in words if w and w not in stop_words and len(w) > 1]
    return keywords or [query.lower().strip()], ""


def _bfs_search(roots: list[Path], keywords: list[str],
                max_results: int = 20) -> list[Path]:
    """
    BUG 1 FIX: BFS with NO depth limit. 
    Visited set prevents infinite loops.
    Finds files where ALL keywords match the path (IRIS jaisi logic).
    """
    found   = []
    visited = set()
    queue   = deque(roots)

    while queue and len(found) < max_results:
        current = queue.popleft()

        try:
            current_real = current.resolve()
        except Exception:
            continue

        if current_real in visited:
            continue
        visited.add(current_real)

        try:
            entries = list(current.iterdir())
        except (PermissionError, OSError):
            continue

        for entry in entries:
            if len(found) >= max_results:
                break

            try:
                name_lower = entry.name.lower()
                path_lower = str(entry).lower()

                # Skip system/junk folders
                if entry.is_dir():
                    if (name_lower.startswith((".", "$")) or
                            name_lower in _SKIP_DIRS):
                        continue
                    queue.append(entry)
                elif entry.is_file():
                    # ALL keywords must match the path
                    if all(kw in path_lower for kw in keywords):
                        found.append(entry)
            except (PermissionError, OSError):
                continue

    return found


def smart_search(query: str, max_results: int = 20) -> str:
    """
    UPGRADED search — combines BUG 1 + 2 + 3 fixes:
    1. Gemini extracts real keywords
    2. BFS with no depth limit
    3. All drives scanned
    """
    print(f"[FileManager] Smart search: '{query}'")

    # Step 1: Extract keywords via Gemini
    keywords, root_hint = _extract_keywords_gemini(query)
    print(f"[FileManager] Keywords: {keywords} | Root hint: '{root_hint}'")

    if not keywords:
        return f"Could not extract search keywords from: '{query}'"

    # Step 2: Determine search roots
    roots = []

    if root_hint:
        hint_lower = root_hint.lower()
        # Single drive letter e.g. "d" or "d drive"
        if len(hint_lower) == 1 and hint_lower.isalpha():
            drive = Path(f"{hint_lower.upper()}:\\")
            if drive.exists():
                roots = [drive]
        # Known shortcuts
        elif hint_lower in _SHORTCUTS:
            fn = _SHORTCUTS[hint_lower]
            p  = fn() if callable(fn) else fn
            if p.exists():
                roots = [p]

    # If no specific root found, search everywhere
    if not roots:
        # Priority: common personal dirs first (fast), then full drives
        personal = [
            _get_desktop(), _get_downloads(), _get_documents(),
            Path.home() / "Pictures", Path.home() / "Music",
            Path.home() / "Videos", Path.home() / "OneDrive",
        ]
        roots = [p for p in personal if p.exists()]
        # Add non-C drives for broader search
        for drive in _get_active_drives():
            if not str(drive).startswith("C") and drive not in roots:
                roots.append(drive)
        # Finally add C:\Users\<name> if not already covered
        if Path.home() not in roots:
            roots.append(Path.home())

    print(f"[FileManager] Searching in {len(roots)} root(s)...")

    # Step 3: BFS search
    results = _bfs_search(roots, keywords, max_results)

    if not results:
        return (f"No files found matching '{query}'.\n"
                f"Keywords used: {keywords}\n"
                f"Searched in: {', '.join(str(r) for r in roots[:3])}"
                + (" + more drives" if len(roots) > 3 else ""))

    lines = [f"Found {len(results)} file(s) for '{query}':"]
    for p in results:
        try:
            size = _format_size(p.stat().st_size)
            lines.append(f"  📄 {p.name} ({size})\n     📁 {p.parent}")
        except Exception:
            lines.append(f"  📄 {p}")

    return "\n".join(lines)


# ── BUG 4 FIX: Safe open with full error handling ─────────────────

def open_file(path: str, reveal: bool = False) -> str:
    """
    BUG 4 FIX: Safe file open with:
    - Existence check before attempting
    - Full try/except
    - 'reveal' mode to open containing folder
    - Clear error messages
    """
    try:
        target = Path(path).expanduser().resolve()

        if not target.exists():
            # Try to find it via smart_search as fallback
            return (f"File not found: {target.name}\n"
                    f"Full path checked: {target}\n"
                    f"Tip: Try 'find {target.name}' to locate it.")

        if reveal:
            # Open folder with file highlighted (Windows Explorer)
            if os.name == "nt":
                subprocess.Popen(
                    ["explorer", "/select,", str(target)],
                    shell=False
                )
                return f"Revealed in Explorer: {target.name}"
            else:
                subprocess.Popen(["xdg-open", str(target.parent)])
                return f"Opened folder: {target.parent.name}"

        # Normal open
        if os.name == "nt":
            os.startfile(str(target))
        else:
            subprocess.Popen(["xdg-open", str(target)])

        return f"Opening: {target.name}"

    except FileNotFoundError:
        return f"Cannot open — file not found: {path}"
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Could not open '{path}': {e}"


# ── All existing functions (unchanged but cleaned up) ──────────────

def list_files(path: str = "desktop", show_hidden: bool = False) -> str:
    try:
        target = _resolve_path(path)
        if not target.exists():  return f"Path not found: {target}"
        if not target.is_dir():  return f"Not a directory: {target}"
        items = []
        for item in sorted(target.iterdir()):
            if not show_hidden and item.name.startswith("."): continue
            if item.is_dir():
                items.append(f"[DIR] {item.name}/")
            else:
                items.append(f"[FILE] {item.name} ({_format_size(item.stat().st_size)})")
        if not items: return f"Empty directory: {target}"
        return f"Contents of {target.name}/ ({len(items)} items):\n" + "\n".join(items)
    except PermissionError: return f"Permission denied: {path}"
    except Exception as e:  return f"Error listing: {e}"


def create_file(path: str, content: str = "") -> str:
    try:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"File created: {target.name}"
    except Exception as e: return f"Could not create file: {e}"


def create_folder(path: str) -> str:
    try:
        target = Path(path).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        return f"Folder created: {target}"
    except Exception as e: return f"Could not create folder: {e}"


def delete_file(path: str, confirm: bool = False) -> str:
    if not confirm:
        return "Deletion blocked — confirm=True required. Bolo: 'haan delete karo'."
    try:
        target = Path(path).expanduser()
        if not target.exists(): return f"Not found: {path}"
        try:
            send2trash.send2trash(str(target))
            return f"Moved to Recycle Bin: {target.name}"
        except Exception:
            pass
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return f"Permanently deleted: {target.name}"
    except PermissionError: return f"Permission denied: {path}"
    except Exception as e:  return f"Could not delete: {e}"


def move_file(source: str, destination: str) -> str:
    try:
        src = Path(source).expanduser()
        dst = _resolve_path(destination)
        if not src.exists(): return f"Source not found: {source}"
        if dst.is_dir():     dst = dst / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Moved: {src.name} → {dst.parent.name}/"
    except Exception as e: return f"Could not move: {e}"


def copy_file(source: str, destination: str) -> str:
    try:
        src = Path(source).expanduser()
        dst = _resolve_path(destination)
        if not src.exists(): return f"Source not found: {source}"
        if dst.is_dir():     dst = dst / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(str(src), str(dst)) if src.is_dir() else shutil.copy2(str(src), str(dst))
        return f"Copied: {src.name} → {dst.parent.name}/"
    except Exception as e: return f"Could not copy: {e}"


def rename_file(path: str, new_name: str) -> str:
    try:
        target   = Path(path).expanduser()
        new_path = target.parent / new_name
        if not target.exists():  return f"Not found: {path}"
        if new_path.exists():    return f"'{new_name}' already exists."
        target.rename(new_path)
        return f"Renamed: {target.name} → {new_name}"
    except Exception as e: return f"Could not rename: {e}"


def write_file(path: str, content: str, append: bool = False) -> str:
    try:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "a" if append else "w", encoding="utf-8") as f:
            f.write(content)
        return f"{'Appended' if append else 'Written'} to: {target.name}"
    except Exception as e: return f"Could not write: {e}"


def find_files(name: str = "", extension: str = "",
               path: str = "home", max_results: int = 20) -> str:
    """
    Standard find — kept for backward compat.
    For smart search use smart_search() directly.
    """
    # If query looks conversational (Hindi/mixed), route to smart_search
    hindi_indicators = [
        "dhundho", "dhoondho", "mera", "meri", "mere",
        "wala", "wali", "chahiye", "karo"
    ]
    search_query = name or extension
    if any(w in search_query.lower() for w in hindi_indicators):
        return smart_search(search_query, max_results)

    try:
        search_path = _resolve_path(path)
        if not search_path.exists():
            return f"Search path not found: {path}"
        results = []
        pattern  = f"*{extension}" if extension else "*"
        for item in search_path.rglob(pattern):
            if item.is_file():
                if name and name.lower() not in item.name.lower(): continue
                results.append(
                    f"📄 {item.name} ({_format_size(item.stat().st_size)}) — {item.parent}")
                if len(results) >= max_results: break
        if not results:
            return f"No {name or extension or 'files'} found in {search_path.name}/"
        return f"Found {len(results)} file(s):\n" + "\n".join(results)
    except Exception as e:
        return f"Search error: {e}"


def deep_search(query: str, start_path: Path = None) -> str:
    """
    BUG 5 FIX: Routes to smart_search (non-blocking BFS).
    start_path kept for backward compatibility.
    """
    if start_path and start_path != Path.home():
        # User specified explicit start path — use BFS from there
        keywords, _ = _extract_keywords_gemini(query)
        if not keywords:
            keywords = [query.lower().strip()]
        results = _bfs_search([start_path], keywords, max_results=20)
        if not results:
            return f"No files matching '{query}' found in {start_path}."
        lines = [f"Found {len(results)} match(es):"]
        for p in results:
            lines.append(f"  📄 {p.name}\n     📁 {p.parent}")
        return "\n".join(lines)

    # Default: full smart search
    return smart_search(query, max_results=20)


def get_largest_files(path: str = "home", count: int = 10) -> str:
    try:
        search_path = _resolve_path(path)
        if not search_path.exists(): return f"Path not found: {path}"
        files = []
        for item in search_path.rglob("*"):
            if item.is_file():
                try: files.append((item.stat().st_size, item))
                except Exception: continue
        files.sort(reverse=True)
        top = files[:count]
        if not top: return "No files found."
        lines = [f"Top {len(top)} largest files in {search_path.name}/:"]
        for size, f in top:
            lines.append(f"  {_format_size(size):>10}  {f.name}  ({f.parent})")
        return "\n".join(lines)
    except Exception as e: return f"Error: {e}"


def get_disk_usage(path: str = "home") -> str:
    try:
        target = _resolve_path(path)
        usage  = shutil.disk_usage(target)
        pct    = usage.used / usage.total * 100
        return (f"Disk usage for {target}:\n"
                f"  Total : {_format_size(usage.total)}\n"
                f"  Used  : {_format_size(usage.used)} ({pct:.1f}%)\n"
                f"  Free  : {_format_size(usage.free)}")
    except Exception as e: return f"Could not get disk usage: {e}"


def organize_desktop() -> str:
    try:
        desktop  = _get_desktop()
        type_map = {
            "Images":    [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg"],
            "Documents": [".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt",
                          ".pptx", ".csv"],
            "Videos":    [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
            "Music":     [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"],
            "Archives":  [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Code":      [".py", ".js", ".html", ".css", ".json", ".ts", ".cpp", ".java"],
        }
        moved, skipped = [], []
        for item in desktop.iterdir():
            if item.is_dir() or item.name.startswith("."): continue
            ext        = item.suffix.lower()
            target_dir = next(
                (desktop / folder for folder, exts in type_map.items() if ext in exts),
                desktop / "Others"
            )
            target_dir.mkdir(exist_ok=True)
            new_path = target_dir / item.name
            if new_path.exists():
                skipped.append(item.name)
                continue
            shutil.move(str(item), str(new_path))
            moved.append(f"{item.name} → {target_dir.name}/")
        result = f"Desktop organized. {len(moved)} files moved."
        if moved:
            result += "\n" + "\n".join(moved[:10])
            if len(moved) > 10:
                result += f"\n... and {len(moved)-10} more."
        if skipped:
            result += f"\n{len(skipped)} files skipped."
        return result
    except Exception as e: return f"Could not organize desktop: {e}"


def get_file_info(path: str) -> str:
    try:
        target = Path(path).expanduser()
        if not target.exists(): return f"Not found: {path}"
        stat = target.stat()
        info = {
            "Name":      target.name,
            "Type":      "Folder" if target.is_dir() else "File",
            "Size":      _format_size(stat.st_size),
            "Location":  str(target.parent),
            "Created":   datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M"),
            "Modified":  datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "Extension": target.suffix or "None",
        }
        return "\n".join(f"  {k}: {v}" for k, v in info.items())
    except Exception as e: return f"Could not get file info: {e}"


def read_document(path: str) -> str:
    p = Path(path).expanduser()
    if not p.exists(): return f"File not found: {path}"
    ext = p.suffix.lower()
    try:
        if ext == ".txt":
            return p.read_text(encoding="utf-8", errors="ignore")[:5000]
        elif ext == ".pdf":
            text = []
            with open(p, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages[:10]:
                    text.append(page.extract_text() or "")
            return "\n".join(text)[:5000]
        elif ext == ".docx":
            doc = Document(p)
            return "\n".join(para.text for para in doc.paragraphs)[:5000]
        else:
            return f"Unsupported type: {ext}. Supported: .txt, .pdf, .docx"
    except Exception as e:
        return f"Error reading {ext}: {e}"


def find_duplicates(directory: str) -> str:
    target = Path(directory).expanduser()
    if not target.is_dir(): return f"Not a directory: {directory}"
    hashes = {}
    for item in target.rglob("*"):
        if item.is_file():
            try:
                h = hashlib.md5(item.read_bytes()).hexdigest()
                hashes.setdefault(h, []).append(str(item))
            except Exception: continue
    dupes = {h: ps for h, ps in hashes.items() if len(ps) > 1}
    if not dupes: return f"No duplicate files in {target.name}."
    res = ["Duplicate files found:"]
    for h, paths in dupes.items():
        res.append(f"\nHash {h[:8]}…:")
        for p in paths: res.append(f"  - {p}")
    return "\n".join(res)


def clean_downloads(days: int = 30) -> str:
    downloads    = _get_downloads()
    cleanup_dir  = downloads / "JARVIS_Cleanup"
    cleanup_dir.mkdir(exist_ok=True)
    threshold    = datetime.now() - timedelta(days=days)
    moved        = []
    for item in downloads.iterdir():
        if item.is_file() and not item.name.startswith("."):
            if datetime.fromtimestamp(item.stat().st_mtime) < threshold:
                try:
                    shutil.move(str(item), str(cleanup_dir / item.name))
                    moved.append(item.name)
                except Exception: continue
    if not moved:
        return f"Downloads already clean (no files older than {days} days)."
    return f"Moved {len(moved)} old files to JARVIS_Cleanup/."


def get_recent_files(directory: str, count: int = 5) -> str:
    target = Path(directory).expanduser()
    if not target.is_dir(): return f"Not a directory: {directory}"
    files = []
    for item in target.rglob("*"):
        if item.is_file():
            try: files.append((item.stat().st_mtime, item))
            except Exception: continue
    files.sort(key=lambda x: x[0], reverse=True)
    if not files[:count]: return "No recent files found."
    res = [f"Recent files in {target.name}:"]
    for mtime, p in files[:count]:
        dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        res.append(f"  [{dt}] {p.name}")
    return "\n".join(res)


# ══════════════════════════════════════════════════════════════════
# MAIN DISPATCHER
# ══════════════════════════════════════════════════════════════════

def file_manager(parameters: dict, response=None,
                 player=None, session_memory=None) -> str:

    params = parameters or {}
    action = params.get("action", "info").lower().strip()
    path   = params.get("path", "desktop")
    name   = params.get("name", "")
    content= params.get("content", "")
    confirm= params.get("confirm", False)
    query  = params.get("query", "") or name

    def _fp(p: str, n: str) -> str:
        base = _resolve_path(p)
        return str(base / n) if n else str(base)

    result = "Unknown action."
    try:
        if   action == "list":             result = list_files(path)
        elif action == "create_file":      result = create_file(_fp(path, name), content=content)
        elif action == "create_folder":    result = create_folder(_fp(path, name))
        elif action == "delete":           result = delete_file(_fp(path, name), confirm=confirm)
        elif action == "move":             result = move_file(_fp(path, name), params.get("destination",""))
        elif action == "copy":             result = copy_file(_fp(path, name), params.get("destination",""))
        elif action == "rename":           result = rename_file(_fp(path, name), params.get("new_name",""))
        elif action == "read":             result = read_document(_fp(path, name))
        elif action == "write":            result = write_file(_fp(path, name), content=content, append=params.get("append", False))
        elif action == "largest":          result = get_largest_files(path=path, count=params.get("count", 10))
        elif action == "disk_usage":       result = get_disk_usage(path)
        elif action == "organize_desktop": result = organize_desktop()
        elif action == "info":             result = get_file_info(_fp(path, name))
        elif action == "find_duplicates":  result = find_duplicates(_fp(path, name))
        elif action == "clean_downloads":  result = clean_downloads(params.get("days", 30))
        elif action == "recent":           result = get_recent_files(_fp(path, name), count=params.get("count", 5))

        # BUG 4 FIX: safe open with reveal support
        elif action == "open":
            result = open_file(_fp(path, name),
                               reveal=params.get("reveal", False))

        # BUG 1+2+3 FIX: smart search routes here
        elif action in ("find", "search"):
            result = smart_search(query or name, params.get("max_results", 20))

        # BUG 5 FIX: deep_search uses BFS now
        elif action == "deep_search":
            start = Path(path).expanduser() if path not in ("desktop", "home", "") else Path.home()
            result = deep_search(query, start_path=start)

        else:
            result = f"Unknown action: '{action}'"

    except Exception as e:
        result = f"File manager error ({action}): {e}"

    if player:
        player.write_log(f"[file] {result[:80]}")
    return result
