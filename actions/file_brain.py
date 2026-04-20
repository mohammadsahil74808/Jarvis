import hashlib
import shutil
import send2trash
from pathlib import Path
from datetime import datetime, timedelta

import PyPDF2
from docx import Document

def _get_desktop() -> Path:
    # Check OneDrive first
    one_drive_desktop = Path.home() / "OneDrive" / "Desktop"
    if one_drive_desktop.exists():
        return one_drive_desktop
    return Path.home() / "Desktop"

def _get_downloads() -> Path:
    one_drive_downloads = Path.home() / "OneDrive" / "Downloads"
    if one_drive_downloads.exists():
        return one_drive_downloads
    return Path.home() / "Downloads"

def _format_size(bytes_size: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} GB"

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

def file_brain(parameters: dict, **kwargs) -> str:
    """
    Intelligent File Manager for JARVIS.
    Actions: read, find_duplicates, clean_downloads, recent, search
    """
    action = parameters.get("action", "recent").lower()
    path = parameters.get("path", "desktop")
    
    if path.lower() == "desktop": path = str(_get_desktop())
    if path.lower() == "downloads": path = str(_get_downloads())
    
    try:
        if action == "read":
            return read_document(path)
        
        elif action == "find_duplicates":
            return find_duplicates(path)
        
        elif action == "clean_downloads":
            days = parameters.get("days", 30)
            return clean_downloads(days=days)
        
        elif action == "recent":
            count = parameters.get("count", 5)
            return get_recent_files(path, count=count)
        
        elif action == "search" or action == "deep_search":
            query = parameters.get("query", "")
            if action == "deep_search" or path.lower() in ["home", "user", "system"]:
                return deep_search(query, start_path=Path.home())
            
            # Normal search logic
            results = list(Path(path).expanduser().rglob(f"*{query}*"))
            if not results: return f"No files matching '{query}' found in {path}."
            return "Found files:\n" + "\n".join([str(r) for r in results[:10]])

        elif action == "copy":
            source = Path(path).expanduser()
            dest = Path(parameters.get("destination", "")).expanduser()
            if source.is_dir():
                shutil.copytree(source, dest / source.name)
            else:
                shutil.copy2(source, dest)
            return f"Copied {source.name} to {dest.name}"

        elif action == "move":
            source = Path(path).expanduser()
            dest = Path(parameters.get("destination", "")).expanduser()
            shutil.move(str(source), str(dest))
            return f"Moved {source.name} to {dest.name}"

        elif action == "delete":
            target = Path(path).expanduser()
            send2trash.send2trash(str(target))
            return f"Moved {target.name} to Recycle Bin."

        elif action == "rename":
            target = Path(path).expanduser()
            new_name = parameters.get("new_name", "")
            new_path = target.parent / new_name
            target.rename(new_path)
            return f"Renamed {target.name} to {new_name}"

        elif action == "open":
            import os
            target = Path(path).expanduser()
            os.startfile(str(target))
            return f"Opening {target.name}..."

        return f"Action '{action}' not recognized by File Brain."

    except Exception as e:
        return f"File Brain Error: {str(e)}"
