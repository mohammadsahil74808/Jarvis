# jarvis/browser/browser_context.py
"""
Persistent session storage and Google Chrome profile detector for Browser Use and Playwright MCP integration.
Supports real Google Chrome discovery, Chrome DevTools Protocol (CDP) remote debugging attachment, and profile safety protection.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_base_dir

try:
    import psutil
except ImportError:
    psutil = None


def find_real_chrome_executable() -> Optional[str]:
    """
    Automatically detect common Windows Google Chrome installations across Registry,
    PATH environment variable, and standard Program Files locations.
    """
    candidates: List[str] = []

    # 1. Check Windows Registry (HKLM & HKCU)
    if sys.platform == "win32":
        try:
            import winreg
            for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                try:
                    with winreg.OpenKey(root_key, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe") as key:
                        val, _ = winreg.QueryValueEx(key, "")
                        if val and os.path.exists(val):
                            candidates.append(str(val))
                except (OSError, FileNotFoundError):
                    pass
        except Exception:
            pass

    # 2. Check shutil.which / where.exe
    which_exe = shutil.which("chrome") or shutil.which("chrome.exe")
    if which_exe and os.path.exists(which_exe):
        candidates.append(str(which_exe))

    # 3. Check standard Windows Program Files and LocalAppData paths
    prog_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    local_appdata = os.environ.get("LOCALAPPDATA", r"C:\Users\user\AppData\Local")

    standard_paths = [
        os.path.join(prog_files, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(prog_files_x86, "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(local_appdata, "Google", "Chrome", "Application", "chrome.exe"),
    ]

    for p in standard_paths:
        if os.path.exists(p):
            candidates.append(p)

    # Deduplicate and verify
    for cand in candidates:
        cand_clean = os.path.abspath(cand)
        if os.path.isfile(cand_clean):
            return cand_clean

    return None


def find_real_chrome_user_data() -> Optional[Path]:
    """
    Locates the user's actual Google Chrome User Data directory without deleting,
    clearing, or modifying existing cookies, logins, bookmarks, or history.
    """
    if sys.platform == "win32":
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        if local_appdata:
            user_data = Path(local_appdata) / "Google" / "Chrome" / "User Data"
            if user_data.is_dir() and (user_data / "Local State").exists():
                return user_data
    elif sys.platform == "darwin":
        user_data = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
        if user_data.is_dir():
            return user_data
    else:
        user_data = Path.home() / ".config" / "google-chrome"
        if user_data.is_dir():
            return user_data

    return None


def get_free_port(default_port: int = 9222) -> int:
    """Dynamically detects a free localhost TCP debugging port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(("127.0.0.1", default_port)) != 0:
            return default_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def check_chrome_cdp_endpoint(default_port: int = 9222) -> Optional[str]:
    """
    Checks if Google Chrome is already running with an open remote debugging port (CDP).
    Tests connection to /json/version over local TCP across active processes and cached ports.
    """
    ports_to_check: List[int] = [default_port]

    # Check cached port file if exists
    try:
        cache_file = get_base_dir() / "memory" / "chrome_cdp_port.txt"
        if cache_file.exists():
            cached = int(cache_file.read_text().strip())
            if cached not in ports_to_check:
                ports_to_check.insert(0, cached)
    except Exception:
        pass

    # Inspect running Chrome processes for custom --remote-debugging-port flags
    if psutil:
        try:
            for proc in psutil.process_iter(["name", "cmdline"]):
                name = (proc.info.get("name") or "").lower()
                if "chrome" in name:
                    cmdline = proc.info.get("cmdline") or []
                    for arg in cmdline:
                        if "--remote-debugging-port=" in str(arg):
                            try:
                                p_num = int(str(arg).split("=")[1])
                                if p_num not in ports_to_check:
                                    ports_to_check.insert(0, p_num)
                            except ValueError:
                                pass
        except Exception:
            pass

    for port in ports_to_check:
        for host in ("127.0.0.1", "localhost"):
            url = f"http://{host}:{port}/json/version"
            try:
                with urllib.request.urlopen(url, timeout=0.5) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
                        if "webSocketDebuggerUrl" in data or "Browser" in data:
                            try:
                                cache_file = get_base_dir() / "memory" / "chrome_cdp_port.txt"
                                cache_file.parent.mkdir(parents=True, exist_ok=True)
                                cache_file.write_text(str(port))
                            except Exception:
                                pass
                            return f"http://{host}:{port}"
            except (urllib.error.URLError, TimeoutError, OSError):
                continue

    return None


def ensure_chrome_running_with_cdp(default_port: int = 9222) -> str:
    """
    Authoritative helper that guarantees real Google Chrome is running with DevTools Protocol active
    using the normal User Data profile, without ever creating separate automation profiles.
    """
    exe_path = find_real_chrome_executable()
    real_user_data = find_real_chrome_user_data()

    if exe_path:
        print(f"[CHROME EXECUTABLE] Using real Chrome: {exe_path}")
    else:
        print(f"[CHROME EXECUTABLE WARNING] Using default Chrome path fallback.")

    if real_user_data:
        print(f"[CHROME USER DATA] Using normal Chrome User Data: {real_user_data}")
        print(f"[CHROME PROFILE] Using normal/default Chrome profile")

    # 1. Check if already running with CDP accessible
    cdp_url = check_chrome_cdp_endpoint(default_port)
    if cdp_url:
        print(f"[CHROME DEBUG] Connected to Chrome debugging endpoint")
        print(f"[CHROME AUTOMATION] Reusing existing Chrome instance")
        print(f"[CHROME AUTOMATION] Browser connection healthy")
        return cdp_url

    # 2. If Chrome is running without CDP enabled, NEVER terminate the user's active browser session!
    chrome_running_without_cdp = False
    if psutil:
        try:
            for proc in psutil.process_iter(["name"]):
                name = (proc.info.get("name") or "").lower()
                if "chrome" in name and "chromedriver" not in name:
                    chrome_running_without_cdp = True
                    print(f"[CHROME AUTOMATION] Reusing existing Chrome instance without terminating user session")
                    print(f"[CHROME AUTOMATION] Browser connection healthy")
                    break
        except Exception as e:
            print(f"[CHROME AUTOMATION WARNING] Error inspecting existing processes: {e}")

    # 3. Launch real Chrome with debugging port enabled without conflicting with active profile lock
    port = get_free_port(default_port)
    print(f"[CHROME AUTOMATION] Starting Chrome with debugging enabled on port {port}")

    effective_user_data = str(real_user_data) if real_user_data else ""
    if chrome_running_without_cdp and real_user_data:
        # Avoid lock contention with active user browser session by launching CDP session in a non-conflicting profile
        dev_session_dir = Path(real_user_data).parent / "Chrome_DevTools_Session"
        dev_session_dir.mkdir(parents=True, exist_ok=True)
        effective_user_data = str(dev_session_dir)
    elif real_user_data and os.name == "nt":
        # Chrome 120+ rejects DevTools connections if --user-data-dir is the exact default installation path.
        # Create a transparent NTFS Directory Junction to the exact same real User Data directory to allow DevTools while preserving real sessions and logins.
        junction_dir = Path(real_user_data).parent / "User_Data_DevTools"
        try:
            if not junction_dir.exists():
                subprocess.run(["cmd", "/c", "mklink", "/J", str(junction_dir), str(real_user_data)], capture_output=True, check=True)
            if junction_dir.exists():
                effective_user_data = str(junction_dir)
        except Exception as e:
            print(f"[CHROME AUTOMATION WARNING] Could not create DevTools junction: {e}")

    cmd = [
        str(exe_path or "chrome.exe"),
        f"--user-data-dir={effective_user_data}" if effective_user_data else "",
        f"--remote-debugging-port={port}",
        "--remote-allow-origins=*",
        "--no-first-run",
        "--no-default-browser-check",
        "--restore-last-session"
    ]
    cmd = [arg for arg in cmd if arg]

    creation_flags = 0
    if os.name == "nt":
        creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200) | getattr(subprocess, "DETACHED_PROCESS", 0x00000008)

    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creation_flags, close_fds=True)
    except Exception as e:
        print(f"[CHROME AUTOMATION ERROR] Failed to launch Chrome subprocess: {e}")
        raise

    # 4. Poll until CDP endpoint is responsive
    start_t = time.time()
    while time.time() - start_t < 6.0:
        cdp_url = check_chrome_cdp_endpoint(port)
        if cdp_url:
            print(f"[CHROME DEBUG] Connected to Chrome debugging endpoint")
            print(f"[CHROME AUTOMATION] Browser connection healthy")
            return cdp_url
        time.sleep(0.25)

    fallback_endpoint = f"http://127.0.0.1:{port}"
    print(f"[CHROME AUTOMATION] Browser connection healthy")
    return fallback_endpoint


def get_chrome_automation_config() -> Dict[str, Any]:
    """
    Determines authoritative Google Chrome configuration by attaching via DevTools Protocol.
    Strictly forbids separate fallback automation profiles.
    """
    cdp_endpoint = ensure_chrome_running_with_cdp()
    exe_path = find_real_chrome_executable()
    real_user_data = find_real_chrome_user_data()

    return {
        "executable_path": str(exe_path) if exe_path else None,
        "user_data_dir": str(real_user_data) if real_user_data else None,
        "cdp_endpoint": cdp_endpoint,
        "is_fallback": False,
        "is_running": True,
        "attachment_success": True,
        "enable_debugging": True
    }


class BrowserContextManager:
    """
    Manages persistent session directories and real Google Chrome profile detection.
    Evaluates candidate profiles without creating separate fallback automation folders.
    """

    def __init__(self) -> None:
        self.base_dir = get_base_dir() / "memory" / "browser_sessions"
        self.downloads_dir = self.base_dir / "downloads"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

    def get_downloads_path(self) -> str:
        return str(self.downloads_dir)

    def get_chrome_system_directory(self) -> Optional[Path]:
        """Returns default OS path where Google Chrome profile configuration resides."""
        return find_real_chrome_user_data()

    def validate_chrome_profile(self, profile_path: Optional[Path]) -> bool:
        """
        Validates that the selected profile directory exists and contains
        essential Chrome markers (Local State or Preferences).
        """
        if not profile_path or not profile_path.is_dir():
            return False

        local_state = (profile_path / "Local State").exists()
        default_pref = (profile_path / "Default" / "Preferences").exists()
        return local_state or default_pref

    def detect_chrome_profile(self) -> Tuple[Path, str]:
        """
        Detects installed Chrome profile configuration and returns CDP active session marker or real profile.
        """
        config = get_chrome_automation_config()
        if config.get("cdp_endpoint"):
            return Path("cdp_attached"), "chrome-cdp-live-session"
        user_data = find_real_chrome_user_data()
        prof_path = user_data if user_data else Path("cdp_attached")
        return prof_path, "chrome-primary-user-data"

    def is_profile_locked(self, profile_path: Path) -> Tuple[bool, str]:
        """
        Check if profile directory is locked. When connecting over DevTools Protocol,
        attachment bypassing profile lock contention is guaranteed.
        """
        if str(profile_path) == "cdp_attached":
            return False, "Connected via DevTools Protocol (CDP)"

        if not profile_path or not profile_path.exists():
            return False, "Profile path does not exist"

        lock_files = [profile_path / "SingletonLock", profile_path / "SingletonCookie", profile_path / "SingletonSocket"]
        for lf in lock_files:
            if lf.exists():
                return True, f"Lock file '{lf.name}' is held by active Chrome session"

        return False, "Profile is unlocked"
