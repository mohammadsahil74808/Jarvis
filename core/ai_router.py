import os
import json
import re
from pathlib import Path
from groq import Groq
from core.config import get_groq_api_key, BASE_DIR

def is_coding_request(text: str) -> bool:
    """Detects if the user text has a coding/programming intent."""
    text = text.lower()
    coding_keywords = [
        "write code", "fix bug", "debug", "create website", "make python script",
        "build app", "html", "css", "js", "javascript", "react", "sql query",
        "explain code", "refactor", "optimize code", "project structure",
        "programming", "python", "script", "code layout", "how to code",
        "fix error", "syntax", "develop", "npm", "pip install"
    ]
    
    # Check for direct keyword matches
    if any(kw in text for kw in coding_keywords):
        return True
    
    # Check for code-like patterns (e.g. extension names or short snippets)
    if re.search(r'\b(python|javascript|java|cpp|html|css|sql|rust|golang)\b', text):
        return True
        
    return False

def get_project_context() -> str:
    """Gathers context from the current project files for better code generation."""
    context_parts = []
    # Only read small/important files to keep token usage low
    important_files = ["main.py", "requirements.txt", "readme.md"]
    
    for filename in important_files:
        file_path = BASE_DIR / filename
        if file_path.exists():
            try:
                # Read first 100 lines to avoid massive context
                content = ""
                with open(file_path, "r", encoding="utf-8") as f:
                    content = "".join([next(f) for _ in range(100)])
                context_parts.append(f"--- File: {filename} ---\n{content}\n")
            except Exception:
                pass
                
    return "\n".join(context_parts)

def handle_coding_task(prompt: str, project_context: str = None) -> str:
    """Routes the coding task to Groq API and handles file saving/opening."""
    api_key = get_groq_api_key()
    if not api_key:
        return "Error: Groq API key missing. Please add it to config/api_keys.json."

    try:
        client = Groq(api_key=api_key)
        
        if not project_context:
            project_context = get_project_context()
            
        system_prompt = f"""You are an elite software engineer. 
Provide clean, efficient, and production-grade code.
Always use proper formatting and comments. 
Focus on speed and low token usage by being direct.

Current Project Context:
{project_context}

IMPORTANT: Always wrap your code in triple backticks with the language specified, like:
```python
# code here
```
"""

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.2,
        )
        
        response_text = chat_completion.choices[0].message.content
        
        # Extract code blocks
        code_blocks = re.findall(r'```(?:\w+)?\n(.*?)\n```', response_text, re.DOTALL)
        
        if code_blocks:
            # Combine all code blocks or just take the first major one
            main_code = code_blocks[0]
            
            # Determine extension
            ext = ".py"
            if "html" in response_text.lower()[:500]: ext = ".html"
            elif "javascript" in response_text.lower()[:500] or "react" in response_text.lower()[:500]: ext = ".js"
            elif "css" in response_text.lower()[:500]: ext = ".css"
            
            # Save to Desktop
            desktop = Path.home() / "Desktop"
            save_path = desktop / f"jarvis_code{ext}"
            save_path.write_text(main_code, encoding="utf-8")
            
            # Open in VS Code
            import subprocess
            try:
                subprocess.Popen(["code", str(save_path)], shell=True)
                feedback = f"\n\n[System] Code has been saved to Desktop and opened in VS Code."
                return response_text + feedback
            except Exception as e:
                return response_text + f"\n\n[System] Saved to Desktop, but failed to open VS Code: {e}"
        
        return response_text
    except Exception as e:
        return f"Groq Error: {str(e)}"
