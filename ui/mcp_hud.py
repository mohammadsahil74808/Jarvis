# ui/mcp_hud.py
import json
import math
import time
import tkinter as tk
from tkinter import font as tkfont

class MCPResultRenderer:
    """Converts raw string and JSON tool outputs into structured, human-readable formatting."""
    
    @classmethod
    def format_output(cls, tool_name: str, raw_output: str) -> str:
        if not raw_output or raw_output.strip() == "":
            return "Operation completed successfully (No output returned)."
        
        # Check if the output contains untrusted data wrapping
        if "<untrusted_data>" in raw_output and "</untrusted_data>" in raw_output:
            try:
                parts = raw_output.split("<untrusted_data>")
                content = parts[1].split("</untrusted_data>")[0].strip()
                raw_output = content
            except Exception:
                pass

        # Try parsing as JSON
        data = None
        try:
            data = json.loads(raw_output)
        except Exception:
            # Not strict JSON, return clean text
            return raw_output.strip()

        # Handle specific tool formats or general JSON structures
        name_lower = tool_name.lower()
        if "repository" in name_lower or "repo" in name_lower or "search" in name_lower:
            formatted = cls._format_repositories(data)
            if formatted:
                return formatted
                
        if "issue" in name_lower or "pull" in name_lower or "pr" in name_lower:
            formatted = cls._format_issues_prs(data)
            if formatted:
                return formatted
                
        if "commit" in name_lower or "log" in name_lower:
            formatted = cls._format_commits(data)
            if formatted:
                return formatted
                
        if "file" in name_lower or "dir" in name_lower or "path" in name_lower or "list" in name_lower:
            formatted = cls._format_filesystem(data)
            if formatted:
                return formatted

        # Fallback generic JSON human-readable formatter (NO RAW JSON DUMP)
        return cls._format_generic_json(data)

    @classmethod
    def _format_repositories(cls, data):
        items = None
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "full_name" in data[0]:
            items = data
            
        if items is None:
            return None
            
        if len(items) == 0:
            return "No matching GitHub repositories found."
            
        lines = ["[GITHUB REPOSITORIES]", "=" * 50]
        for item in items[:15]:  # Cap at 15 for readable display
            name = item.get("full_name") or item.get("name", "Unknown Repo")
            stars = item.get("stargazers_count", 0)
            lang = item.get("language") or "N/A"
            desc = item.get("description") or "No description provided."
            url = item.get("html_url") or item.get("url", "")
            
            lines.append(f"[REPO]  {name}  [ Stars: {stars} | Lang: {lang} ]")
            lines.append(f"        {desc}")
            if url:
                lines.append(f"        [URL] {url}")
            lines.append("-" * 50)
            
        if len(items) > 15:
            lines.append(f"        ...and {len(items) - 15} more repositories.")
        return "\n".join(lines)

    @classmethod
    def _format_issues_prs(cls, data):
        items = None
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and ("title" in data[0] or "number" in data[0]):
            items = data
            
        if items is None:
            return None
            
        if len(items) == 0:
            return "No issues or pull requests found."
            
        lines = ["[ISSUES & PULL REQUESTS]", "=" * 50]
        for item in items[:15]:
            number = item.get("number", "?")
            title = item.get("title", "Untitled")
            state = item.get("state", "open").upper()
            user = item.get("user", {}).get("login", "Unknown author")
            url = item.get("html_url") or ""
            
            lines.append(f"[ITEM]  #{number} [{state}] {title}")
            lines.append(f"        Author: {user}")
            if url:
                lines.append(f"        [URL] {url}")
            lines.append("-" * 50)
            
        if len(items) > 15:
            lines.append(f"        ...and {len(items) - 15} more items.")
        return "\n".join(lines)

    @classmethod
    def _format_commits(cls, data):
        items = None
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
        elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict) and "sha" in data[0]:
            items = data
            
        if items is None:
            return None
            
        if len(items) == 0:
            return "No commits found in history."
            
        lines = ["[COMMIT HISTORY]", "=" * 50]
        for item in items[:15]:
            sha = str(item.get("sha", "000000"))[:7]
            commit_obj = item.get("commit", {})
            msg = commit_obj.get("message", "").split("\n")[0] if isinstance(commit_obj, dict) else str(commit_obj)
            author = item.get("author", {}).get("login") if isinstance(item.get("author"), dict) else "Unknown"
            if author == "Unknown" and isinstance(commit_obj, dict):
                author = commit_obj.get("author", {}).get("name", "Unknown")
                
            lines.append(f"[COMMIT]  [{sha}] {msg}")
            lines.append(f"          Author: {author}")
            lines.append("-" * 50)
            
        if len(items) > 15:
            lines.append(f"          ...and {len(items) - 15} more commits.")
        return "\n".join(lines)

    @classmethod
    def _format_filesystem(cls, data):
        if isinstance(data, list):
            lines = ["[DIRECTORY / FILE LIST]", "=" * 50]
            for entry in data:
                if isinstance(entry, dict):
                    name = entry.get("name") or entry.get("path") or str(entry)
                    is_dir = entry.get("is_directory", False) or entry.get("type") == "dir"
                    size = entry.get("size_bytes", entry.get("size", ""))
                    icon = "[DIR] " if is_dir else "[FILE]"
                    size_str = f" ({size} B)" if size and not is_dir else ""
                    lines.append(f"  {icon}  {name}{size_str}")
                else:
                    lines.append(f"  [ITEM]  {str(entry)}")
            return "\n".join(lines)
        elif isinstance(data, dict):
            if "entries" in data or "children" in data or "files" in data:
                sub_list = data.get("entries") or data.get("children") or data.get("files")
                if isinstance(sub_list, list):
                    return cls._format_filesystem(sub_list)
        return None

    @classmethod
    def _format_generic_json(cls, data, indent=0) -> str:
        prefix = "  " * indent
        if isinstance(data, dict):
            lines = []
            if indent == 0:
                lines.append("[TOOL RESULT SUMMARY]")
                lines.append("=" * 50)
            for k, v in data.items():
                clean_key = str(k).replace("_", " ").title()
                if isinstance(v, (dict, list)):
                    lines.append(f"{prefix}[>] {clean_key}:")
                    lines.append(cls._format_generic_json(v, indent + 1))
                else:
                    lines.append(f"{prefix}[>] {clean_key}: {v}")
            return "\n".join(lines)
        elif isinstance(data, list):
            lines = []
            for i, item in enumerate(data):
                if isinstance(item, (dict, list)):
                    lines.append(f"{prefix}[+] Item #{i+1}:")
                    lines.append(cls._format_generic_json(item, indent + 1))
                else:
                    lines.append(f"{prefix}[-] {item}")
            return "\n".join(lines)
        else:
            return f"{prefix}{str(data)}"


class MCPResultHUD:
    """Centered, smooth floating terminal HUD for displaying MCP tool execution results."""
    
    def __init__(self, parent_tk):
        self.parent = parent_tk
        self.window = None
        self.persona = "jarvis"
        self.is_visible = False
        self.current_alpha = 0.0
        self.target_alpha = 0.0
        self.loading_angle = 0.0
        self.is_loading = False
        self._anim_timer = None
        self._auto_close_timer = None
        self._drag_data = {"x": 0, "y": 0}
        
        # Color schemes matching JARVIS & FRIDAY personas
        self.themes = {
            "jarvis": {
                "bg": "#000a12",
                "border": "#0088ff",
                "accent": "#00ffff",
                "text": "#ffffff",
                "subtext": "#88cde5",
                "header_bg": "#001a2e",
                "err": "#ff3366"
            },
            "friday": {
                "bg": "#120e00",
                "border": "#ff8800",
                "accent": "#ffcc00",
                "text": "#ffffff",
                "subtext": "#e5cf88",
                "header_bg": "#2e2000",
                "err": "#ff3344"
            }
        }
        self.current_colors = self.themes["jarvis"]

    def set_theme(self, persona: str):
        persona = persona.lower()
        if persona in self.themes:
            self.persona = persona
            self.current_colors = self.themes[persona]
            if self.window and self.window.winfo_exists():
                self._apply_theme()

    def _apply_theme(self):
        c = self.current_colors
        self.window.configure(bg=c["border"])
        self.main_frame.configure(bg=c["bg"], highlightbackground=c["border"], highlightcolor=c["accent"])
        self.header_frame.configure(bg=c["header_bg"])
        self.title_label.configure(bg=c["header_bg"], fg=c["accent"])
        self.close_btn.configure(bg=c["header_bg"], fg=c["accent"], activebackground=c["border"], activeforeground=c["text"])
        self.content_frame.configure(bg=c["bg"])
        self.loading_canvas.configure(bg=c["bg"])
        self.loading_label.configure(bg=c["bg"], fg=c["subtext"])
        self.text_area.configure(bg=c["bg"], fg=c["text"], insertbackground=c["accent"], selectbackground=c["border"])

    def _ensure_window(self):
        if self.window and self.window.winfo_exists():
            return
            
        self.window = tk.Toplevel(self.parent)
        self.window.title("MCP Result HUD")
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.0)
        
        c = self.current_colors
        self.window.configure(bg=c["border"])
        
        # 1-pixel outer glow/border effect via padding
        self.main_frame = tk.Frame(self.window, bg=c["bg"], bd=1, relief="flat", highlightthickness=1, highlightbackground=c["border"], highlightcolor=c["accent"])
        self.main_frame.pack(fill="both", expand=True, padx=1, pady=1)
        
        # Header bar
        self.header_frame = tk.Frame(self.main_frame, bg=c["header_bg"], height=28)
        self.header_frame.pack(fill="x", side="top")
        self.header_frame.pack_propagate(False)
        
        self.title_label = tk.Label(
            self.header_frame, 
            text="◈ MCP PROTOCOL // SYSTEM ONLINE", 
            font=("Segoe UI", 9, "bold"), 
            bg=c["header_bg"], 
            fg=c["accent"], 
            anchor="w"
        )
        self.title_label.pack(side="left", padx=10, pady=2)
        
        self.close_btn = tk.Button(
            self.header_frame,
            text="✕",
            bg=c["header_bg"],
            fg=c["accent"],
            bd=0,
            font=("Segoe UI", 10, "bold"),
            activebackground=c["border"],
            activeforeground=c["text"],
            command=self.hide
        )
        self.close_btn.pack(side="right", padx=8, pady=2)
        
        # Content area
        self.content_frame = tk.Frame(self.main_frame, bg=c["bg"])
        self.content_frame.pack(fill="both", expand=True, padx=12, pady=12)
        
        # Loading widgets
        self.loading_canvas = tk.Canvas(self.content_frame, width=120, height=120, bg=c["bg"], highlightthickness=0)
        self.loading_label = tk.Label(self.content_frame, text="Initiating tool execution...", font=("Segoe UI", 11), bg=c["bg"], fg=c["subtext"])
        
        # Result display widgets
        text_font = tkfont.Font(family="Consolas", size=10)
        self.text_area = tk.Text(
            self.content_frame,
            bg=c["bg"],
            fg=c["text"],
            font=text_font,
            wrap="word",
            bd=0,
            highlightthickness=0,
            padx=5,
            pady=5
        )
        self.scrollbar = tk.Scrollbar(self.content_frame, orient="vertical", command=self.text_area.yview)
        self.text_area.configure(yscrollcommand=self.scrollbar.set)
        
        # Event binding for dragging and closing
        self.header_frame.bind("<ButtonPress-1>", self._on_drag_start)
        self.header_frame.bind("<B1-Motion>", self._on_drag_motion)
        self.title_label.bind("<ButtonPress-1>", self._on_drag_start)
        self.title_label.bind("<B1-Motion>", self._on_drag_motion)
        self.window.bind("<Escape>", lambda e: self.hide())
        
        self._center_on_screen(640, 420)

    def _center_on_screen(self, width=640, height=420):
        sw = self.parent.winfo_screenwidth()
        sh = self.parent.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2 - 40  # Slightly above exact center for visual balance
        self.window.geometry(f"{width}x{height}+{x}+{y}")

    def _on_drag_start(self, event):
        self._drag_data["x"] = event.x_root - self.window.winfo_x()
        self._drag_data["y"] = event.y_root - self.window.winfo_y()

    def _on_drag_motion(self, event):
        x = event.x_root - self._drag_data["x"]
        y = event.y_root - self._drag_data["y"]
        self.window.geometry(f"+{x}+{y}")

    def _start_fade_loop(self):
        if self._anim_timer:
            return
        self._anim_timer = self.parent.after(20, self._step_fade)

    def _step_fade(self):
        if not self.window or not self.window.winfo_exists():
            self._anim_timer = None
            return

        diff = self.target_alpha - self.current_alpha
        if abs(diff) > 0.03:
            self.current_alpha += math.copysign(0.05, diff)
            try:
                self.window.attributes("-alpha", max(0.0, min(1.0, self.current_alpha)))
            except Exception:
                pass
            self._anim_timer = self.parent.after(20, self._step_fade)
        else:
            self.current_alpha = self.target_alpha
            try:
                self.window.attributes("-alpha", self.current_alpha)
            except Exception:
                pass
            self._anim_timer = None
            if self.current_alpha <= 0.01:
                self.window.withdraw()
                self.is_visible = False

    def _start_loading_anim(self):
        if not self.is_loading or not self.window or not self.window.winfo_exists():
            return
        self.loading_angle = (self.loading_angle + 12) % 360
        self._draw_loading_spinner()
        self.parent.after(30, self._start_loading_anim)

    def _draw_loading_spinner(self):
        c = self.loading_canvas
        c.delete("all")
        cx, cy = 60, 60
        r1 = 35
        r2 = 45
        accent = self.current_colors["accent"]
        subtext = self.current_colors["subtext"]
        
        # Draw sci-fi style concentric arcs
        c.create_arc(cx-r2, cy-r2, cx+r2, cy+r2, start=self.loading_angle, extent=120, outline=accent, width=3, style="arc")
        c.create_arc(cx-r2, cy-r2, cx+r2, cy+r2, start=(self.loading_angle + 180) % 360, extent=80, outline=subtext, width=2, style="arc")
        c.create_arc(cx-r1, cy-r1, cx+r1, cy+r1, start=(-self.loading_angle * 1.5) % 360, extent=200, outline=accent, width=2, style="arc")
        c.create_oval(cx-6, cy-6, cx+6, cy+6, fill=accent, outline="")

    def show_loading(self, tool_name: str, arguments: dict):
        """Show HUD with an animated sci-fi loading indicator while tool executes."""
        self._cancel_auto_close()
        self._ensure_window()
        self.window.deiconify()
        self.is_visible = True
        
        self.title_label.config(text=f"◈ MCP PROTOCOL // EXECUTING: {tool_name.upper()}")
        self.loading_label.config(text=f"Running operation on target tool '{tool_name}'...")
        
        # Hide result area, show loading area
        self.text_area.pack_forget()
        self.scrollbar.pack_forget()
        self.loading_canvas.pack(pady=(60, 15))
        self.loading_label.pack()
        
        self.is_loading = True
        self.target_alpha = 0.95
        self._start_fade_loop()
        self.parent.after(10, self._start_loading_anim)

    def show_result(self, tool_name: str, result_text: str):
        """Replace loading animation with clean human-readable result presentation."""
        self._cancel_auto_close()
        self.is_loading = False
        self._ensure_window()
        self.window.deiconify()
        self.is_visible = True
        
        self.title_label.config(text=f"◈ MCP PROTOCOL // RESULT: {tool_name.upper()}")
        
        # Hide loading widgets
        self.loading_canvas.pack_forget()
        self.loading_label.pack_forget()
        
        # Show text area
        self.scrollbar.pack(side="right", fill="y")
        self.text_area.pack(side="left", fill="both", expand=True)
        
        formatted_content = MCPResultRenderer.format_output(tool_name, result_text)
        
        self.text_area.config(state="normal", fg=self.current_colors["text"])
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", formatted_content)
        self.text_area.config(state="disabled")
        
        self.target_alpha = 0.95
        self._start_fade_loop()
        
        # Set auto-close after 20 seconds of display
        self._auto_close_timer = self.parent.after(20000, self.hide)

    def show_error(self, tool_name: str, error_text: str):
        """Show tool failure or error message cleanly in the HUD."""
        self._cancel_auto_close()
        self.is_loading = False
        self._ensure_window()
        self.window.deiconify()
        self.is_visible = True
        
        self.title_label.config(text=f"◈ MCP PROTOCOL // ERROR: {tool_name.upper()}")
        
        self.loading_canvas.pack_forget()
        self.loading_label.pack_forget()
        
        self.scrollbar.pack(side="right", fill="y")
        self.text_area.pack(side="left", fill="both", expand=True)
        
        self.text_area.config(state="normal", fg=self.current_colors["err"])
        self.text_area.delete("1.0", tk.END)
        self.text_area.insert("1.0", f"⚠️ TOOL EXECUTION FAILED\n{'='*50}\nTool: {tool_name}\n\nDetails:\n{error_text}")
        self.text_area.config(state="disabled")
        
        self.target_alpha = 0.95
        self._start_fade_loop()
        self._auto_close_timer = self.parent.after(20000, self.hide)

    def hide(self):
        """Smoothly fade out and dismiss the HUD."""
        self._cancel_auto_close()
        self.is_loading = False
        self.target_alpha = 0.0
        self._start_fade_loop()

    def _cancel_auto_close(self):
        if self._auto_close_timer:
            try:
                self.parent.after_cancel(self._auto_close_timer)
            except Exception:
                pass
            self._auto_close_timer = None
