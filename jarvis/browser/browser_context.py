# jarvis/browser/browser_context.py
"""
Persistent session storage and Firefox profile detector for Browser Use integration.
Detects real system Firefox user profiles from FIREFOX_PROFILE_PATH or system profiles with full evaluation logging.
"""

from __future__ import annotations

import configparser
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List, Set

from core.config import get_base_dir


class BrowserContextManager:
    """
    Manages persistent session directories and real system Firefox profile detection.
    Evaluates all candidate profiles, validates essential profile markers (places.sqlite / prefs.js),
    and prefers .default-release or FIREFOX_PROFILE_PATH with full logging transparency.
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

    def get_firefox_system_directory(self) -> Path:
        """Returns default OS path where Firefox profile configuration resides."""
        if sys.platform == "win32":
            return Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox"
        elif sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Firefox"
        else:
            return Path.home() / ".mozilla" / "firefox"

    def validate_firefox_profile(self, profile_path: Optional[Path]) -> bool:
        """
        Validates that the selected profile directory exists and contains
        essential Firefox profile markers: places.sqlite or prefs.js.
        """
        if not profile_path or not profile_path.is_dir():
            return False

        places = (profile_path / "places.sqlite").exists()
        prefs = (profile_path / "prefs.js").exists()

        return places or prefs

    def detect_firefox_profile(self) -> Tuple[Path, str]:
        """
        Always uses an isolated browser profile in jarvis/browser_profile 
        to ensure safety and prevent lock contention with the user's main browser.
        """
        isolated_dir = get_base_dir() / "jarvis" / "browser_profile"
        isolated_dir.mkdir(parents=True, exist_ok=True)
        print(f"[FIREFOX PROFILE] Using isolated automation profile: {isolated_dir}")
        return isolated_dir, "jarvis-isolated"

    def is_profile_locked(self, profile_path: Path) -> Tuple[bool, str]:
        """
        Fast and explicit check to determine if the Firefox profile is locked
        by trying to acquire an exclusive lock on its parent.lock file.
        """
        if not profile_path or not profile_path.exists():
            return False, "Profile path does not exist"

        lock_files = [profile_path / "parent.lock", profile_path / ".parentlock", profile_path / "lock"]
        for lf in lock_files:
            if lf.exists():
                try:
                    with open(lf, "a"):
                        pass
                except (PermissionError, OSError) as e:
                    reason = f"Lock file '{lf.name}' is exclusively locked by active Firefox process ({e})"
                    print(f"[FIREFOX PROFILE LOCK DETECTED] {reason}")
                    return True, reason

        return False, "Profile is unlocked"
