"""
JARVIS Floating File Search Window
=====================================
Jab bhi file_manager search/find/deep_search action ho,
yeh window pop karti hai — live results dikhata hai.

Integration:
    main.py mein file_manager tool block mein use karo.
    Niche comment mein exact code diya hua hai.
"""

import tkinter as tk
import threading
import time
import os
from pathlib import Path
from .floating_widget import (
    FloatingWidget,
    C_BG, C_PRI, C_MID, C_DIM, C_DIMMER,
    C_ACC, C_ACC2, C_TEXT, C_PANEL, C_GREEN, C_RED, C_BORDER
)

# File type → icon mapping
_EXT_ICONS = {
    ".py":    ("🐍", "#3572A5"),
    ".js":    ("JS", "#f7df1e"),
    ".ts":    ("TS", "#007ACC"),
    ".html":  ("◇",  "#e34c26"),
    ".css":   ("◈",  "#264de4"),
    ".json":  ("{}",  C_ACC2),
    ".txt":   ("T",   C_TEXT),
    ".pdf":   ("P",   "#FF0000"),
    ".docx":  ("W",  "#2B579A"),
    ".xlsx":  ("X",  "#217346"),
    ".png":   ("▣",   "#9B59B6"),
    ".jpg":   ("▣",   "#9B59B6"),
    ".jpeg":  ("▣",   "#9B59B6"),
    ".mp4":   ("▶",   "#E74C3C"),
    ".mp3":   ("♪",   "#1DB954"),
    ".zip":   ("◉",   C_ACC),
    ".exe":   ("⚙",   C_MID),
    ".md":    ("#",   C_PRI),
}
_DEFAULT_ICON = ("■", C_DIM)


class FileSearchWidget(FloatingWidget):
    """
    Floating window for file_manager find / search / deep_search.

    Usage (main.py mein, _execute_tool() ke andar):
    -----------------------------------------------
    elif name == "file_manager":
        action = args.get("action", "")
        widget = None

        # ← Yeh block add karo:
        if action in ("find", "search", "deep_search"):
            query = args.get("query") or args.get("name") or ""
            widget = FileSearchWidget.launch(self.ui.root, query, action)

        from actions.file_manager import file_manager
        r = await loop.run_in_executor(
            None, lambda: file_manager(parameters=args, player=self.ui))
        result = r or "Done."

        # ← Aur yeh block:
        if widget:
            self.ui.root.after(0, lambda res=result: widget.show_results(res))
    """

    def __init__(self, parent_root: tk.Tk, query: str, action: str = "search"):
        self.query    = query
        self.action   = action.upper()
        self._tick    = 0
        self._found   = 0
        super().__init__(parent_root,
                         title=f"FILE {self.action}",
                         width=580, height=460)

    # ─────────────────────────────────────────────────────────────────
    # BODY
    # ─────────────────────────────────────────────────────────────────
    def _build_body(self):
        # ── Search bar ─────────────────────────────────────────────
        bar = tk.Frame(self, bg=C_DIM)
        bar.pack(fill="x", padx=14, pady=(10, 4))

        tk.Label(bar, text="SCANNING FOR",
                 fg=C_MID, bg=C_DIM,
                 font=("Courier", 7, "bold")).pack(
            side="left", padx=(8, 4), pady=5)

        tk.Label(bar,
                 text=self.query[:60] + ("…" if len(self.query) > 60 else ""),
                 fg=C_ACC2, bg=C_DIM,
                 font=("Courier", 9, "bold")).pack(
            side="left", padx=4, pady=5)

        # ── Status row ─────────────────────────────────────────────
        sr = tk.Frame(self, bg=C_BG)
        sr.pack(fill="x", padx=14, pady=(2, 4))

        self._dot_label = tk.Label(sr, text="●",
                                   fg=C_PRI, bg=C_BG,
                                   font=("Courier", 8))
        self._dot_label.pack(side="left")

        self._status_label = tk.Label(
            sr, text="Initializing file scanner…",
            fg=C_ACC2, bg=C_BG, font=("Courier", 9))
        self._status_label.pack(side="left", padx=6)

        self._count_label = tk.Label(
            sr, text="",
            fg=C_GREEN, bg=C_BG, font=("Courier", 9, "bold"))
        self._count_label.pack(side="right", padx=6)

        tk.Frame(self, bg=C_BORDER, height=1).pack(fill="x", padx=14)

        # ── File list ──────────────────────────────────────────────
        list_frame = tk.Frame(self, bg=C_PANEL)
        list_frame.pack(fill="both", expand=True, padx=14, pady=6)

        self._listbox = tk.Listbox(
            list_frame,
            bg=C_PANEL, fg=C_TEXT,
            font=("Courier", 9),
            selectbackground=C_DIM,
            selectforeground=C_PRI,
            activestyle="none",
            borderwidth=0,
            highlightthickness=0)
        self._listbox.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(list_frame, command=self._listbox.yview,
                          bg=C_BG, troughcolor=C_DIMMER,
                          activebackground=C_MID, width=6)
        sb.pack(side="right", fill="y")
        self._listbox.configure(yscrollcommand=sb.set)

        # Double-click to open file
        self._listbox.bind("<Double-Button-1>", self._on_open_file)

        # ── Preview / path bar ─────────────────────────────────────
        tk.Frame(self, bg=C_BORDER, height=1).pack(fill="x", padx=14)

        self._path_label = tk.Label(
            self, text="",
            fg=C_MID, bg=C_BG,
            font=("Courier", 7),
            anchor="w")
        self._path_label.pack(fill="x", padx=20, pady=(3, 0))

        # Hover on list item → show path
        self._listbox.bind("<Motion>", self._on_hover)

        # ── Footer ─────────────────────────────────────────────────
        footer = tk.Frame(self, bg=C_BG, height=26)
        footer.pack(fill="x")
        footer.pack_propagate(False)

        self._footer_label = tk.Label(
            footer,
            text="JARVIS  ›  File System  ›  Scanning…",
            fg=C_DIM, bg=C_BG, font=("Courier", 7))
        self._footer_label.pack(side="left", padx=14)

        tk.Label(footer, text="Double-click to open",
                 fg=C_DIM, bg=C_BG, font=("Courier", 7)).pack(
            side="right", padx=14)

        # Store paths separately
        self._file_paths: list[str] = []
        self._start_time = time.time()

        self._animate_scan()

    # ─────────────────────────────────────────────────────────────────
    # ANIMATION
    # ─────────────────────────────────────────────────────────────────
    def _animate_scan(self):
        if hasattr(self, "_scan_done") and self._scan_done:
            return
        self._tick += 1
        scan_texts = [
            "Scanning filesystem…",
            "Checking directories…",
            "Matching patterns…",
            "Indexing results…",
        ]
        colors = [C_PRI, C_ACC2, C_GREEN, C_ACC]
        try:
            self._dot_label.config(
                fg=colors[self._tick % len(colors)])
            self._status_label.config(
                text=scan_texts[self._tick % len(scan_texts)])
        except Exception:
            return
        self.after(450, self._animate_scan)

    # ─────────────────────────────────────────────────────────────────
    # RESULT DISPLAY
    # ─────────────────────────────────────────────────────────────────
    def show_results(self, result_text: str):
        """
        Call karo jab file_manager search complete ho.
        result_text = file_manager() ka return value (string)
        """
        self._scan_done = True
        elapsed = int(time.time() - self._start_time)

        try:
            self._listbox.delete(0, tk.END)
            self._file_paths.clear()
        except Exception:
            return

        # Parse file paths from result text
        lines = result_text.strip().split("\n")
        found = 0

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Detect if it looks like a file path
            is_path = (
                (":\\" in stripped or "/" in stripped or stripped.startswith("\\"))
                and any(c in stripped for c in [".", "\\", "/"])
            )

            if is_path:
                # Extract path (remove leading bullets/numbers)
                path = stripped.lstrip("•-*123456789. ").strip()
                self._add_file_item(path)
                found += 1
            elif stripped and not stripped.startswith("Search") \
                    and not stripped.startswith("["):
                # Show as info line
                try:
                    self._listbox.insert(tk.END, f"   {stripped}")
                    self._listbox.itemconfig(tk.END, fg=C_MID)
                    self._file_paths.append("")
                except Exception:
                    pass

        try:
            self._status_label.config(
                text=f"✓  Scan complete  ({elapsed}s)",
                fg=C_GREEN)
            self._count_label.config(
                text=f"{found} found" if found else "Not found")
            self._footer_label.config(
                text="JARVIS  ›  File System  ›  Done — Double-click to open")
        except Exception:
            pass

        # If nothing useful found, show raw text
        if found == 0 and result_text.strip():
            try:
                self._listbox.delete(0, tk.END)
                for line in lines[:30]:
                    if line.strip():
                        self._listbox.insert(tk.END, f"  {line.strip()}")
                        self._listbox.itemconfig(tk.END, fg=C_TEXT)
                        self._file_paths.append("")
            except Exception:
                pass

        # Auto close after 45s
        self.after(45_000, self.close)

    def _add_file_item(self, path: str):
        """Add a file to the listbox with icon and color."""
        try:
            ext = Path(path).suffix.lower()
            icon, color = _EXT_ICONS.get(ext, _DEFAULT_ICON)
            name = Path(path).name
            parent = str(Path(path).parent)

            # Shorten parent path
            if len(parent) > 35:
                parent = "…" + parent[-33:]

            display = f"  {icon}  {name:<30}  {parent}"
            self._listbox.insert(tk.END, display)
            self._listbox.itemconfig(tk.END, fg=color)
            self._file_paths.append(path)
        except Exception:
            self._listbox.insert(tk.END, f"  ■  {path}")
            self._listbox.itemconfig(tk.END, fg=C_TEXT)
            self._file_paths.append(path)

    # ─────────────────────────────────────────────────────────────────
    # INTERACTIONS
    # ─────────────────────────────────────────────────────────────────
    def _on_open_file(self, event):
        """Double-click → open file in default app."""
        sel = self._listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx < len(self._file_paths) and self._file_paths[idx]:
            path = self._file_paths[idx]
            try:
                os.startfile(path)
            except Exception as e:
                self._status_label.config(
                    text=f"Could not open: {e}", fg=C_RED)

    def _on_hover(self, event):
        """Show full path on hover."""
        try:
            idx = self._listbox.nearest(event.y)
            if 0 <= idx < len(self._file_paths) and self._file_paths[idx]:
                self._path_label.config(text=self._file_paths[idx])
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────────
    # STATIC LAUNCHER
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def launch(root: tk.Tk, query: str,
               action: str = "search") -> "FileSearchWidget":
        """Thread-safe launcher."""
        result = [None]

        def _create():
            result[0] = FileSearchWidget(root, query, action)

        root.after(0, _create)
        time.sleep(0.12)
        return result[0]
