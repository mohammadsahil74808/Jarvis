"""
JARVIS Floating Widget — Base Class
====================================
Tera JARVIS ka color theme use karta hai.
Har floating window (Search, DeepResearch, FileSearch) isi se inherit karega.

Usage:
    from ui.floating_widget import FloatingWidget
"""

import tkinter as tk
import threading
import time
from ctypes import windll

# ── JARVIS Color Theme (teri ui.py se match) ──────────────────────────────
C_BG     = "#000000"
C_PRI    = "#00d4ff"
C_MID    = "#007a99"
C_DIM    = "#003344"
C_DIMMER = "#001520"
C_ACC    = "#ff6600"
C_ACC2   = "#ffcc00"
C_TEXT   = "#8ffcff"
C_PANEL  = "#010c10"
C_GREEN  = "#00ff88"
C_RED    = "#ff3333"
C_BORDER = "#003d55"


def _apply_rounded(win, w, h, r=18):
    """Win32 rounded corners."""
    try:
        win.update_idletasks()
        hwnd = win.winfo_id()
        region = windll.gdi32.CreateRoundRectRgn(0, 0, w, h, r, r)
        windll.user32.SetWindowRgn(hwnd, region, True)
    except Exception:
        pass


class FloatingWidget(tk.Toplevel):
    """
    Base floating window class.

    Parameters
    ----------
    parent_root : tk.Tk  — main JARVIS window
    title       : str    — header bar mein dikhne wala title
    width       : int    — window width  (default 540)
    height      : int    — window height (default 420)
    """

    def __init__(self, parent_root: tk.Tk, title: str,
                 width: int = 540, height: int = 420):
        super().__init__(parent_root)

        self.W = width
        self.H = height
        self._title_str = title

        # ── Window position: screen center ────────────────────────────
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - width)  // 2
        y  = (sh - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")
        self.overrideredirect(True)          # no OS titlebar
        self.attributes("-alpha", 0.0)       # start invisible (fade-in)
        self.attributes("-topmost", True)    # always on top
        self.configure(bg=C_BG)
        self.resizable(False, False)

        _apply_rounded(self, width, height, r=18)

        # ── Drag support ───────────────────────────────────────────────
        self._drag_x = 0
        self._drag_y = 0

        # ── Build layout ───────────────────────────────────────────────
        self._build_header()
        self._build_body()

        # ── Fade in ────────────────────────────────────────────────────
        self._fade_in()

    # ─────────────────────────────────────────────────────────────────
    # HEADER  (title bar + close button)
    # ─────────────────────────────────────────────────────────────────
    def _build_header(self):
        self.header = tk.Frame(self, bg=C_DIMMER, height=38)
        self.header.pack(fill="x", side="top")
        self.header.pack_propagate(False)

        # JARVIS logo dot
        dot = tk.Label(self.header, text="●", fg=C_PRI,
                       bg=C_DIMMER, font=("Courier", 9))
        dot.pack(side="left", padx=(10, 4))

        # Title
        lbl = tk.Label(self.header,
                       text=f"J.A.R.V.I.S  ›  {self._title_str}",
                       fg=C_TEXT, bg=C_DIMMER,
                       font=("Courier", 9, "bold"))
        lbl.pack(side="left")

        # Close button
        close_btn = tk.Label(self.header, text="✕", fg=C_MID,
                             bg=C_DIMMER, font=("Courier", 10),
                             cursor="hand2")
        close_btn.pack(side="right", padx=10)
        close_btn.bind("<Button-1>", lambda e: self.close())
        close_btn.bind("<Enter>",    lambda e: close_btn.config(fg=C_RED))
        close_btn.bind("<Leave>",    lambda e: close_btn.config(fg=C_MID))

        # Drag bindings on header
        for w in (self.header, lbl, dot):
            w.bind("<ButtonPress-1>",   self._on_drag_start)
            w.bind("<B1-Motion>",       self._on_drag_move)

        # Separator line
        sep = tk.Frame(self, bg=C_BORDER, height=1)
        sep.pack(fill="x")

    # ─────────────────────────────────────────────────────────────────
    # BODY  (subclasses override this)
    # ─────────────────────────────────────────────────────────────────
    def _build_body(self):
        """Override in subclass to add content."""
        pass

    # ─────────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────────
    def _on_drag_start(self, event):
        self._drag_x = event.x_root - self.winfo_x()
        self._drag_y = event.y_root - self.winfo_y()

    def _on_drag_move(self, event):
        nx = event.x_root - self._drag_x
        ny = event.y_root - self._drag_y
        self.geometry(f"+{nx}+{ny}")

    def _fade_in(self, alpha=0.0):
        if alpha <= 0.95:
            self.attributes("-alpha", alpha)
            self.after(18, self._fade_in, alpha + 0.07)
        else:
            self.attributes("-alpha", 0.95)

    def close(self):
        """Fade out then destroy."""
        def _fade_out(alpha=0.95):
            if alpha > 0.0:
                try:
                    self.attributes("-alpha", alpha)
                    self.after(18, _fade_out, alpha - 0.08)
                except Exception:
                    pass
            else:
                try:
                    self.destroy()
                except Exception:
                    pass
        _fade_out()

    def set_status(self, text: str, color: str = C_ACC2):
        """Update status label (if exists in subclass)."""
        if hasattr(self, "_status_label"):
            self._status_label.config(text=text, fg=color)

    def append_result(self, text: str, tag: str = "normal"):
        """Append text to result area (if exists in subclass)."""
        if hasattr(self, "_result_text"):
            self._result_text.configure(state="normal")
            self._result_text.insert(tk.END, text + "\n", tag)
            self._result_text.see(tk.END)
            self._result_text.configure(state="disabled")
