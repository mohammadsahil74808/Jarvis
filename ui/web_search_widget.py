"""
JARVIS Floating Web Search Window
===================================
Jab bhi web_search tool call ho, yeh window pop ho jaati hai.
Query dikhata hai, searching animation, phir results.

Integration:
    main.py mein _execute_tool() ke andar web_search block mein
    ek line add karni hai — niche comment mein bataya hai.
"""

import tkinter as tk
import threading
from .floating_widget import (
    FloatingWidget,
    C_BG, C_PRI, C_MID, C_DIM, C_DIMMER,
    C_ACC, C_ACC2, C_TEXT, C_PANEL, C_GREEN, C_RED, C_BORDER
)


class WebSearchWidget(FloatingWidget):
    """
    Floating window for web_search tool.

    Usage (main.py mein, _execute_tool() ke andar):
    -----------------------------------------------
    elif name == "web_search":
        # ← Yeh line add karo:
        widget = WebSearchWidget.launch(self.ui.root, args.get("query",""))
        from actions.web_search import web_search as web_search_action
        r = await loop.run_in_executor(None,
                lambda: web_search_action(parameters=args, player=self.ui))
        result = r or "Done."
        # ← Aur yeh line:
        if widget: self.ui.root.after(0, lambda: widget.show_result(result))
    """

    def __init__(self, parent_root: tk.Tk, query: str):
        self.query = query
        self._dots = 0
        super().__init__(parent_root,
                         title="WEB SEARCH",
                         width=580, height=440)

    # ─────────────────────────────────────────────────────────────────
    # BODY
    # ─────────────────────────────────────────────────────────────────
    def _build_body(self):
        # ── Query display ──────────────────────────────────────────
        q_frame = tk.Frame(self, bg=C_DIM)
        q_frame.pack(fill="x", padx=14, pady=(10, 4))

        tk.Label(q_frame, text="QUERY", fg=C_MID,
                 bg=C_DIM, font=("Courier", 7, "bold")).pack(
            side="left", padx=(8, 4), pady=4)

        self._query_label = tk.Label(
            q_frame,
            text=self.query[:72] + ("…" if len(self.query) > 72 else ""),
            fg=C_ACC2, bg=C_DIM,
            font=("Courier", 9, "bold"),
            anchor="w", wraplength=440)
        self._query_label.pack(side="left", padx=4, pady=4)

        # ── Status bar ─────────────────────────────────────────────
        status_row = tk.Frame(self, bg=C_BG)
        status_row.pack(fill="x", padx=14, pady=(2, 6))

        tk.Label(status_row, text="●", fg=C_PRI,
                 bg=C_BG, font=("Courier", 8)).pack(side="left")

        self._status_label = tk.Label(
            status_row,
            text="Connecting to search engine…",
            fg=C_ACC2, bg=C_BG,
            font=("Courier", 9))
        self._status_label.pack(side="left", padx=6)

        # Separator
        tk.Frame(self, bg=C_BORDER, height=1).pack(fill="x", padx=14)

        # ── Result area ────────────────────────────────────────────
        result_frame = tk.Frame(self, bg=C_PANEL)
        result_frame.pack(fill="both", expand=True, padx=14, pady=10)

        self._result_text = tk.Text(
            result_frame,
            bg=C_PANEL, fg=C_TEXT,
            font=("Courier", 9),
            wrap="word",
            borderwidth=0,
            state="disabled",
            padx=10, pady=8,
            insertbackground=C_TEXT,
            selectbackground=C_DIM)
        self._result_text.pack(side="left", fill="both", expand=True)

        # Scrollbar
        sb = tk.Scrollbar(result_frame, command=self._result_text.yview,
                          bg=C_BG, troughcolor=C_DIMMER,
                          activebackground=C_MID, width=6)
        sb.pack(side="right", fill="y")
        self._result_text.configure(yscrollcommand=sb.set)

        # Tags for coloring
        self._result_text.tag_config("header",  foreground=C_PRI,  font=("Courier", 9, "bold"))
        self._result_text.tag_config("normal",  foreground=C_TEXT, font=("Courier", 9))
        self._result_text.tag_config("url",     foreground=C_ACC,  font=("Courier", 8))
        self._result_text.tag_config("success", foreground=C_GREEN,font=("Courier", 9, "bold"))
        self._result_text.tag_config("dim",     foreground=C_MID,  font=("Courier", 8))

        # ── Footer ─────────────────────────────────────────────────
        tk.Frame(self, bg=C_BORDER, height=1).pack(fill="x", padx=14)
        footer = tk.Frame(self, bg=C_BG, height=28)
        footer.pack(fill="x")
        footer.pack_propagate(False)

        self._footer_label = tk.Label(
            footer,
            text="JARVIS  ›  Search Module  ›  Active",
            fg=C_DIM, bg=C_BG,
            font=("Courier", 7))
        self._footer_label.pack(side="left", padx=14)

        # Start searching animation
        self._animate_search()

    # ─────────────────────────────────────────────────────────────────
    # ANIMATION
    # ─────────────────────────────────────────────────────────────────
    def _animate_search(self):
        """Dot animation while searching."""
        if not hasattr(self, "_searching_done") or not self._searching_done:
            self._dots = (self._dots + 1) % 4
            dot_str = "●" * self._dots + "○" * (3 - self._dots)
            stages = [
                "Sending query to Gemini…",
                "Scanning web sources…",
                "Extracting results…",
                "Processing data…",
            ]
            stage_idx = (self._dots) % len(stages)
            try:
                self._status_label.config(
                    text=f"{dot_str}  {stages[stage_idx]}",
                    fg=C_ACC2)
            except Exception:
                return
            self.after(500, self._animate_search)

    # ─────────────────────────────────────────────────────────────────
    # RESULT DISPLAY
    # ─────────────────────────────────────────────────────────────────
    def show_result(self, result_text: str):
        """
        Call karo jab search complete ho.
        result_text = web_search() ka return value
        """
        self._searching_done = True

        try:
            self._status_label.config(
                text="✓  Search complete",
                fg=C_GREEN)
            self._footer_label.config(
                text="JARVIS  ›  Search Module  ›  Done — Close karne ke liye ✕")
        except Exception:
            return

        # Format and display
        self._result_text.configure(state="normal")
        self._result_text.delete("1.0", tk.END)

        # Split into lines and color them
        lines = result_text.strip().split("\n")
        for line in lines:
            stripped = line.strip()
            if not stripped:
                self._result_text.insert(tk.END, "\n")
                continue
            if stripped.startswith("###") or stripped.startswith("**"):
                clean = stripped.replace("###", "").replace("**", "").strip()
                self._result_text.insert(tk.END, clean + "\n", "header")
            elif stripped.startswith("http"):
                self._result_text.insert(tk.END, stripped + "\n", "url")
            elif stripped.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.")):
                self._result_text.insert(tk.END, stripped + "\n", "header")
            elif stripped.startswith("•") or stripped.startswith("-"):
                self._result_text.insert(tk.END, stripped + "\n", "normal")
            else:
                self._result_text.insert(tk.END, stripped + "\n", "normal")

        self._result_text.configure(state="disabled")
        self._result_text.see("1.0")

        # Auto-close after 30 seconds
        self.after(30_000, self.close)

    # ─────────────────────────────────────────────────────────────────
    # STATIC LAUNCHER  (thread-safe)
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def launch(root: tk.Tk, query: str) -> "WebSearchWidget":
        """
        Thread-safe launcher.
        main.py se call karo: widget = WebSearchWidget.launch(self.ui.root, query)
        """
        result = [None]

        def _create():
            result[0] = WebSearchWidget(root, query)

        root.after(0, _create)
        # Wait briefly for creation
        import time
        time.sleep(0.12)
        return result[0]
