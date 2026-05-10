# actions/cursor_agent.py
# ══════════════════════════════════════════════════════════════
# JARVIS Cursor-Style Coding Agent
# Exactly like Cursor AI / Windsurf / Aider:
#   1. Read files
#   2. AI generates changes
#   3. Apply changes
#   4. Run & test automatically
#   5. If error → AI fixes → re-run (loop)
#   6. Repeat until working or max attempts
#
# Uses ONLY FREE models (Groq / NVIDIA / Gemini)
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import os
import re
import sys
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

from core.ai_router import get_ai_router

MAX_FIX_LOOPS  = 6      # Max auto-fix attempts
RUN_TIMEOUT    = 30     # Seconds before killing test run
BACKUP_SUFFIX  = ".jarvis_bak"


# ══════════════════════════════════════════════════════════════
# CORE HELPERS
# ══════════════════════════════════════════════════════════════

def _read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return f"[Could not read file: {e}]"


def _write_file(path: str, content: str) -> None:
    """Write file — auto-backup original first."""
    p = Path(path)
    if p.exists():
        shutil.copy2(p, str(p) + BACKUP_SUFFIX)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def _strip_fences(text: str) -> str:
    """Remove markdown code fences from AI response."""
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z]*\r?\n?", "", text)
    text = re.sub(r"\r?\n?```\s*$", "", text)
    return text.strip()


def _run_code(file_path: str, timeout: int = RUN_TIMEOUT) -> tuple[bool, str]:
    """
    Run a Python file. Returns (success, output).
    success = True if exit code 0 and no ERROR in output.
    """
    try:
        result = subprocess.run(
            [sys.executable, file_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout + result.stderr
        success = result.returncode == 0 and "Error" not in result.stderr
        return success, output
    except subprocess.TimeoutExpired:
        return False, f"TimeoutError: Program ran for {timeout}s without finishing"
    except Exception as e:
        return False, str(e)


def _extract_file_blocks(ai_response: str) -> dict[str, str]:
    """
    Parse AI response for multiple file blocks.
    Supports formats:
      ### filename.py
      ```python
      code here
      ```
    """
    files = {}
    # Pattern: ### some/file.py followed by code block
    pattern = re.compile(
        r"###\s+([\w/\\.\-]+)\s*\n```[a-zA-Z]*\n(.*?)```",
        re.DOTALL
    )
    for match in pattern.finditer(ai_response):
        filename = match.group(1).strip()
        code     = match.group(2).strip()
        files[filename] = code
    return files


# ══════════════════════════════════════════════════════════════
# DIFF APPLY (Cursor-style patch)
# ══════════════════════════════════════════════════════════════

def _apply_diff(original: str, diff_text: str) -> str:
    """
    Apply a simple SEARCH/REPLACE diff format:
      <<<<<<< SEARCH
      old code
      =======
      new code
      >>>>>>> REPLACE
    """
    result = original
    blocks = re.findall(
        r"<<<<<<<\s*SEARCH\s*\n(.*?)\n=======\s*\n(.*?)\n>>>>>>>\s*REPLACE",
        diff_text,
        re.DOTALL
    )
    for old, new in blocks:
        if old in result:
            result = result.replace(old, new, 1)
        else:
            # Fuzzy match — try stripping whitespace
            old_stripped = old.strip()
            for line in result.split("\n"):
                if line.strip() == old_stripped:
                    result = result.replace(line, new, 1)
                    break
    return result


# ══════════════════════════════════════════════════════════════
# MAIN CURSOR AGENT FUNCTION
# ══════════════════════════════════════════════════════════════

def cursor_agent(parameters: dict, player=None, **kwargs) -> str:
    """
    JARVIS Cursor-style coding agent.

    Parameters (from JARVIS tool call)
    ----------
    task         : what to do (e.g. "add a dark mode toggle to this file")
    files        : list of file paths to work on
    project_dir  : optional project directory to scan
    run_after    : True = run the main file after editing and auto-fix errors
    main_file    : which file to run for testing (default: first .py file)
    language     : "python" | "javascript" | "any" (default: auto-detect)
    """
    router      = get_ai_router()
    task        = parameters.get("task",        "")
    files       = parameters.get("files",       [])
    project_dir = parameters.get("project_dir", "")
    run_after   = parameters.get("run_after",   True)
    main_file   = parameters.get("main_file",   "")
    language    = parameters.get("language",    "auto")

    if not task:
        return "Task batao — kya karna hai code mein?"

    # ── Collect files ──────────────────────────────────────
    if project_dir and not files:
        p = Path(project_dir).expanduser()
        if p.exists():
            # Auto-collect relevant source files
            exts = {".py", ".js", ".ts", ".html", ".css", ".json"}
            files = [
                str(f) for f in p.rglob("*")
                if f.suffix in exts
                and "node_modules" not in str(f)
                and "__pycache__"   not in str(f)
                and BACKUP_SUFFIX   not in str(f)
            ][:20]  # max 20 files

    if not files:
        return (
            "Koi file nahi mili.\n"
            "Bolo: 'edit main.py — add error handling'\n"
            "Ya: 'fix all bugs in my project at C:/Users/Sahil/myproject'"
        )

    if player:
        player.write_log(f"[CursorAgent] Task: {task[:60]}")
        player.write_log(f"[CursorAgent] Files: {len(files)}")

    # ── Read all files ─────────────────────────────────────
    file_contents = {}
    for f in files:
        content = _read_file(f)
        file_contents[f] = content

    # ── Build context for AI ───────────────────────────────
    files_context = "\n\n".join(
        f"### {Path(f).name} ({f})\n```\n{content[:3000]}\n```"
        for f, content in file_contents.items()
    )

    # ── Step 1: AI generates changes ───────────────────────
    print(f"[CursorAgent] Generating changes for: {task}")

    system_prompt = """You are an elite software engineer like Cursor AI.
You edit code precisely and safely.

When given files and a task:
1. Output ONLY the complete updated file(s)
2. Use this format for each file:
   ### filename.py
   ```python
   complete file content here
   ```
3. If task is a small change, use SEARCH/REPLACE format:
   <<<<<<< SEARCH
   old code line(s)
   =======
   new code line(s)
   >>>>>>> REPLACE
4. Be minimal — only change what's needed
5. Keep all existing functionality intact
6. Add clear comments for any new code"""

    user_prompt = f"""Task: {task}

Files to edit:
{files_context}

Output the complete updated file(s) with changes applied."""

    ai_response = router.generate(
        prompt=user_prompt,
        system=system_prompt,
        task="code",
        max_tokens=4096,
    )

    # ── Step 2: Apply changes ──────────────────────────────
    changes_made = []

    # Try multi-file block format first
    file_blocks = _extract_file_blocks(ai_response)

    if file_blocks:
        for fname, new_content in file_blocks.items():
            # Match to actual file paths
            matching = [
                f for f in files
                if Path(f).name == fname or f.endswith(fname)
            ]
            target = matching[0] if matching else str(Path(files[0]).parent / fname)
            _write_file(target, new_content)
            changes_made.append(target)
            print(f"[CursorAgent] ✓ Updated: {Path(target).name}")

    elif "<<<<<<< SEARCH" in ai_response:
        # Apply diff to first file
        target  = files[0]
        original = file_contents[target]
        updated  = _apply_diff(original, ai_response)
        if updated != original:
            _write_file(target, updated)
            changes_made.append(target)
            print(f"[CursorAgent] ✓ Diff applied: {Path(target).name}")

    else:
        # Single file — treat whole response as new content
        new_content = _strip_fences(ai_response)
        if new_content and len(new_content) > 50:
            _write_file(files[0], new_content)
            changes_made.append(files[0])
            print(f"[CursorAgent] ✓ Replaced: {Path(files[0]).name}")

    if not changes_made:
        return f"AI ne changes generate kiye lekin apply nahi ho paye.\nAI Response:\n{ai_response[:500]}"

    if not run_after:
        names = [Path(f).name for f in changes_made]
        return f"✓ {len(changes_made)} file(s) updated: {', '.join(names)}"

    # ── Step 3: Auto-test loop (Cursor-style) ─────────────
    test_file = main_file
    if not test_file:
        # Auto-detect main file
        py_files  = [f for f in changes_made if f.endswith(".py")]
        test_file = py_files[0] if py_files else None

    if not test_file or not test_file.endswith(".py"):
        names = [Path(f).name for f in changes_made]
        return (
            f"✓ Changes applied to: {', '.join(names)}\n"
            f"Auto-test skipped (no Python file to run)."
        )

    print(f"[CursorAgent] Running: {test_file}")
    if player:
        player.write_log(f"[CursorAgent] Testing: {Path(test_file).name}")

    for attempt in range(1, MAX_FIX_LOOPS + 1):
        success, output = _run_code(test_file, timeout=RUN_TIMEOUT)

        if success:
            print(f"[CursorAgent] ✓ Tests passed on attempt {attempt}!")
            return (
                f"✓ Task complete!\n"
                f"Files changed : {', '.join(Path(f).name for f in changes_made)}\n"
                f"Test result   : PASSED (attempt {attempt})\n"
                f"Output        :\n{output[:400]}"
            )

        print(f"[CursorAgent] Attempt {attempt}/{MAX_FIX_LOOPS} — Error detected")
        print(f"[CursorAgent] Error: {output[:200]}")

        if attempt >= MAX_FIX_LOOPS:
            break

        # Ask AI to fix the error
        print(f"[CursorAgent] AI fixing error...")
        if player:
            player.write_log(f"[CursorAgent] Auto-fixing (attempt {attempt})...")

        current_content = _read_file(test_file)
        fix_prompt = f"""Fix this Python error.

File: {Path(test_file).name}
Error:
{output[:1500]}

Current code:
```python
{current_content[:3000]}
```

Return the COMPLETE fixed Python file only. No explanation."""

        fixed_code = router.generate(
            prompt=fix_prompt,
            system="You are an expert Python debugger. Fix errors precisely.",
            task="code",
        )
        fixed_code = _strip_fences(fixed_code)

        if fixed_code and len(fixed_code) > 30:
            _write_file(test_file, fixed_code)
            print(f"[CursorAgent] Fix applied — retesting...")
            time.sleep(0.5)

    return (
        f"⚠ Task applied but tests still failing after {MAX_FIX_LOOPS} attempts.\n"
        f"Files changed : {', '.join(Path(f).name for f in changes_made)}\n"
        f"Last error    : {output[:400]}\n"
        f"Backups saved : {BACKUP_SUFFIX} files in same directory."
    )


# ── TOOL DECLARATION ──────────────────────────────────────────
CURSOR_AGENT_TOOL = {
    "name": "cursor_agent",
    "description": (
        "Cursor/Windsurf-style AI coding agent. Reads your code files, "
        "makes requested changes using AI, then automatically runs and tests "
        "the code. If there are errors, it fixes them automatically in a loop "
        "until the code works. Use when user wants to edit, fix, refactor, "
        "or add features to existing code files."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "What to do — e.g. 'add dark mode', 'fix all bugs', 'add error handling'",
            },
            "files": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of file paths to edit (optional if project_dir given)",
            },
            "project_dir": {
                "type": "string",
                "description": "Project folder path — agent will find all source files automatically",
            },
            "run_after": {
                "type": "boolean",
                "description": "Run and auto-test after editing (default: true)",
            },
            "main_file": {
                "type": "string",
                "description": "Which file to run for testing (optional — auto-detected)",
            },
        },
        "required": ["task"],
    },
}
