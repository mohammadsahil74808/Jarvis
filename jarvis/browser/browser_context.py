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
        Evaluates all available Firefox profiles on the system, logging full details
        for every candidate, and selects the optimal profile according to strict priority:
        1. FIREFOX_PROFILE_PATH environment variable / config value.
        2. Valid *.default-release profiles.
        3. Valid *.default profiles from profiles.ini / Profiles directory.
        4. Fallback automation profile if no valid system profile passes validation.
        """
        ff_dir = self.get_firefox_system_directory()
        profiles_dir = ff_dir / "Profiles"
        ini_path = ff_dir / "profiles.ini"
        installs_ini_path = ff_dir / "installs.ini"

        env_profile = os.environ.get("FIREFOX_PROFILE_PATH")
        if not env_profile:
            try:
                from core.config import get_config
                env_profile = get_config().get("firefox_profile_path")
            except Exception:
                pass

        candidates: Set[Path] = set()

        # 1. User configured path
        if env_profile:
            candidates.add(Path(env_profile).resolve())

        # 2. Profiles directory scan
        if profiles_dir.exists():
            for child in profiles_dir.glob("*"):
                if child.is_dir():
                    candidates.add(child.resolve())

        # 3. Parse profiles.ini
        if ini_path.exists():
            parser = configparser.ConfigParser()
            try:
                parser.read(ini_path, encoding="utf-8")
                for section in parser.sections():
                    rel_path = parser[section].get("Path") or parser[section].get("Default")
                    if rel_path:
                        is_rel = parser[section].get("IsRelative", "1") == "1"
                        target = (ff_dir / rel_path.replace("/", os.sep)) if is_rel else Path(rel_path)
                        candidates.add(target.resolve())
            except Exception as e:
                print(f"[FIREFOX DETECT WARNING] Error parsing profiles.ini: {e}")

        print("\n=== EVALUATING ALL CANDIDATE FIREFOX PROFILES ===")
        valid_scored_candidates: List[Tuple[float, Path, str]] = []

        for candidate in sorted(candidates, key=lambda x: str(x)):
            print(f"\nFound profile:\n{candidate}")

            exists = candidate.exists() and candidate.is_dir()
            has_places = (candidate / "places.sqlite").exists() if exists else False
            has_prefs = (candidate / "prefs.js").exists() if exists else False
            has_compat = (candidate / "compatibility.ini").exists() if exists else False
            has_installs = installs_ini_path.exists()

            mtime_str = "N/A"
            mtime_val = 0.0
            if exists:
                try:
                    mtime_val = candidate.stat().st_mtime
                    mtime_str = datetime.fromtimestamp(mtime_val).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    pass

            print(f"  - exists: {exists}")
            print(f"  - places.sqlite: {has_places}")
            print(f"  - prefs.js: {has_prefs}")
            print(f"  - compatibility.ini: {has_compat}")
            print(f"  - installs.ini: {has_installs}")
            print(f"  - last modified time: {mtime_str}")

            is_valid = self.validate_firefox_profile(candidate)

            if not exists:
                print("Rejected because:\nDirectory does not exist")
            elif not is_valid:
                print("Rejected because:\nvalidation failed (missing places.sqlite and prefs.js)")
            else:
                print("Accepted candidate for selection scoring")

                score = 0.0
                # Rule 1: FIREFOX_PROFILE_PATH env override (always wins)
                if env_profile and Path(env_profile).resolve() == candidate:
                    score += 10000.0

                # Rule 4: Always prefer .default-release over .default
                if candidate.name.endswith(".default-release") or "default-release" in candidate.name:
                    score += 1000.0
                elif candidate.name.endswith(".default") or "default" in candidate.name:
                    score += 100.0

                # Prefer non default-default profiles
                if "default-default" in candidate.name:
                    score -= 50.0

                # Add timestamp tie-breaker
                score += (mtime_val / 1e10)

                valid_scored_candidates.append((score, candidate, mtime_str))

        print("\n=== PROFILE DECISION PROCESS ===")
        if not valid_scored_candidates:
            print("No valid system Firefox profiles passed validation.")
            fallback_dir = self.base_dir / "firefox_profile"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            print(f"[FIREFOX PROFILE] Using fallback automation profile: {fallback_dir}")
            return fallback_dir, "Fallback Automation Profile"

        valid_scored_candidates.sort(key=lambda x: x[0], reverse=True)
        for rank, (score, path_obj, mtime) in enumerate(valid_scored_candidates, 1):
            print(f"Rank {rank} (Score {score:.4f}): {path_obj} [Last Modified: {mtime}]")

        winning_profile = valid_scored_candidates[0][1]
        print(f"\n[FIREFOX PROFILE] Using: {winning_profile}\n")
        return winning_profile, winning_profile.name

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
