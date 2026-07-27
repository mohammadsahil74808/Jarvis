# actions/doctor.py
"""
Jarvis System Health & Environment Doctor (Jarvis Doctor).
Ported and adapted from claw doctor.
Runs comprehensive diagnostics across API keys, dependencies, audio, git, and path security.
"""
from __future__ import annotations

import os
import sys
import platform
import subprocess
from pathlib import Path
from typing import Dict, Any

from core.config import get_api_key, get_groq_api_key, BASE_DIR
from core.path_scope import WorkspacePathScope
from core.cost_tracker import CostTracker


def run_doctor(parameters: dict | None = None, player: Any = None) -> str:
    """Executes complete system health diagnostics and returns a formatted report."""
    results: list[str] = []
    results.append("=== J.A.R.V.I.S. SYSTEM HEALTH DOCTOR REPORT ===\n")

    # 1. OS & Python Environment
    py_ver = sys.version.split()[0]
    os_info = f"{platform.system()} {platform.release()} ({platform.machine()})"
    results.append(f"[OS/Python] OS: {os_info} | Python: {py_ver} [OK]")

    # 2. Workspace & Path Scope
    try:
        scope = WorkspacePathScope.default_scope()
        root_path = scope.roots[0]
        results.append(f"[PathScope] Workspace Root: {root_path} [OK]")
    except Exception as e:
        results.append(f"[PathScope] [WARN] Scope Error: {e}")

    # 3. Gemini API Key & Connection
    gemini_key = get_api_key()
    if gemini_key:
        masked = gemini_key[:4] + "..." + gemini_key[-4:] if len(gemini_key) > 8 else "***"
        results.append(f"[API] Gemini API Key: Configured ({masked}) [OK]")
    else:
        results.append("[API] [WARN] Gemini API Key: NOT FOUND in environment or config!")

    # 4. Groq API Key
    groq_key = get_groq_api_key()
    if groq_key:
        masked_groq = groq_key[:4] + "..." + groq_key[-4:] if len(groq_key) > 8 else "***"
        results.append(f"[API] Groq API Key: Configured ({masked_groq}) [OK]")
    else:
        results.append("[API] Groq API Key: Not configured (Optional fallback)")

    # 5. Desktop Automation Libraries
    try:
        import pyautogui
        results.append("[Libraries] PyAutoGUI: Installed [OK]")
    except ImportError:
        results.append("[Libraries] [WARN] PyAutoGUI: NOT installed!")

    try:
        import pyperclip
        results.append("[Libraries] Pyperclip: Installed [OK]")
    except ImportError:
        results.append("[Libraries] [WARN] Pyperclip: NOT installed!")

    # 6. Audio Engine Dependencies
    try:
        import pyaudio
        results.append("[Audio] PyAudio: Installed [OK]")
    except ImportError:
        results.append("[Audio] [WARN] PyAudio: NOT installed (Mic audio disabled)")

    try:
        import webrtcvad
        results.append("[Audio] WebRTC VAD: Installed [OK]")
    except ImportError:
        results.append("[Audio] [WARN] WebRTC VAD: NOT installed (Voice detection degraded)")

    # 7. Git Working Tree Status
    try:
        git_res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(BASE_DIR),
            capture_output=True,
            text=True,
            timeout=5
        )
        if git_res.returncode == 0:
            modified_files = [line for line in git_res.stdout.splitlines() if line.strip()]
            if not modified_files:
                results.append("[Git] Repository: Clean working tree [OK]")
            else:
                results.append(f"[Git] Repository: {len(modified_files)} modified file(s)")
        else:
            results.append("[Git] Repository: Git not initialized or error")
    except Exception as e:
        results.append(f"[Git] Git Check Warning: {e}")

    # 8. Token Cost Tracker Summary
    tracker_summary = CostTracker.get_instance().get_summary()
    results.append(
        f"[Usage] Session Tokens: {tracker_summary['total_tokens']} | "
        f"Calls: {tracker_summary['total_api_calls']} | "
        f"Est Cost: ${tracker_summary['total_cost_usd']:.4f} USD [OK]"
    )

    results.append("\n[OK] ALL SYSTEM HEALTH DIAGNOSTICS COMPLETED.")
    report_text = "\n".join(results)
    if player and hasattr(player, "write_log"):
        player.write_log("SYS: Doctor diagnostic check complete.")
    return report_text
