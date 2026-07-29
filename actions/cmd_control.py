import subprocess
import sys
import re
import shlex
from pathlib import Path


from core.config import get_gemini_client, get_desktop_path




def _get_platform() -> str:
    if sys.platform == "win32":  return "windows"
    if sys.platform == "darwin": return "macos"
    return "linux"

WIN_COMMAND_MAP = [
    (["disk space", "disk usage", "storage", "free space", "c drive space"],
     "wmic logicaldisk get caption,freespace,size /format:list", False),
    (["running processes", "list processes", "show processes", "active processes", "tasklist"],
     "tasklist /fo table", False),
    (["ip address", "my ip", "network info", "ipconfig"],
     "ipconfig /all", False),
    (["ping", "internet connection", "connected to internet"],
     "ping -n 4 google.com", False),
    (["open ports", "listening ports", "netstat"],
     "netstat -an | findstr LISTENING", False),
    (["wifi networks", "available wifi", "wireless networks"],
     "netsh wlan show networks", False),
    (["system info", "computer info", "hardware info", "pc info", "specs"],
     "systeminfo", False),
    (["cpu usage", "processor usage"],
     "wmic cpu get loadpercentage", False),
    (["memory usage", "ram usage"],
     "wmic OS get FreePhysicalMemory,TotalVisibleMemorySize /Value", False),
    (["windows version", "os version"],
     "ver", False),
    (["installed programs", "installed software", "installed apps"],
     "wmic product get name,version /format:table", False),
    (["battery", "battery level", "power status"],
     "powershell (Get-WmiObject -Class Win32_Battery).EstimatedChargeRemaining", False),
    (["current time", "what time", "system time"],
     "time /t", False),
    (["current date", "what date", "system date"],
     "date /t", False),
    (["desktop files", "files on desktop"],
     f'dir "{Path.home() / "Desktop"}"', False),
    (["downloads", "files in downloads"],
     f'dir "{Path.home() / "Downloads"}"', False),
    (["large files", "biggest files", "largest files"],
     'powershell "Get-ChildItem C:\\ -Recurse -ErrorAction SilentlyContinue | Sort-Object Length -Descending | Select-Object -First 10 FullName,Length | Format-Table"', False),
]

def _find_hardcoded(task: str) -> str | None:
    task_lower = task.lower()
    
    if "notepad" in task_lower or any(ext in task_lower for ext in [".txt", ".log", ".md", ".csv"]):
        file_match = re.search(r'[\"\']?([\S]+\.(?:txt|log|md|csv|json|xml))[\"\']?', task, re.IGNORECASE)
        if file_match:
            filename = file_match.group(1)
            desktop  = get_desktop_path()
            filepath = Path(filename) if Path(filename).is_absolute() else desktop / filename
            return f'notepad "{filepath}"'
        if "notepad" in task_lower:
            return "notepad"
    pip_match = re.search(r"install\s+([\w\-]+)", task_lower)
    if pip_match:
        package = pip_match.group(1)
        return f"pip install {package}"

    for keywords, command, _ in WIN_COMMAND_MAP:
        if command and any(kw in task_lower for kw in keywords):
            return command

    return None

DANGEROUS_PATTERNS = [
    r'\bdel\b', r'\brmdir\b', r'\brd\b', r'\bformat\b', r'\bshutdown\b',
    r'\brestart-computer\b', r'\bstop-process\b', r'\btaskkill\b',
    r'\breg\s+delete\b', r'\bnet\s+user\b', r'\bnet\s+localgroup\b',
    r'\bcd\s+.*&&.*del\b', r'\brm\s+-rf\b', r'\bdiskpart\b'
]
_DANGEROUS_RE = re.compile("|".join(DANGEROUS_PATTERNS), re.IGNORECASE)

SAFE_ALLOWLIST = [
    r'^dir\b', r'^ipconfig\b', r'^systeminfo\b', r'^tasklist\b',
    r'^ping\b', r'^netstat\b', r'^ver\b', r'^time\b', r'^date\b',
    r'^echo\b', r'^type\b', r'^where\b'
]
_SAFE_RE = re.compile("|".join(SAFE_ALLOWLIST), re.IGNORECASE)

def is_dangerous(command: str) -> bool:
    # If it's explicitly allowed, it's not dangerous
    if _SAFE_RE.search(command.strip()):
        return False
    return bool(_DANGEROUS_RE.search(command))

def _is_safe(command: str) -> tuple[bool, str]:
    # We use a very strict check for the "Blocked" list which always overrides
    BLOCKED = [r"\beval\b", r"\b__import__\b", r"\bos\.system\b"]
    for p in BLOCKED:
        if re.search(p, command, re.IGNORECASE):
            return False, f"Prohibited pattern: {p}"

    # Check if command matches predefined list
    normalized = command.strip().lower()
    is_predefined = False
    for keywords, cmd, _ in WIN_COMMAND_MAP:
        if cmd.strip().lower() == normalized:
            is_predefined = True
            break

    if not is_predefined:
        # Strict quote-aware scanner to block command chaining operators outside quotes
        in_dquote = False
        in_squote = False
        i = 0
        while i < len(command):
            char = command[i]
            if char == '"' and not in_squote:
                in_dquote = not in_dquote
            elif char == "'" and not in_dquote:
                in_squote = not in_squote
            elif not in_dquote and not in_squote:
                if char == ';':
                    return False, "Prohibited chaining operator outside quotes: ';'"
                elif char == '&':
                    operator = "&"
                    if i + 1 < len(command) and command[i+1] == '&':
                        operator = "&&"
                    return False, f"Prohibited chaining operator outside quotes: '{operator}'"
                elif char == '|':
                    operator = "|"
                    if i + 1 < len(command) and command[i+1] == '|':
                        operator = "||"
                    return False, f"Prohibited chaining operator outside quotes: '{operator}'"
                elif char == '>':
                    return False, "Prohibited redirect operator outside quotes: '>'"
                elif char == '<':
                    return False, "Prohibited redirect operator outside quotes: '<'"
            i += 1

    return True, "OK"

def _ask_gemini(task: str) -> str:
    try:
        client = get_gemini_client()

        prompt = (
            f"Convert this request to a single Windows CMD command.\n"
            f"Output ONLY the command. No explanation, no markdown, no backticks.\n"
            f"If unsafe or impossible, output: UNSAFE\n\n"
            f"Request: {task}\n\nCommand:"
        )
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        command  = (response.text or "").strip().strip("`").strip()
        if command.startswith("```"):
            lines   = command.split("\n")
            if len(lines) > 2:
                command = "\n".join(lines[1:-1]).strip()
            else:
                command = lines[0].strip()
        return command
    except Exception as e:
        return f"ERROR: {e}"

import threading
import time

class TerminalSession:
    def __init__(self):
        self.process = subprocess.Popen(
            ["cmd.exe"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            cwd=str(Path.home())
        )
        self.output_buffer = ""
        self.lock = threading.Lock()
        
        self.reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self.reader_thread.start()
        
    def _read_output(self):
        while True:
            try:
                char = self.process.stdout.read(1) if self.process.stdout else None
                if not char:
                    break
                with self.lock:
                    self.output_buffer += char
                    # Keep buffer size manageable
                    if len(self.output_buffer) > 20000:
                        self.output_buffer = self.output_buffer[-20000:]
            except Exception:
                break
                
    def execute(self, command: str, wait_time: float = 2.0) -> str:
        if self.process.poll() is not None:
            return "Error: Terminal process died."
            
        with self.lock:
            start_pos = len(self.output_buffer)
            
        try:
            if self.process.stdin:
                self.process.stdin.write(command + "\n")
                self.process.stdin.flush()
        except Exception as e:
            return f"Failed to write to terminal: {e}"
            
        # Wait for output to settle
        time.sleep(wait_time)
        
        with self.lock:
            new_output = self.output_buffer[start_pos:]
            return new_output.strip()

_global_terminal = None

def get_terminal():
    global _global_terminal
    if _global_terminal is None or _global_terminal.process.poll() is not None:
        _global_terminal = TerminalSession()
    return _global_terminal


def cmd_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None
) -> str:
    task    = (parameters or {}).get("task", "").strip()
    command = (parameters or {}).get("command", "").strip()

    if not task and not command:
        return "Please describe what you want to do or provide a command/input."

    if not command:
        command = _find_hardcoded(task)
        if command:
            print(f"[CMD] [STATIC] Hardcoded: {command[:80]}")
        else:
            print(f"[CMD] [AI] Gemini fallback for: {task}")
            command = _ask_gemini(task)
            print(f"[CMD] [OK] Generated: {command[:80]}")
            if command == "UNSAFE":
                return "I cannot generate a safe command for that request, sir."
            if command.startswith("ERROR:"):
                return f"Could not generate command: {command}"

    if is_dangerous(command):
        confirm = (parameters or {}).get("confirm", False)
        if not confirm:
            return (
                f"SECURITY ALERT: The command '{command}' is destructive or sensitive.\n"
                f"If you are sure, please repeat the request and add 'confirm': True to the parameters."
            )

    safe, reason = _is_safe(command)
    if not safe:
        return f"Blocked for safety: {reason}"

    if any(x in command.lower() for x in ["notepad", "explorer", "start "]):
        # Safely parse and run detached GUI commands
        if sys.platform == "win32":
            args = shlex.split(command, posix=False)
        else:
            args = shlex.split(command)
        subprocess.Popen(args, shell=False)
        return f"Opened: {command}"

    # Use persistent terminal for execution
    term = get_terminal()
    output = term.execute(command)
    
    # Log to JARVIS UI so user can see it
    if player:
        log_text = output[:500] + ("..." if len(output) > 500 else "")
        player.write_log(f"> {command}\n{log_text}")

    if not output:
        output = "Command executed. (No immediate output, it may still be running or waiting for input)"

    return f"Executed in persistent terminal.\n\nOutput:\n{output[:2000]}"
