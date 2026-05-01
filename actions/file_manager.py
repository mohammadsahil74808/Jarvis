# actions/file_manager.py
import shutil
import send2trash
import os
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
import PyPDF2
from docx import Document

from core.config import BASE_DIR, get_desktop_path, get_downloads_path, get_documents_path

def _get_desktop() -> Path:
    return get_desktop_path()

def _get_downloads() -> Path:
    return get_downloads_path()

def _get_documents() -> Path:
    return get_documents_path()

def _resolve_path(raw: str) -> Path:
    """
    Resolves a path from user input.
    Supports shortcuts: 'desktop', 'downloads', 'documents', 'home'
    """
    if not raw or not str(raw).strip():
        raise ValueError("File path cannot be empty. Please specify a valid path.")
    raw = raw.strip().strip("'\"")
    shortcuts = {
        "desktop":   _get_desktop(),
        "downloads": _get_downloads(),
        "documents": Path.home() / "Documents",
        "pictures":  Path.home() / "Pictures",
        "music":     Path.home() / "Music",
        "videos":    Path.home() / "Videos",
        "home":      Path.home(),
    }
    lower = raw.strip().lower()
    if lower in shortcuts:
        return shortcuts[lower]
    return Path(raw).expanduser()

def _format_size(bytes_size: int) -> str:
    """Converts bytes to human readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"

def list_files(path: str = "desktop", show_hidden: bool = False) -> str:
    """Lists files and folders in a directory."""
    try:
        target = _resolve_path(path)
        if not target.exists():
            return f"Path not found: {target}"
        if not target.is_dir():
            return f"Not a directory: {target}"

        items = []
        for item in sorted(target.iterdir()):
            if not show_hidden and item.name.startswith("."):
                continue
            if item.is_dir():
                items.append(f"[DIR] {item.name}/")
            else:
                size = _format_size(item.stat().st_size)
                items.append(f"[FILE] {item.name} ({size})")

        if not items:
            return f"Directory is empty: {target}"

        return f"Contents of {target.name}/ ({len(items)} items):\n" + "\n".join(items)

    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Error listing files: {e}"

def create_file(path: str, content: str = "") -> str:
    """Creates a new file with optional content."""
    try:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"File created: {target.name}"
    except Exception as e:
        return f"Could not create file: {e}"

def create_folder(path: str) -> str:
    """Creates a new folder (and parent folders if needed)."""
    try:
        target = Path(path).expanduser()
        target.mkdir(parents=True, exist_ok=True)
        return f"Folder created: {target}"
    except Exception as e:
        return f"Could not create folder: {e}"

def delete_file(path: str, confirm: bool = False) -> str:
    """
    Deletes a file or folder.
    Moves to Recycle Bin on Windows if possible, otherwise permanent delete.
    REQUIREMENT: confirm must be True.
    """
    if not confirm:
        return "Deletion blocked. Please confirm by setting 'confirm': True in your parameters."
    try:
        target = Path(path).expanduser()
        if not target.exists():
            return f"Not found: {path}"

        try:

            send2trash.send2trash(str(target))
            return f"Moved to Recycle Bin: {target.name}"
        except ImportError:
            pass

        # Fallback: permanent delete
        if target.is_dir():
            shutil.rmtree(target)
            return f"Folder deleted permanently from: {target.absolute()}"
        else:
            target.unlink()
            return f"File deleted permanently from: {target.absolute()}"

    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Could not delete: {e}"

def move_file(source: str, destination: str) -> str:
    """Moves a file or folder to a new location."""
    try:
        src  = Path(source).expanduser()
        dst  = _resolve_path(destination)

        if not src.exists():
            return f"Source not found: {source}"

        if dst.is_dir():
            dst = dst / src.name

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"Moved: {src.name} → {dst.parent.name}/"

    except Exception as e:
        return f"Could not move: {e}"

def copy_file(source: str, destination: str) -> str:
    """Copies a file or folder."""
    try:
        src = Path(source).expanduser()
        dst = _resolve_path(destination)

        if not src.exists():
            return f"Source not found: {source}"

        if dst.is_dir():
            dst = dst / src.name

        dst.parent.mkdir(parents=True, exist_ok=True)

        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))

        return f"Copied: {src.name} → {dst.parent.name}/"

    except Exception as e:
        return f"Could not copy: {e}"

def rename_file(path: str, new_name: str) -> str:
    """Renames a file or folder."""
    try:
        target   = Path(path).expanduser()
        new_path = target.parent / new_name

        if not target.exists():
            return f"Not found: {path}"
        if new_path.exists():
            return f"A file named '{new_name}' already exists."

        target.rename(new_path)
        return f"Renamed: {target.name} → {new_name}"

    except Exception as e:
        return f"Could not rename: {e}"

def write_file(path: str, content: str, append: bool = False) -> str:
    """Writes or appends content to a file."""
    try:
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)
        action = "Appended to" if append else "Written to"
        return f"{action} successfully at: {target.absolute()}"
    except Exception as e:
        return f"Could not write file: {e}"

def find_files(name: str = "", extension: str = "", path: str = "home",
               max_results: int = 20) -> str:
    """
    Searches for files or folders. If no extension is provided, performs a smart folder search.
    """
    try:
        # 1. Real Folder Search Logic (Requested for accuracy)
        if not extension and name:
            name_lower = name.lower().strip()
            # Check common directories
            roots = [get_desktop_path(), get_documents_path(), get_downloads_path(), Path.home()]
            
            # Phase A: Quick check (Immediate children)
            for root in roots:
                if not root.exists(): continue
                try:
                    for item in root.iterdir():
                        if item.is_dir() and item.name.lower() == name_lower:
                            return str(item)
                except Exception: continue

            # Phase B: os.walk search (Limited depth for speed)
            for root in roots:
                if not root.exists(): continue
                root_str = str(root)
                for dirpath, dirnames, filenames in os.walk(root_str):
                    # Limit depth to 2 levels
                    rel = os.path.relpath(dirpath, root_str)
                    depth = 0 if rel == "." else len(Path(rel).parts)
                    if depth >= 2:
                        dirnames[:] = []
                        continue
                    
                    for d in dirnames:
                        if d.lower() == name_lower:
                            return os.path.join(dirpath, d)

            # If it's likely a folder request (no extension), return "not found" instead of defaulting to desktop files
            if path == "desktop" or path == "home":
                return "Folder not found on system"

        # 2. Standard File Search Logic
        search_path = _resolve_path(path)
        if not search_path.exists():
            return f"Search path not found: {path}"

        results = []
        pattern = f"*{extension}" if extension else "*"

        for item in search_path.rglob(pattern):
            if item.is_file():
                if name and name.lower() not in item.name.lower():
                    continue
                size = _format_size(item.stat().st_size)
                results.append(f"📄 {item.name} ({size}) — {item.parent}")
                if len(results) >= max_results:
                    break

        if not results:
            query = name or extension or "files"
            return f"No {query} found in {search_path.name}/"

        return f"Found {len(results)} file(s):\n" + "\n".join(results)

    except Exception as e:
        return f"Search error: {e}"

def get_largest_files(path: str = "home", count: int = 10) -> str:
    """Returns the largest files in a directory."""
    try:
        search_path = _resolve_path(path)
        if not search_path.exists():
            return f"Path not found: {path}"

        files = []
        for item in search_path.rglob("*"):
            if item.is_file():
                try:
                    files.append((item.stat().st_size, item))
                except Exception:
                    continue

        files.sort(reverse=True)
        top = files[:count]

        if not top:
            return "No files found."

        lines = [f"Top {len(top)} largest files in {search_path.name}/:\n"]
        for size, f in top:
            lines.append(f"  {_format_size(size):>10}  {f.name}  ({f.parent})")

        return "\n".join(lines)

    except Exception as e:
        return f"Error: {e}"

def get_disk_usage(path: str = "home") -> str:
    """Returns disk usage information."""
    try:
        target = _resolve_path(path)
        usage  = shutil.disk_usage(target)
        total  = _format_size(usage.total)
        used   = _format_size(usage.used)
        free   = _format_size(usage.free)
        pct    = usage.used / usage.total * 100

        return (
            f"Disk usage for {target}:\n"
            f"  Total : {total}\n"
            f"  Used  : {used} ({pct:.1f}%)\n"
            f"  Free  : {free}"
        )
    except Exception as e:
        return f"Could not get disk usage: {e}"

def organize_desktop() -> str:
    """
    Organizes the desktop by grouping files into folders by type.
    Creates folders: Images, Documents, Videos, Music, Archives, Others
    """
    try:
        desktop = _get_desktop()
        type_map = {
            "Images":    [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg", ".ico"],
            "Documents": [".pdf", ".doc", ".docx", ".txt", ".xls", ".xlsx", ".ppt", ".pptx", ".csv"],
            "Videos":    [".mp4", ".avi", ".mkv", ".mov", ".wmv", ".flv", ".webm"],
            "Music":     [".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma"],
            "Archives":  [".zip", ".rar", ".7z", ".tar", ".gz"],
            "Code":      [".py", ".js", ".html", ".css", ".json", ".xml", ".ts", ".cpp", ".java"],
        }

        moved    = []
        skipped  = []

        for item in desktop.iterdir():

            if item.is_dir() or item.name.startswith("."):
                continue

            ext        = item.suffix.lower()
            target_dir = None

            for folder, extensions in type_map.items():
                if ext in extensions:
                    target_dir = desktop / folder
                    break

            if target_dir is None:
                target_dir = desktop / "Others"

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
            result += f"\n{len(skipped)} files skipped (already exist)."

        return result

    except Exception as e:
        return f"Could not organize desktop: {e}"

def get_file_info(path: str) -> str:
    """Returns detailed information about a file."""
    try:
        target = Path(path).expanduser()
        if not target.exists():
            return f"Not found: {path}"

        stat = target.stat()
        info = {
            "Name":     target.name,
            "Type":     "Folder" if target.is_dir() else "File",
            "Size":     _format_size(stat.st_size),
            "Location": str(target.parent),
            "Created":  datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M"),
            "Modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
            "Extension": target.suffix or "None",
        }

        return "\n".join(f"  {k}: {v}" for k, v in info.items())

    except Exception as e:
        return f"Could not get file info: {e}"

def read_document(path: str) -> str:
    """Reads text from .txt, .pdf, or .docx files."""
    p = Path(path).expanduser()
    if not p.exists():
        return f"Error: File {path} not found."
    
    ext = p.suffix.lower()
    try:
        if ext == ".txt":
            return p.read_text(encoding="utf-8", errors="ignore")[:5000]
        
        elif ext == ".pdf":
            text = []
            with open(p, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages[:10]: # Limit to first 10 pages
                    text.append(page.extract_text())
            return "\n".join(text)[:5000]
        
        elif ext == ".docx":
            doc = Document(p)
            text = [para.text for para in doc.paragraphs]
            return "\n".join(text)[:5000]
        
        else:
            return f"Unsupported file type: {ext}. JARVIS can only read .txt, .pdf, and .docx directly."
    except Exception as e:
        return f"Error reading {ext} file: {str(e)}"

def find_duplicates(directory: str) -> str:
    """Finds duplicate files based on MD5 content hash."""
    target = Path(directory).expanduser()
    if not target.is_dir():
        return f"Error: {directory} is not a directory."
    
    hashes = {} # hash -> list of paths
    duplicates = []
    
    for item in target.rglob("*"):
        if item.is_file():
            try:
                file_hash = hashlib.md5(item.read_bytes()).hexdigest()
                if file_hash in hashes:
                    hashes[file_hash].append(str(item))
                    duplicates.append(str(item))
                else:
                    hashes[file_hash] = [str(item)]
            except Exception:
                continue
    
    if not duplicates:
        return f"No duplicate files found in {target.name}."
    
    res = ["Duplicate files found:"]
    for h, paths in hashes.items():
        if len(paths) > 1:
            res.append(f"\nHash {h}:")
            for p in paths:
                res.append(f"  - {p}")
    return "\n".join(res)

def clean_downloads(days=30) -> str:
    """Moves files older than X days to a Cleanup folder."""
    downloads = _get_downloads()
    cleanup_dir = downloads / "JARVIS_Cleanup"
    cleanup_dir.mkdir(exist_ok=True)
    
    threshold = datetime.now() - timedelta(days=days)
    moved = []
    
    for item in downloads.iterdir():
        if item.is_file() and not item.name.startswith("."):
            mtime = datetime.fromtimestamp(item.stat().st_mtime)
            if mtime < threshold:
                try:
                    shutil.move(str(item), str(cleanup_dir / item.name))
                    moved.append(item.name)
                except Exception:
                    continue
    
    if not moved:
        return f"Downloads folder is already clean (no files older than {days} days)."
    return f"Moved {len(moved)} old files to {cleanup_dir.name}/ folder."

def deep_search(query: str, start_path: Path = None) -> str:
    """Searches extensively for a file starting from a path (default: Home)."""
    if start_path is None:
        start_path = Path.home()
        
    print(f"[FileBrain] 🔍 Deep search for '{query}' in {start_path}...")
    results = []
    
    # Simple rglob search first (fast but might hit permission errors)
    try:
        # We search inside major subdirs first to avoid scanning everything at once
        major_dirs = [start_path / "Desktop", start_path / "Downloads", start_path / "Documents", start_path / "Videos", start_path / "Pictures"]
        
        # Add the ones that exist
        targets = [d for d in major_dirs if d.exists()]
        if not targets: targets = [start_path] # Fallback
        
        for target in targets:
            try:
                found = list(target.rglob(f"*{query}*"))
                for item in found:
                    if item.is_file():
                        results.append(str(item))
                    if len(results) >= 20: break
            except PermissionError:
                continue
            if len(results) >= 20: break
            
    except Exception as e:
        return f"Deep Search Error: {str(e)}"
                
    if not results:
        # Last resort: direct glob in home (non-recursive) just in case
        results = [str(p) for p in start_path.glob(f"*{query}*") if p.is_file()]
        if not results:
            return f"No files matching '{query}' found even after deep search in {start_path}."
        
    return f"Found {len(results)} matches:\n" + "\n".join(results[:15])

def get_recent_files(directory: str, count=5) -> str:
    """Returns the most recently modified files."""
    target = Path(directory).expanduser()
    if not target.is_dir():
        return f"Error: {directory} is not a directory."
    
    files = []
    for item in target.rglob("*"):
        if item.is_file():
            try:
                files.append((item.stat().st_mtime, item))
            except Exception:
                continue
    
    files.sort(key=lambda x: x[0], reverse=True)
    recent = files[:count]
    
    if not recent:
        return "No recent files found."
    
    res = [f"Recent files in {target.name}:"]
    for mtime, p in recent:
        dt = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        res.append(f"  [{dt}] {p.name}")
    return "\n".join(res)

def file_manager(parameters: dict, response=None, player=None, session_memory=None) -> str:
    action  = (parameters or {}).get("action", "info").lower().strip()
    path    = (parameters or {}).get("path", "desktop")
    name    = (parameters or {}).get("name", "")
    content = (parameters or {}).get("content", "")
    confirm = (parameters or {}).get("confirm", False)

    def _full_path(p: str, n: str) -> str:
        base = _resolve_path(p)
        if n: return str(base / n)
        return str(base)

    result = "Unknown action."
    try:
        if action == "list": result = list_files(path)
        elif action == "create_file": result = create_file(_full_path(path, name), content=content)
        elif action == "create_folder": result = create_folder(_full_path(path, name))
        elif action == "delete": result = delete_file(_full_path(path, name), confirm=confirm)
        elif action == "move": result = move_file(_full_path(path, name), parameters.get("destination", ""))
        elif action == "copy": result = copy_file(_full_path(path, name), parameters.get("destination", ""))
        elif action == "rename": result = rename_file(_full_path(path, name), parameters.get("new_name", ""))
        elif action == "read": result = read_document(_full_path(path, name))
        elif action == "write": result = write_file(_full_path(path, name), content=content, append=parameters.get("append", False))
        elif action in ["find", "search"]: result = find_files(name=name or parameters.get("query", ""), extension=parameters.get("extension", ""), path=path, max_results=parameters.get("max_results", 20))
        elif action == "largest": result = get_largest_files(path=path, count=parameters.get("count", 10))
        elif action == "disk_usage": result = get_disk_usage(path)
        elif action == "organize_desktop": result = organize_desktop()
        elif action == "info": result = get_file_info(_full_path(path, name))
        elif action == "find_duplicates": result = find_duplicates(_full_path(path, name))
        elif action == "clean_downloads": result = clean_downloads(parameters.get("days", 30))
        elif action == "recent": result = get_recent_files(_full_path(path, name), count=parameters.get("count", 5))
        elif action == "deep_search": result = deep_search(parameters.get("query", ""), start_path=Path(path).expanduser())
        elif action == "open":
            target = Path(_full_path(path, name)).expanduser()
            os.startfile(str(target))
            result = f"Opening {target.name}..."
        else: result = f"Unknown action: '{action}'"
    except Exception as e:
        result = f"File manager error: {e}"

    if player: player.write_log(f"[file] {result[:60]}")
    return result
