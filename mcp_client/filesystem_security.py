# mcp_client/filesystem_security.py
"""
Filesystem Security and Permission Layer for J.A.R.V.I.S. MCP Filesystem.
Provides path normalization, drive scoping (C:\\ and D:\\), risk classification,
user confirmation gating for destructive operations, absolute blocking of security violations,
and privacy-safe audit logging.
"""

import os
import re
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List

# Allowed Drive Roots
ALLOWED_DRIVES = {"C:", "D:"}

# Protected / High-Risk Windows Paths
PROTECTED_PATH_PATTERNS = [
    r'^[a-zA-Z]:\\windows(?:\b|\\)',
    r'^[a-zA-Z]:\\program files(?:\b|\\)',
    r'^[a-zA-Z]:\\program files \(x86\)(?:\b|\\)',
    r'^[a-zA-Z]:\\programdata(?:\b|\\)',
    r'^[a-zA-Z]:\\users\\[^\\]+\\appdata(?:\b|\\)',
    r'^[a-zA-Z]:\\system volume information(?:\b|\\)',
    r'^[a-zA-Z]:\\\$recycle\.bin(?:\b|\\)',
    r'^[a-zA-Z]:\\bootmgr$',
    r'^[a-zA-Z]:\\pagefile\.sys$',
    r'^[a-zA-Z]:\\swapfile\.sys$',
]

# Sensitive Files / Credentials to ABSOLUTELY BLOCK from extraction
BLOCKED_SENSITIVE_PATTERNS = [
    r'\\appdata\\local\\google\\chrome\\user data\\.*\\(?:cookies|login data|web data)',
    r'\\appdata\\roaming\\mozilla\\firefox\\profiles\\.*\\(?:cookies\.sqlite|logins\.json)',
    r'\\\.ssh\\(?:id_rsa|id_ed25519|id_dsa)',
    r'\\\.aws\\credentials',
    r'\\system32\\config\\(?:sam|system|security)',
]

# Risk Levels
RISK_SAFE = "SAFE"
RISK_CONFIRMATION_REQUIRED = "CONFIRMATION_REQUIRED"
RISK_BLOCKED = "BLOCKED"

# Affirmative confirmation phrases
AFFIRMATIVE_WORDS = {
    "yes", "proceed", "do it", "confirm", "go ahead", "yep", "yeah", "sure", "ok",
    "okay", "haan", "ha", "karo", "kardo", "aage badho", "continue", "allow", "approve"
}

class PathSecurity:
    """Handles path normalization, drive scoping, and protected path checks."""

    @staticmethod
    def normalize_path(raw_path: str) -> str:
        """Normalizes raw path string into absolute Windows path format."""
        if not raw_path:
            return ""
        clean = str(raw_path).strip().strip("'\"")
        # Replace forward slashes with backslashes
        clean = os.path.normpath(os.path.abspath(clean))
        return clean

    @staticmethod
    def is_allowed_drive(path_str: str) -> bool:
        """Verifies if path belongs to allowed drives (C:\\ or D:\\)."""
        norm = PathSecurity.normalize_path(path_str)
        drive = os.path.splitdrive(norm)[0].upper()
        return drive in ALLOWED_DRIVES

    @staticmethod
    def is_protected_system_path(path_str: str) -> bool:
        """Checks if a path falls inside protected/high-risk Windows directories."""
        norm = PathSecurity.normalize_path(path_str).lower()
        for pattern in PROTECTED_PATH_PATTERNS:
            if re.search(pattern, norm):
                return True
        return False

    @staticmethod
    def is_blocked_credential_path(path_str: str) -> bool:
        """Checks if a path targets credentials, cookies, or session tokens."""
        norm = PathSecurity.normalize_path(path_str).lower()
        for pattern in BLOCKED_SENSITIVE_PATTERNS:
            if re.search(pattern, norm):
                return True
        return False


class AuditLogger:
    """Logs every filesystem operation cleanly without logging file contents or secrets."""

    @staticmethod
    def log_event(
        operation: str,
        source_path: str,
        destination_path: Optional[str],
        risk_level: str,
        confirmation_required: bool,
        confirmation_result: str,
        final_result: str
    ) -> None:
        """Appends audit event to memory/filesystem_audit.log."""
        try:
            from core.config import get_base_dir
            mem_dir = get_base_dir() / "memory"
            mem_dir.mkdir(parents=True, exist_ok=True)
            log_file = mem_dir / "filesystem_audit.log"

            event = {
                "timestamp": datetime.now().isoformat(),
                "operation": operation,
                "source_path": PathSecurity.normalize_path(source_path) if source_path else None,
                "destination_path": PathSecurity.normalize_path(destination_path) if destination_path else None,
                "risk_level": risk_level,
                "confirmation_required": confirmation_required,
                "confirmation_result": confirmation_result,
                "final_result": final_result
            }

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(event) + "\n")
        except Exception as e:
            print(f"[AUDIT LOG WARNING] Could not write audit log: {e}")


class FileSystemSecurityManager:
    """Centralized permission and risk validation engine for Filesystem MCP tools."""

    def __init__(self):
        self.pending_confirmation: Optional[Dict[str, Any]] = None

    def print_startup_logs(self):
        """Prints required filesystem startup log lines."""
        print("[MCP FILESYSTEM] C: drive access enabled")
        print("[MCP FILESYSTEM] D: drive access enabled")
        print("[SECURITY] Filesystem permission layer active")
        print("[SECURITY] Destructive operations require confirmation")

    def evaluate_operation(self, tool_name: str, arguments: dict) -> Tuple[str, Optional[str], str]:
        """
        Evaluates a filesystem operation before execution.
        Returns Tuple[risk_level, confirmation_message_or_block_reason, path_summary].
        """
        tool = str(tool_name).lower().strip()

        # Extract primary and secondary paths
        path = str(arguments.get("path") or arguments.get("file_path") or arguments.get("directory") or arguments.get("source") or "")
        dest = str(arguments.get("destination") or arguments.get("target") or arguments.get("dest") or "")

        norm_path = PathSecurity.normalize_path(path) if path else ""
        norm_dest = PathSecurity.normalize_path(dest) if dest else ""

        # 1. Drive Scope Check
        if norm_path and not PathSecurity.is_allowed_drive(norm_path):
            drive = os.path.splitdrive(norm_path)[0]
            err = f"SECURITY BLOCK: Access to drive '{drive}' is denied. Only C:\\ and D:\\ are accessible."
            AuditLogger.log_event(tool, norm_path, norm_dest, RISK_BLOCKED, False, "BLOCKED", "BLOCKED")
            return (RISK_BLOCKED, err, norm_path)

        if norm_dest and not PathSecurity.is_allowed_drive(norm_dest):
            drive = os.path.splitdrive(norm_dest)[0]
            err = f"SECURITY BLOCK: Access to destination drive '{drive}' is denied. Only C:\\ and D:\\ are accessible."
            AuditLogger.log_event(tool, norm_path, norm_dest, RISK_BLOCKED, False, "BLOCKED", "BLOCKED")
            return (RISK_BLOCKED, err, norm_dest)

        # 2. Blocked Credentials / Token Extraction Check
        if PathSecurity.is_blocked_credential_path(norm_path) or PathSecurity.is_blocked_credential_path(norm_dest):
            err = "SECURITY BLOCK: Access to sensitive browser cookies, session tokens, or credentials is strictly prohibited."
            AuditLogger.log_event(tool, norm_path, norm_dest, RISK_BLOCKED, False, "BLOCKED", "BLOCKED")
            return (RISK_BLOCKED, err, norm_path)

        # 3. Blocked Wiping / Root Partition Destruction Check
        if tool in ("delete_directory", "rmdir", "delete_file", "bulk_delete"):
            if norm_path.upper() in ("C:\\", "D:\\", "C:", "D:"):
                err = "SECURITY BLOCK: Root drive formatting, partition destruction, or wiping is strictly prohibited."
                AuditLogger.log_event(tool, norm_path, norm_dest, RISK_BLOCKED, False, "BLOCKED", "BLOCKED")
                return (RISK_BLOCKED, err, norm_path)

        # 4. Check Protected Windows System Locations
        is_protected = PathSecurity.is_protected_system_path(norm_path) or PathSecurity.is_protected_system_path(norm_dest)

        # 5. Risk Classification by Tool / Operation Type
        # A. Delete / Remove / Destroy operations
        if any(kw in tool for kw in ["delete", "remove", "unlink", "rmdir", "destroy", "format", "wipe"]):
            msg = f"Sir, this will permanently delete '{norm_path}'. Do you want me to proceed?"
            return (RISK_CONFIRMATION_REQUIRED, msg, norm_path)

        # B. Executing scripts or binaries
        if tool in ("execute_file", "run_script", "launch") or any(norm_path.endswith(ext) for ext in [".exe", ".bat", ".cmd", ".ps1", ".vbs", ".msi"]):
            msg = f"Sir, this will execute binary/script '{norm_path}'. Do you want me to proceed?"
            return (RISK_CONFIRMATION_REQUIRED, msg, norm_path)

        # C. Overwriting an existing non-empty file
        if tool in ("write_file", "edit_file", "move_file", "copy_file"):
            target_to_check = norm_dest if norm_dest else norm_path
            if target_to_check and os.path.exists(target_to_check) and os.path.isfile(target_to_check):
                try:
                    size = os.path.getsize(target_to_check)
                    if size > 10240:  # File > 10 KB or important
                        msg = f"Sir, this will overwrite existing file '{target_to_check}' ({size // 1024} KB). Do you want me to proceed?"
                        return (RISK_CONFIRMATION_REQUIRED, msg, target_to_check)
                except Exception:
                    pass

        # D. Any mutation inside a Protected System Path requires confirmation
        if is_protected and tool in ("write_file", "edit_file", "create_directory", "move_file", "copy_file"):
            msg = f"Sir, this will modify protected system location '{norm_path}'. Do you want me to proceed?"
            return (RISK_CONFIRMATION_REQUIRED, msg, norm_path)

        # 6. SAFE Operations (Listing, Reading, Normal File/Folder Creation)
        return (RISK_SAFE, None, norm_path)

    def set_pending_confirmation(self, tool_name: str, arguments: dict, prompt_msg: str):
        """Stores pending risky operation awaiting user confirmation."""
        self.pending_confirmation = {
            "tool_name": tool_name,
            "arguments": arguments,
            "prompt_msg": prompt_msg,
            "timestamp": time.time()
        }

    def clear_pending_confirmation(self):
        """Clears pending confirmation state."""
        self.pending_confirmation = None

    def is_affirmative_response(self, text: str) -> bool:
        """Checks if a user response string is an explicit affirmative confirmation."""
        if not text:
            return False
        clean = text.lower().strip().strip(".!?,")
        words = set(clean.split())
        return bool(words.intersection(AFFIRMATIVE_WORDS) or clean in AFFIRMATIVE_WORDS)


# Global singleton instance for JARVIS security layer
_security_manager = None

def get_filesystem_security_manager() -> FileSystemSecurityManager:
    global _security_manager
    if _security_manager is None:
        _security_manager = FileSystemSecurityManager()
    return _security_manager
