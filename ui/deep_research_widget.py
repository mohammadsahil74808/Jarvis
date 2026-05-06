"""
JARVIS Floating Deep Research Window
======================================
Deep research ke liye — multiple sources, live progress,
article extraction — sab ek khoobsurat floating window mein.

Integration:
    main.py mein research_mode tool block mein use karo.
    Niche comment mein exact code hai.
"""

import tkinter as tk
import threading
import time
from .floating_widget import (
    FloatingWidget,
    C_BG, C_PRI, C_MID, C_DIM, C_DIMMER,
    C_ACC, C_ACC2, C_TEXT, C_PANEL, C_GREEN, C_RED, C_BORDER
)


class DeepResearchWidget(FloatingWidget):
    """
    Floating window for research_mode tool.

    Usage (main.py mein, _execute_tool() ke andar):
    -----------------------------------------------
    if name == "research_mode":
        # ← Yeh line add karo:
        widget = DeepResearchWidget.launch(self.ui.root, args.get("query",""))
        from actions.research_mode import research_mode
        r = await loop.run_in_executor(
            None, lambda: research_mode(args, _widget_ref=widget))
        result = r or "Done."
        # widget khud hi show_done() call karega jab research_mode finish ho
    """

    def __init__(self, parent_root: tk.Tk, query: str):
        self.query   = query
        self._tick   = 0
        self._phase  = 0
        self._phases = [
            ("INIT",     "Initializing research engine…",   C_ACC2),
            ("SEARCH",   "Searching across the web…",       C_PRI),
            ("EXTRACT",  "Extracting article content…",     C_ACC),
            ("ANALYZE",  "Analyzing and synthesizing…",     C_ACC2),
            ("FINALIZE", "Compiling final report…",         C_GREEN),
        ]
        self._phase_steps = []  # completed phases shown in tracker
        super().__init__(parent_root,
                         title="DEEP RESEARCH",
                         width=620, height=500)

    # ─────────────────────────────────────────────────────────────────
    # BODY
    # ─────────────────────────────────────────────────────────────────
    def _build_body(self):
        # ── Query ──────────────────────────────────────────────────
        q_frame = tk.Frame(self, bg=C_DIM)
        q_frame.pack(fill="x", padx=14, pady=(10, 4))

        tk.Label(q_frame, text="RESEARCH TOPIC",
                 fg=C_MID, bg=C_DIM,
                 font=("Courier", 7, "bold")).pack(
            side="left", padx=(8, 4), pady=5)

        self._query_label = tk.Label(
            q_frame,
            text=self.query[:68] + ("…" if len(self.query) > 68 else ""),
            fg=C_ACC2, bg=C_DIM,
            font=("Courier", 9, "bold"),
            anchor="w")
        self._query_label.pack(side="left", padx=4, pady=5)

        # ── Phase tracker (left column) + Result (right) ───────────
        body = tk.Frame(self, bg=C_BG)
        body.pack(fill="both", expand=True, padx=14, pady=(4, 4))

        # Left: phase steps
        left = tk.Frame(body, bg=C_DIMMER, width=160)
        left.pack(side="left", fill="y", padx=(0, 8))
        left.pack_propagate(False)

        tk.Label(left, text="PIPELINE",
                 fg=C_MID, bg=C_DIMMER,
                 font=("Courier", 7, "bold")).pack(pady=(10, 4))

        self._phase_frame = tk.Frame(left, bg=C_DIMMER)
        self._phase_frame.pack(fill="x", padx=6)

        # Right: result area
        right = tk.Frame(body, bg=C_BG)
        right.pack(side="left", fill="both", expand=True)

        # Status bar
        status_row = tk.Frame(right, bg=C_BG)
        status_row.pack(fill="x", pady=(0, 4))

        self._dot_label = tk.Label(status_row, text="●",
                                   fg=C_PRI, bg=C_BG,
                                   font=("Courier", 8))
        self._dot_label.pack(side="left")

        self._status_label = tk.Label(
            status_row,
            text="Starting deep research…",
            fg=C_ACC2, bg=C_BG,
            font=("Courier", 9))
        self._status_label.pack(side="left", padx=6)

        # Source counter
        self._src_label = tk.Label(
            status_row, text="",
            fg=C_MID, bg=C_BG,
            font=("Courier", 8))
        self._src_label.pack(side="right", padx=4)

        tk.Frame(right, bg=C_BORDER, height=1).pack(fill="x", pady=(0, 4))

        # Result text
        txt_frame = tk.Frame(right, bg=C_PANEL)
        txt_frame.pack(fill="both", expand=True)

        self._result_text = tk.Text(
            txt_frame,
            bg=C_PANEL, fg=C_TEXT,
            font=("Courier", 9),
            wrap="word", borderwidth=0,
            state="disabled",
            padx=8, pady=6,
            insertbackground=C_TEXT,
            selectbackground=C_DIM)
        self._result_text.pack(side="left", fill="both", expand=True)

        sb = tk.Scrollbar(txt_frame, command=self._result_text.yview,
                          bg=C_BG, troughcolor=C_DIMMER,
                          activebackground=C_MID, width=6)
        sb.pack(side="right", fill="y")
        self._result_text.configure(yscrollcommand=sb.set)

        # Text tags
        self._result_text.tag_config("h1",      foreground=C_PRI,  font=("Courier", 10, "bold"))
        self._result_text.tag_config("h2",      foreground=C_ACC2, font=("Courier", 9,  "bold"))
        self._result_text.tag_config("normal",  foreground=C_TEXT, font=("Courier", 9))
        self._result_text.tag_config("url",     foreground=C_ACC,  font=("Courier", 8))
        self._result_text.tag_config("success", foreground=C_GREEN,font=("Courier", 9,  "bold"))
        self._result_text.tag_config("dim",     foreground=C_MID,  font=("Courier", 8))
        self._result_text.tag_config("bullet",  foreground=C_TEXT, font=("Courier", 9),
                                     lmargin1=12, lmargin2=20)

        # ── Footer ─────────────────────────────────────────────────
        tk.Frame(self, bg=C_BORDER, height=1).pack(fill="x", padx=14)
        footer = tk.Frame(self, bg=C_BG, height=26)
        footer.pack(fill="x")
        footer.pack_propagate(False)

        self._footer_label = tk.Label(
            footer,
            text="JARVIS  ›  Research Engine  ›  Running",
            fg=C_DIM, bg=C_BG,
            font=("Courier", 7))
        self._footer_label.pack(side="left", padx=14)

        self._time_label = tk.Label(
            footer, text="",
            fg=C_DIM, bg=C_BG,
            font=("Courier", 7))
        self._time_label.pack(side="right", padx=14)

        self._start_time = time.time()
        self._animate()

    # ─────────────────────────────────────────────────────────────────
    # ANIMATION
    # ─────────────────────────────────────────────────────────────────
    def _animate(self):
        """Pulse the status dot."""
        if hasattr(self, "_research_done") and self._research_done:
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

    # ─────────────────────────────────────────────────────────────────
    # PROGRESS UPDATES  (research_mode.py se call karo)
    # ─────────────────────────────────────────────────────────────────
    def update_phase(self, phase_name: str, status_text: str = "",
                     sources_found: int = 0):
        """
        Call from research_mode.py to update progress.
        phase_name = "SEARCH" | "EXTRACT" | "ANALYZE" | "FINALIZE"
        """
        try:
            # Update status label
            if status_text:
                self._status_label.config(text=status_text)

            # Update source counter
            if sources_found > 0:
                self._src_label.config(
                    text=f"Sources: {sources_found}")

            # Add to pipeline tracker
            self._phase_steps.append(phase_name)
            self._refresh_pipeline()
        except Exception:
            pass

    def _refresh_pipeline(self):
        """Redraw the left-side pipeline steps."""
        try:
            for w in self._phase_frame.winfo_children():
                w.destroy()

            all_phases = ["SEARCH", "EXTRACT", "ANALYZE", "FINALIZE"]
            for ph in all_phases:
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

    def stream_chunk(self, text: str):
        """
        Streaming: call karo har chunk ke saath as research progresses.
        text = partial result text
        """
        try:
            self._result_text.configure(state="normal")
            self._result_text.delete("1.0", tk.END)
            lines = text.strip().split("\n")
            for line in lines:
                self._append_formatted_line(line)
            self._result_text.configure(state="disabled")
            self._result_text.see(tk.END)
        except Exception:
            pass

    def _append_formatted_line(self, line: str):
        stripped = line.strip()
        if not stripped:
            self._result_text.insert(tk.END, "\n")
            return
        if stripped.startswith("### "):
            self._result_text.insert(tk.END, stripped[4:] + "\n", "h1")
        elif stripped.startswith("## "):
            self._result_text.insert(tk.END, stripped[3:] + "\n", "h2")
        elif stripped.startswith("**") and stripped.endswith("**"):
            self._result_text.insert(tk.END, stripped.replace("**","") + "\n", "h2")
        elif stripped.startswith("http"):
            self._result_text.insert(tk.END, stripped + "\n", "url")
        elif stripped.startswith(("- ", "• ", "* ")):
            self._result_text.insert(tk.END, stripped + "\n", "bullet")
        else:
            self._result_text.insert(tk.END, stripped + "\n", "normal")

    def show_done(self, final_text: str = ""):
        """
        Call karo jab research complete ho jaaye.
        """
        self._research_done = True
        try:
            self._status_label.config(
                text="✓  Research complete",
                fg=C_GREEN)
            self._footer_label.config(
                text="JARVIS  ›  Research Engine  ›  Done — ✕ close")
            elapsed = int(time.time() - self._start_time)
            self._time_label.config(
                text=f"Completed in {elapsed}s", fg=C_GREEN)
        except Exception:
            pass

        if final_text:
            self.stream_chunk(final_text)

        # Mark all phases done
        self._phase_steps = ["SEARCH", "EXTRACT", "ANALYZE", "FINALIZE"]
        self._refresh_pipeline()

        # Auto close after 60s
        self.after(60_000, self.close)

    # ─────────────────────────────────────────────────────────────────
    # STATIC LAUNCHER
    # ─────────────────────────────────────────────────────────────────
    @staticmethod
    def launch(root: tk.Tk, query: str) -> "DeepResearchWidget":
        """Thread-safe launcher."""
        result = [None]

        def _create():
            result[0] = DeepResearchWidget(root, query)

        root.after(0, _create)
        time.sleep(0.12)
        return result[0]
