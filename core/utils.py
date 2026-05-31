# core/utils.py  ← REPLACE
import time, functools, random

def retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempts, current_delay = 0, delay
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts == max_attempts:
                        raise
                    time.sleep(current_delay + random.uniform(0, 0.1 * current_delay))
                    current_delay *= backoff
            return None
        return wrapper
    return decorator

def async_retry(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempts, current_delay = 0, delay
            while attempts < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts == max_attempts:
                        raise
                    import asyncio
                    await asyncio.sleep(current_delay + random.uniform(0, 0.1 * current_delay))
                    current_delay *= backoff
            return None
        return wrapper
    return decorator

def open_browser(url: str) -> bool:
    import platform, subprocess, webbrowser
    current_os = platform.system()
    try:
        if current_os == "Windows":
            subprocess.Popen(["start", "msedge", url], shell=True)
            return True
        elif current_os == "Darwin":
            subprocess.Popen(["open", "-a", "Microsoft Edge", url])
            return True
        else:
            subprocess.Popen(["microsoft-edge", url])
            return True
    except Exception as e:
        webbrowser.open(url)
        return True

# ── SAPI COM — created once, reused instantly ──────────────────
_sapi_voice = None

def speak_local(text: str) -> None:
    """
    INSTANT local TTS via SAPI COM object.
    OLD: spawned PowerShell process = 1.5-3s delay per call
    NEW: reuses COM object = ~30ms, no new process ever
    """
    global _sapi_voice
    if not text or not text.strip():
        return

    # Try SAPI COM (fastest — no process spawn)
    if _sapi_voice is None:
        try:
            import win32com.client
            _sapi_voice = win32com.client.Dispatch("SAPI.SpVoice")
        except Exception:
            _sapi_voice = False

    if _sapi_voice and _sapi_voice is not False:
        try:
            _sapi_voice.Speak(text, 1)  # 1 = SVSFlagsAsync (non-blocking)
            return
        except Exception:
            _sapi_voice = None  # Reset and fall through

    # Fallback: lighter PowerShell (no Add-Type overhead)
    try:
        import subprocess
        safe = text.replace("'", "").replace('"', "")[:200]
        subprocess.Popen(
            ["PowerShell", "-NoProfile", "-NonInteractive", "-Command",
             f'(New-Object -ComObject SAPI.SpVoice).Speak("{safe}")'],
            creationflags=0x08000000   # CREATE_NO_WINDOW
        )
    except Exception as e:
        print(f"[LocalTTS] Failed: {e}")
