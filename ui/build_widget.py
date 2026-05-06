"""
JARVIS Floating Build Window
=============================
Website aur App Builder ke liye live progress dikhane wali window.
Scaffolding, dependencies, build logs — sab yahan dikhega.
"""

import tkinter as tk
import threading
import time
from .floating_widget import (
    FloatingWidget,
    C_BG, C_PRI, C_MID, C_DIM, C_DIMMER,
    C_ACC, C_ACC2, C_TEXT, C_PANEL, C_GREEN, C_RED, C_BORDER
)

class BuildWidget(FloatingWidget):
    """
    Floating window for website_builder and app_builder tools.
    """

    def __init__(self, parent_root: tk.Tk, build_type: str, name: str):
        self.build_type = build_type # "WEBSITE" | "MOBILE APP"
        self.proj_name  = name
        self._tick      = 0
        self._phase_steps = []
        
        # Default phases for builds
        self.all_phases = ["PLAN", "SCAFFOLD", "INSTALL", "BUILD", "PREVIEW"]
        
        super().__init__(parent_root,
                         title=f"{build_type} BUILDER",
                         width=600, height=480)

    def _build_body(self):
        # ── Project Info ──────────────────────────────────────────
        info_frame = tk.Frame(self, bg=C_DIM)
        info_frame.pack(fill="x", padx=14, pady=(10, 4))

        tk.Label(info_frame, text="PROJECT NAME",
                 fg=C_MID, bg=C_DIM,
                 font=("Courier", 7, "bold")).pack(
            side="left", padx=(8, 4), pady=5)

        self._name_label = tk.Label(
            info_frame,
            text=self.proj_name[:60] + ("..." if len(self.proj_name) > 60 else ""),
            fg=C_ACC2, bg=C_DIM,
            font=("Courier", 9, "bold"),
            anchor="w")
        self._name_label.pack(side="left", padx=4, pady=5)

        # ── Layout: Left (Phases) | Right (Logs) ─────────────────
        body = tk.Frame(self, bg=C_BG)
        body.pack(fill="both", expand=True, padx=14, pady=(4, 4))

        # Left Column: Phases
        left = tk.Frame(body, bg=C_DIMMER, width=150)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        tk.Label(left, text="STEPS",
                 fg=C_MID, bg=C_DIMMER,
                 font=("Courier", 7, "bold")).pack(pady=(10, 4))

        self._phase_frame = tk.Frame(left, bg=C_DIMMER)
        self._phase_frame.pack(fill="x", padx=6)
        self._refresh_pipeline()

        # Right Column: Console Logs
        right = tk.Frame(body, bg=C_BG)
        right.pack(side="left", fill="both", expand=True)

        # Status Bar
        status_row = tk.Frame(right, bg=C_BG)
        status_row.pack(fill="x", pady=(0, 4))

        self._dot_label = tk.Label(status_row, text="●",
                                   fg=C_PRI, bg=C_BG,
                                   font=("Courier", 8))
        self._dot_label.pack(side="left")

        self._status_label = tk.Label(
            status_row,
            text="Initializing build...",
            fg=C_ACC2, bg=C_BG,
            font=("Courier", 9))
        self._status_label.pack(side="left", padx=6)

        tk.Frame(right, bg=C_BORDER, height=1).pack(fill="x", pady=(0, 4))

        # Log Console
        txt_frame = tk.Frame(right, bg=C_PANEL)
        txt_frame.pack(fill="both", expand=True)

        self._log_text = tk.Text(
            txt_frame,
            bg=C_PANEL, fg=C_TEXT,
            font=("Consolas", 8),
            wrap="none", borderwidth=0,
            state="disabled",
            padx=8, pady=6,
            insertbackground=C_TEXT,
            selectbackground=C_DIM)
        self._log_text.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(txt_frame, command=self._log_text.yview,
                          bg=C_BG, troughcolor=C_DIMMER,
                          activebackground=C_MID, width=6)
        sb.pack(side="right", fill="y")
        self._log_text.configure(yscrollcommand=sb.set)

        # Tags
        self._log_text.tag_config("info",  foreground=C_TEXT)
        self._log_text.tag_config("ok",    foreground=C_GREEN)
        self._log_text.tag_config("warn",  foreground=C_ACC2)
        self._log_text.tag_config("err",   foreground=C_RED)
        self._log_text.tag_config("cmd",   foreground=C_PRI)

        # ── Footer ─────────────────────────────────────────────────
        tk.Frame(self, bg=C_BORDER, height=1).pack(fill="x", padx=14)
        footer = tk.Frame(self, bg=C_BG, height=26)
        footer.pack(fill="x")
        footer.pack_propagate(False)

        self._footer_label = tk.Label(
            footer,
            text=f"JARVIS  ›  {self.build_type} Builder  ›  Active",
            fg=C_DIM, bg=C_BG,
            font=("Courier", 7))
        self._footer_label.pack(side="left", padx=14)

        self._time_label = tk.Label(
            footer, text="0s",
            fg=C_DIM, bg=C_BG,
            font=("Courier", 7))
        self._time_label.pack(side="right", padx=14)

        self._start_time = time.time()
        self._animate()

    def _animate(self):
        if hasattr(self, "_build_done") and self._build_done:
            return
        self._tick += 1
        colors = [C_PRI, C_ACC2, C_GREEN, C_ACC]
        try:
            self._dot_label.config(fg=colors[self._tick % len(colors)])
            elapsed = int(time.time() - self._start_time)
            self._time_label.config(text=f"{elapsed}s elapsed")
        except Exception:
            return
        self.after(400, self._animate)

    # ── Public API ──────────────────────────────────────────────────

    def log(self, message: str, level: str = "info"):
        """Append a log line to the console."""
        try:
            self._log_text.configure(state="normal")
            tag = level.lower()
            if tag not in ["info", "ok", "warn", "err", "cmd"]:
                tag = "info"
            
            ts = time.strftime("%H:%M:%S")
            self._log_text.insert(tk.END, f"[{ts}] ", "dim")
            self._log_text.insert(tk.END, message + "\n", tag)
            self._log_text.see(tk.END)
            self._log_text.configure(state="disabled")
            
            # Also update status label with the latest message
            self._status_label.config(text=message[:50] + ("..." if len(message)>50 else ""))
        except Exception:
            pass

    def update_phase(self, phase_name: str):
        """Mark a phase as completed."""
        try:
            if phase_name.upper() not in self._phase_steps:
                self._phase_steps.append(phase_name.upper())
                self._refresh_pipeline()
        except Exception:
            pass

    def _refresh_pipeline(self):
        try:
            for w in self._phase_frame.winfo_children():
                w.destroy()

            for ph in self.all_phases:
                done = ph in self._phase_steps
                color  = C_GREEN if done else C_DIM
                prefix = "✓" if done else "○"
                tk.Label(self._phase_frame,
                         text=f"{prefix} {ph}",
                         fg=color, bg=C_DIMMER,
                         font=("Courier", 8),
                         anchor="w").pack(fill="x", pady=2)
        except Exception:
            pass

    def show_done(self, message: str = "Build Complete"):
        self._build_done = True
        try:
            self._status_label.config(text=f"✓ {message}", fg=C_GREEN)
            self._footer_label.config(text=f"JARVIS  ›  {self.build_type} Builder  ›  Finished")
            self.update_phase("PREVIEW")
            # Auto-close after 2 minutes
            self.after(120_000, self.close)
        except Exception:
            pass

    @staticmethod
    def launch(root: tk.Tk, build_type: str, name: str) -> "BuildWidget":
        from threading import Event
        ready_event = Event()
        result = [None]
        
        def _create():
            try:
                result[0] = BuildWidget(root, build_type, name)
            finally:
                ready_event.set()
                
        root.after(0, _create)
        ready_event.wait(timeout=2.0)
        return result[0]
