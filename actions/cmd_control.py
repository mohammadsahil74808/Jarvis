import subprocess
import sys
import json
import re
import shlex
from pathlib import Path


from core.config import get_api_key, BASE_DIR, API_CONFIG_PATH, get_gemini_client, get_desktop_path




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
        command  = response.text.strip().strip("`").strip()
        if command.startswith("```"):
            lines   = command.split("\n")
            if len(lines) > 2:
                command = "\n".join(lines[1:-1]).strip()
            else:
                command = lines[0].strip()
        return command
    except Exception as e:
        return f"ERROR: {e}"

def _run_silent(command: str, timeout: int = 20) -> str:
    try:
        platform = _get_platform()
        if platform == "windows":
            is_ps = command.strip().lower().startswith("powershell")
            if is_ps:
                cmd_inner = re.sub(r'^powershell\s+"?', '', command, flags=re.IGNORECASE).rstrip('"')
                result = subprocess.run(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd_inner],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=timeout,
                    shell=False
                )
            else:
                result = subprocess.run(
                    ["cmd", "/c", command],
                    capture_output=True, text=True,
                    encoding="cp1252", errors="replace",
                    timeout=timeout, cwd=str(Path.home()),
                    shell=False
                )
        else:
            # Unix-like: attempt to run without shell first if it's a simple command
            args = shlex.split(command)
            try:
                result = subprocess.run(
                    args, capture_output=True, text=True,
                    errors="replace", timeout=timeout,
                    cwd=str(Path.home()), shell=False
                )
            except FileNotFoundError:
                # Fallback to shell for builtins/complex pipes
                shell = "/bin/zsh" if platform == "macos" else "/bin/bash"
                result = subprocess.run(
                    command, shell=True, executable=shell,
                    capture_output=True, text=True,
                    errors="replace", timeout=timeout,
                    cwd=str(Path.home())
                )

        output = result.stdout.strip()
        error  = result.stderr.strip()
        if output:  return output[:2000]
        if error:   return f"[stderr]: {error[:500]}"
        return "Command executed with no output."

    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s."
    except Exception as e:
        return f"Execution error: {e}"


def _run_visible(command: str) -> None:
    try:
        platform = _get_platform()
        if platform == "windows":
            subprocess.Popen(
                ["cmd", "/k", command],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                shell=False
            )
        elif platform == "macos":
            subprocess.Popen(["osascript", "-e",
                f'tell application "Terminal" to do script "{command}"'])
        else:
            for term in ["gnome-terminal", "xterm", "konsole"]:
                try:
                    subprocess.Popen([term, "--", "bash", "-c", f"{command}; exec bash"])
                    break
                except FileNotFoundError:
                    continue
    except Exception as e:
        print(f"[CMD] [WARNING] Terminal open failed: {e}")


def cmd_control(
    parameters: dict,
    response=None,
    player=None,
    session_memory=None
) -> str:
    task    = (parameters or {}).get("task", "").strip()
    command = (parameters or {}).get("command", "").strip()
    visible = (parameters or {}).get("visible", True)

    if not task and not command:
        return "Please describe what you want to do, sir."

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

    if player:
        player.write_log(f"[CMD] {command[:60]}")

    if any(x in command.lower() for x in ["notepad", "explorer", "start "]):
        # Safely parse and run instead of shell=True
        args = shlex.split(command)
        subprocess.Popen(args, shell=False)
        return f"Opened: {command}"

    if visible:
        _run_visible(command)
        output = _run_silent(command)
        return f"Terminal opened.\n\nOutput:\n{output}"
    else:
        return _run_silent(command)
