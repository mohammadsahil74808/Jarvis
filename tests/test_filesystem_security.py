# tests/test_filesystem_security.py

import pytest
import os
import tempfile
from mcp_client.filesystem_security import (
    PathSecurity,
    FileSystemSecurityManager,
    RISK_SAFE,
    RISK_CONFIRMATION_REQUIRED,
    RISK_BLOCKED,
    AuditLogger
)

def test_drive_scoping_and_normalization():
    sec = PathSecurity()
    assert sec.is_allowed_drive("C:\\Projects\\Jarvis")
    assert sec.is_allowed_drive("D:\\Projects\\Test")
    assert sec.is_allowed_drive("c:/projects/jarvis")
    assert sec.is_allowed_drive("d:/some_folder/sub")
    assert not sec.is_allowed_drive("E:\\Projects")
    assert not sec.is_allowed_drive("F:\\Projects")

def test_protected_windows_paths():
    sec = PathSecurity()
    assert sec.is_protected_system_path("C:\\Windows\\System32")
    assert sec.is_protected_system_path("C:\\Program Files\\NodeJS")
    assert sec.is_protected_system_path("C:\\Program Files (x86)\\Common Files")
    assert sec.is_protected_system_path("C:\\ProgramData\\Package Cache")
    assert sec.is_protected_system_path("C:\\Users\\user\\AppData\\Local\\Temp")
    assert not sec.is_protected_system_path("C:\\Projects\\Jarvis")
    assert not sec.is_protected_system_path("D:\\Projects\\Test")

def test_blocked_credential_paths():
    sec = PathSecurity()
    assert sec.is_blocked_credential_path("C:\\Users\\user\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cookies")
    assert sec.is_blocked_credential_path("C:\\Users\\user\\.ssh\\id_rsa")
    assert sec.is_blocked_credential_path("C:\\Users\\user\\.aws\\credentials")
    assert not sec.is_blocked_credential_path("C:\\Projects\\Jarvis\\main.py")

def test_safe_operations():
    mgr = FileSystemSecurityManager()
    
    # Read/List/Inspect are SAFE
    risk, msg, path = mgr.evaluate_operation("read_file", {"path": "C:\\Projects\\Jarvis\\main.py"})
    assert risk == RISK_SAFE
    assert msg is None

    risk, msg, path = mgr.evaluate_operation("list_directory", {"path": "D:\\Projects"})
    assert risk == RISK_SAFE
    assert msg is None

    risk, msg, path = mgr.evaluate_operation("search_files", {"path": "C:\\Projects", "pattern": "*.py"})
    assert risk == RISK_SAFE
    assert msg is None

def test_confirmation_required_operations():
    mgr = FileSystemSecurityManager()
    
    # Delete operations require confirmation
    risk, msg, path = mgr.evaluate_operation("delete_file", {"path": "D:\\Projects\\test.txt"})
    assert risk == RISK_CONFIRMATION_REQUIRED
    assert "permanently delete" in msg
    assert "proceed" in msg

    # Script execution requires confirmation
    risk, msg, path = mgr.evaluate_operation("execute_file", {"path": "C:\\Projects\\run.bat"})
    assert risk == RISK_CONFIRMATION_REQUIRED
    assert "execute" in msg

    # Modifying protected system paths requires confirmation
    risk, msg, path = mgr.evaluate_operation("write_file", {"path": "C:\\Program Files\\test.txt"})
    assert risk == RISK_CONFIRMATION_REQUIRED
    assert "protected system location" in msg

def test_blocked_operations():
    mgr = FileSystemSecurityManager()
    
    # Unallowed drive access blocked
    risk, msg, path = mgr.evaluate_operation("read_file", {"path": "E:\\Secret.txt"})
    assert risk == RISK_BLOCKED
    assert "SECURITY BLOCK" in msg

    # Credential theft blocked
    risk, msg, path = mgr.evaluate_operation("read_file", {"path": "C:\\Users\\user\\AppData\\Local\\Google\\Chrome\\User Data\\Default\\Cookies"})
    assert risk == RISK_BLOCKED
    assert "SECURITY BLOCK" in msg

    # Root drive wiping blocked
    risk, msg, path = mgr.evaluate_operation("delete_directory", {"path": "C:\\"})
    assert risk == RISK_BLOCKED
    assert "SECURITY BLOCK" in msg

def test_startup_logs(capsys):
    mgr = FileSystemSecurityManager()
    mgr.print_startup_logs()
    captured = capsys.readouterr().out
    assert "[MCP FILESYSTEM] C: drive access enabled" in captured
    assert "[MCP FILESYSTEM] D: drive access enabled" in captured
    assert "[SECURITY] Filesystem permission layer active" in captured
    assert "[SECURITY] Destructive operations require confirmation" in captured
