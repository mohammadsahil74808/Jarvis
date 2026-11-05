"""
Jarvis First-Time Setup Screen
A 4-step onboarding wizard that launches when api_keys.json is missing or empty.
After completion it writes config/api_keys.json and memory/user_profile.json,
then lets the normal boot sequence continue.
"""
from __future__ import annotations
import json
import math
import os
import random
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox

# ── Paths ──────────────────────────────────────────────────────────────────
_BASE = Path(__file__).resolve().parent.parent
_API_PATH     = _BASE / "config"   / "api_keys.json"
_PROFILE_PATH = _BASE / "memory"   / "user_profile.json"


# ──────────────────────────────────────────────────────────────────────────
# Tiny colour helpers (no external deps)
# ──────────────────────────────────────────────────────────────────────────
def _h2r(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def _r2h(r, g, b) -> str:
    return f"#{int(r):02x}{int(g):02x}{int(b):02x}"

def _blend(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _h2r(c1);  r2, g2, b2 = _h2r(c2)
    return _r2h(r1+(r2-r1)*t, g1+(g2-g1)*t, b1+(b2-b1)*t)

def _dim(c: str, a: float) -> str:
    r, g, b = _h2r(c)
    return _r2h(r*a, g*a, b*a)


# ──────────────────────────────────────────────────────────────────────────
# Persona definitions
# ──────────────────────────────────────────────────────────────────────────
PERSONAS = {
    "J.A.R.V.I.S": {
        "key":       "jarvis",
        "primary":   "#0088ff",
        "secondary": "#00ffff",
        "accent":    "#aa00ff",
        "desc":      "Blue · Cool · Precise",
    },
    "F.R.I.D.A.Y": {
        "key":       "friday",
        "primary":   "#ffaa00",
        "secondary": "#ffcc00",
        "accent":    "#ff8800",
        "desc":      "Gold · Warm · Energetic",
    },
    "E.D.I.T.H": {
        "key":       "edith",
        "primary":   "#00ff88",
        "secondary": "#00ffcc",
        "accent":    "#00cc44",
        "desc":      "Green · Sharp · Strategic",
    },
}

VOICES = {
    "Male (Deep)"   : "en-US-Neural2-J",
    "Female (Soft)" : "en-US-Neural2-F",
    "Neutral"       : "en-US-Neural2-D",
}


# ──────────────────────────────────────────────────────────────────────────
# Reusable styled widgets
# ──────────────────────────────────────────────────────────────────────────
class _StyledEntry(tk.Frame):
    """Single-line entry with a glowing border and label."""

    def __init__(self, parent, label: str, placeholder: str = "",
                 show: str = "", color: str = "#0088ff", **kw):
        super().__init__(parent, bg="#000d14",
                         highlightbackground=_dim(color, 0.35),
                         highlightcolor=color,
                         highlightthickness=1, **kw)
        self._color = color
        self._ph    = placeholder
        self._show  = show
        self._real_show = show

        tk.Label(self, text=label, bg="#000d14", fg=_dim(color, 0.8),
                 font=("Segoe UI", 8), anchor="w").pack(
            side="top", fill="x", padx=8, pady=(6, 0))

        inner = tk.Frame(self, bg="#000d14")
        inner.pack(fill="x", padx=6, pady=(0, 6))

        self.entry = tk.Entry(inner, bg="#000d14", fg=color,
                              insertbackground=color,
                              relief="flat", font=("Segoe UI", 10),
                              show=show if show else "")
        self.entry.pack(side="left", fill="both", expand=True)

        # Placeholder logic
        if placeholder:
            self._set_placeholder()
            self.entry.bind("<FocusIn>",  self._clear_ph)
            self.entry.bind("<FocusOut>", self._set_ph_if_empty)

        # Eye-toggle for password fields
        if show:
            self._eye_btn = tk.Button(
                inner, text="👁", bg="#000d14", fg=_dim(color, 0.6),
                activebackground="#000d14", activeforeground=color,
                relief="flat", cursor="hand2",
                command=self._toggle_show)
            self._eye_btn.pack(side="right", padx=4)

        self.entry.bind("<FocusIn>",  lambda e: self.config(
            highlightbackground=color), add="+")
        self.entry.bind("<FocusOut>", lambda e: self.config(
            highlightbackground=_dim(color, 0.35)), add="+")

    # ── placeholder helpers ──
    def _set_placeholder(self):
        if not self.entry.get():
            self.entry.insert(0, self._ph)
            self.entry.config(fg=_dim(self._color, 0.35), show="")

    def _clear_ph(self, _e=None):
        if self.entry.get() == self._ph:
            self.entry.delete(0, "end")
            self.entry.config(fg=self._color, show=self._real_show)

    def _set_ph_if_empty(self, _e=None):
        if not self.entry.get():
            self._set_placeholder()

    def _toggle_show(self):
        if self.entry["show"] == "":
            self.entry.config(show=self._real_show)
            self._eye_btn.config(fg=_dim(self._color, 0.6))
        else:
            self.entry.config(show="")
            self._eye_btn.config(fg=self._color)

    def get(self) -> str:
        v = self.entry.get()
        return "" if v == self._ph else v

    def set(self, v: str):
        self.entry.delete(0, "end")
        self.entry.insert(0, v)
        self.entry.config(fg=self._color, show=self._real_show)


class _StyledText(tk.Frame):
    """Multi-line text widget with glowing border."""

    def __init__(self, parent, label: str, placeholder: str = "",
                 height: int = 5, color: str = "#0088ff", **kw):
        super().__init__(parent, bg="#000d14",
                         highlightbackground=_dim(color, 0.35),
                         highlightcolor=color,
                         highlightthickness=1, **kw)
        self._color = color
        self._ph    = placeholder

        tk.Label(self, text=label, bg="#000d14", fg=_dim(color, 0.8),
                 font=("Segoe UI", 8), anchor="w").pack(
            side="top", fill="x", padx=8, pady=(6, 0))

        self.text = tk.Text(self, bg="#000d14", fg=color,
                            insertbackground=color,
                            relief="flat", font=("Segoe UI", 9),
                            height=height, wrap="word",
                            padx=8, pady=4)
        self.text.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        if placeholder:
            self._set_placeholder()
            self.text.bind("<FocusIn>",  self._clear_ph)
            self.text.bind("<FocusOut>", self._set_ph_if_empty)

        self.text.bind("<FocusIn>",  lambda e: self.config(
            highlightbackground=color), add="+")
        self.text.bind("<FocusOut>", lambda e: self.config(
            highlightbackground=_dim(color, 0.35)), add="+")

    def _set_placeholder(self):
        if not self.text.get("1.0", "end-1c"):
            self.text.insert("1.0", self._ph)
            self.text.config(fg=_dim(self._color, 0.3))

    def _clear_ph(self, _e=None):
        if self.text.get("1.0", "end-1c") == self._ph:
            self.text.delete("1.0", "end")
            self.text.config(fg=self._color)

    def _set_ph_if_empty(self, _e=None):
        if not self.text.get("1.0", "end-1c").strip():
            self._set_placeholder()

    def get(self) -> str:
        v = self.text.get("1.0", "end-1c").strip()
        return "" if v == self._ph else v


# ──────────────────────────────────────────────────────────────────────────
# Animated Jarvis mini-logo (canvas widget)
# ──────────────────────────────────────────────────────────────────────────
class _JarvisLogo(tk.Canvas):
    def __init__(self, parent, size: int = 90, color: str = "#0088ff", **kw):
        super().__init__(parent, width=size, height=size,
                         bg="#000000", highlightthickness=0, **kw)
        self._sz    = size
        self._cx    = size // 2
        self._cy    = size // 2
        self._color = color
        self._t     = 0.0
        self._angles = [0.0, 120.0, 240.0]
        self._last   = time.time()
        self._animate()

    def set_color(self, c: str):
        self._color = c

    def _animate(self):
        now = time.time()
        dt  = min(now - self._last, 0.05)
        self._last = now
        self._t   += dt

        speeds = [30.0, -45.0, 22.0]
        for i in range(3):
            self._angles[i] = (self._angles[i] + speeds[i] * dt) % 360

        self._draw()
        self.after(30, self._animate)

    def _draw(self):
        self.delete("all")
        cx, cy, r_base = self._cx, self._cy, self._sz * 0.35
        c = self._color

        # Bloom rings
        for i in range(3):
            rr = r_base + 2 + i * 2
            al = (1 - i / 3) * 0.35 * (0.8 + 0.2 * math.sin(self._t * 3))
            col = _dim(c, al)
            self.create_oval(cx-rr, cy-rr, cx+rr, cy+rr, outline=col, width=1)

        # Spinning arcs
        arc_defs = [
            (1.0, 2, 120, 40, self._angles[0]),
            (1.1, 1,  70, 50, self._angles[1]),
            (1.2, 1,  35, 85, self._angles[2]),
        ]
        for r_m, w, ext, gap, ang in arc_defs:
            rr = r_base * r_m
            col = _dim(c, 0.9)
            for s in range(360 // (ext + gap)):
                st = (ang + s * (ext + gap)) % 360
                self.create_arc(cx-rr, cy-rr, cx+rr, cy+rr,
                                start=st, extent=ext,
                                outline=col, width=w, style="arc")

        # Core fill
        self.create_oval(cx-r_base, cy-r_base, cx+r_base, cy+r_base,
                         fill="#050505", outline=_dim(c, 0.3), width=1)

        # Eye dots
        pulse = 0.8 + 0.2 * math.sin(self._t * 5)
        er, es = r_base * 0.18 * pulse, r_base * 0.3
        self.create_oval(cx-es-er, cy-er, cx-es+er, cy+er,
                         fill="#ffffff", outline="")
        self.create_oval(cx+es-er, cy-er, cx+es+er, cy+er,
                         fill="#ffffff", outline="")


# ──────────────────────────────────────────────────────────────────────────
# Main Setup Window
# ──────────────────────────────────────────────────────────────────────────
class JarvisSetupScreen:
    """
    4-step wizard:
      Step 0 — Welcome
      Step 1 — API Keys
      Step 2 — Identity & Voice
      Step 3 — About Yourself + Persona
    """

    STEPS = ["WELCOME", "API KEYS", "IDENTITY", "ABOUT YOU"]

    def __init__(self, master=None):
        W, H = 580, 680

        if master is not None:
            # Use Toplevel so we share the existing Tk mainloop
            self.root = tk.Toplevel(master)
            self._is_toplevel = True
        else:
            self.root = tk.Tk()
            self._is_toplevel = False

        self.root.title("J.A.R.V.I.S — Initial Configuration")
        self.root.configure(bg="#000000")
        self.root.resizable(False, False)

        # Center window
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw-W)//2}+{(sh-H)//2}")

        # Make it frameless (no title bar) — we draw our own
        try:
            self.root.overrideredirect(True)
        except Exception:
            pass

        # Ensure window appears on top and focused
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.focus_force()
        self.root.update()     # force geometry + topmost to apply immediately

        # State
        self._step        = 0
        self._color       = "#0088ff"
        self._persona_key = "jarvis"
        self._completed   = False

        # Drag support (since overrideredirect)
        self._drag = {"x": 0, "y": 0}

        # ── Saved field values (widgets are destroyed between steps) ──
        self._saved_gemini  = ""
        self._saved_groq    = ""
        self._saved_nvidia  = ""
        self._saved_hf      = ""
        self._saved_name    = ""
        self._saved_aname   = ""
        self._saved_wake    = ""
        self._saved_voice   = list(VOICES.keys())[0]

        self._build_ui(W, H)
        self._show_step(0)

    # ──────────────────────────────────────────────────────────────────
    # UI skeleton
    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self, W: int, H: int):
        # Outer border frame
        border = tk.Frame(self.root, bg=_dim(self._color, 0.4), padx=1, pady=1)
        border.pack(fill="both", expand=True)
        self._border = border

        main = tk.Frame(border, bg="#000000")
        main.pack(fill="both", expand=True)

        # ── Top drag-bar ──
        topbar = tk.Frame(main, bg="#000811", height=36)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        self._logo = _JarvisLogo(topbar, size=28, color=self._color)
        self._logo.pack(side="left", padx=10, pady=4)

        self._title_lbl = tk.Label(
            topbar, text="J.A.R.V.I.S  ·  INITIAL CONFIGURATION",
            bg="#000811", fg=self._color,
            font=("Segoe UI", 9, "bold"), anchor="w")
        self._title_lbl.pack(side="left")

        # Close button
        tk.Button(topbar, text="✕", bg="#000811", fg="#ff3366",
                  activebackground="#1a0011", activeforeground="#ff6699",
                  relief="flat", font=("Segoe UI", 10, "bold"),
                  cursor="hand2",
                  command=self._on_close).pack(side="right", padx=8)

        # Drag bindings
        for w in (topbar, self._title_lbl):
            w.bind("<ButtonPress-1>",   self._drag_start)
            w.bind("<B1-Motion>",       self._drag_move)

        # ── Step indicator ──
        self._step_bar = tk.Frame(main, bg="#000000")
        self._step_bar.pack(fill="x", padx=20, pady=(8, 0))
        self._step_dots = []
        for i, name in enumerate(self.STEPS):
            col_frame = tk.Frame(self._step_bar, bg="#000000")
            col_frame.pack(side="left", expand=True)
            dot = tk.Label(col_frame, text="●", bg="#000000",
                           fg=_dim(self._color, 0.25), font=("Segoe UI", 10))
            dot.pack()
            lbl = tk.Label(col_frame, text=name, bg="#000000",
                           fg=_dim(self._color, 0.25), font=("Segoe UI", 7))
            lbl.pack()
            self._step_dots.append((dot, lbl))
            if i < len(self.STEPS) - 1:
                tk.Label(self._step_bar, text="──", bg="#000000",
                         fg=_dim(self._color, 0.15),
                         font=("Segoe UI", 8)).pack(side="left", expand=True)

        # ── Content area ──
        self._content = tk.Frame(main, bg="#000000")
        self._content.pack(fill="both", expand=True, padx=24, pady=12)

        # ── Bottom nav ──
        nav = tk.Frame(main, bg="#000000")
        nav.pack(fill="x", padx=24, pady=(0, 16))

        self._back_btn = tk.Button(
            nav, text="◀  BACK",
            bg="#000d14", fg=_dim(self._color, 0.6),
            activebackground="#001a2a", activeforeground=self._color,
            relief="flat", font=("Segoe UI", 9, "bold"),
            cursor="hand2", width=12,
            command=self._prev_step)
        self._back_btn.pack(side="left")

        self._next_btn = tk.Button(
            nav, text="NEXT  ▶",
            bg=_dim(self._color, 0.2), fg=self._color,
            activebackground=_dim(self._color, 0.35), activeforeground="#ffffff",
            relief="flat", font=("Segoe UI", 9, "bold"),
            cursor="hand2", width=12,
            command=self._next_step)
        self._next_btn.pack(side="right")

        self._nav_ref = nav  # keep ref for button color updates

    # ──────────────────────────────────────────────────────────────────
    # Drag
    # ──────────────────────────────────────────────────────────────────
    def _drag_start(self, e):
        self._drag["x"] = e.x_root - self.root.winfo_x()
        self._drag["y"] = e.y_root - self.root.winfo_y()

    def _drag_move(self, e):
        x = e.x_root - self._drag["x"]
        y = e.y_root - self._drag["y"]
        self.root.geometry(f"+{x}+{y}")

    # ──────────────────────────────────────────────────────────────────
    # Step rendering
    # ──────────────────────────────────────────────────────────────────
    def _clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()

    def _update_step_dots(self):
        for i, (dot, lbl) in enumerate(self._step_dots):
            if i < self._step:
                c = self._color; sym = "✔"
            elif i == self._step:
                c = self._color; sym = "●"
            else:
                c = _dim(self._color, 0.25); sym = "●"
            dot.config(fg=c, text=sym)
            lbl.config(fg=c)

    def _show_step(self, step: int):
        self._step = step
        self._clear_content()
        self._update_step_dots()
        self._back_btn.config(state="normal" if step > 0 else "disabled",
                              fg=self._color if step > 0 else _dim(self._color, 0.3))

        if step == 0:
            self._build_welcome()
            self._next_btn.config(text="START  ▶")
        elif step == 1:
            self._build_api_keys()
            self._next_btn.config(text="NEXT  ▶")
        elif step == 2:
            self._build_identity()
            self._next_btn.config(text="NEXT  ▶")
        elif step == 3:
            self._build_about()
            self._next_btn.config(text="INITIALIZE  ▶")

    # ── Step 0: Welcome ──────────────────────────────────────────────
    def _build_welcome(self):
        c = self._content

        _JarvisLogo(c, size=100, color=self._color).pack(pady=(20, 10))

        tk.Label(c, text="J.A.R.V.I.S", bg="#000000", fg=self._color,
                 font=("Segoe UI", 22, "bold")).pack()
        tk.Label(c, text="Just A Rather Very Intelligent System",
                 bg="#000000", fg=_dim(self._color, 0.55),
                 font=("Segoe UI", 9)).pack(pady=(2, 20))

        msg = (
            "Welcome.  This is your first time running Jarvis.\n\n"
            "In the next few steps, you will configure your API keys,\n"
            "set up your identity, and tell Jarvis a little about yourself.\n\n"
            "Jarvis will use all of this to personalize every\n"
            "interaction — greetings, daily briefings, suggestions,\n"
            "and memory — specifically for you."
        )
        tk.Label(c, text=msg, bg="#000000", fg=_dim(self._color, 0.75),
                 font=("Segoe UI", 9), justify="center").pack(pady=10)

        tk.Label(c, text="── Your details stay local. Nothing is uploaded. ──",
                 bg="#000000", fg=_dim(self._color, 0.35),
                 font=("Segoe UI", 8)).pack(pady=(10, 0))

    # ── Step 1: API Keys ─────────────────────────────────────────────
    def _build_api_keys(self):
        c = self._content

        tk.Label(c, text="API KEYS", bg="#000000", fg=self._color,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Label(c, text="Gemini key is required.  Others are optional.",
                 bg="#000000", fg=_dim(self._color, 0.55),
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 10))

        self._e_gemini = _StyledEntry(
            c, "GEMINI API KEY  *",
            placeholder="AIza...",
            show="•", color=self._color)
        self._e_gemini.pack(fill="x", pady=4)

        self._e_groq = _StyledEntry(
            c, "GROQ API KEY  (optional — fast STT fallback)",
            placeholder="gsk_...",
            show="•", color=self._color)
        self._e_groq.pack(fill="x", pady=4)

        self._e_nvidia = _StyledEntry(
            c, "NVIDIA API KEY  (optional)",
            placeholder="nvapi-...",
            show="•", color=self._color)
        self._e_nvidia.pack(fill="x", pady=4)

        self._e_hf = _StyledEntry(
            c, "HUGGING FACE API KEY  (optional)",
            placeholder="hf_...",
            show="•", color=self._color)
        self._e_hf.pack(fill="x", pady=4)

        # Pre-fill if file already exists (partial config)
        try:
            if _API_PATH.exists():
                existing = json.loads(_API_PATH.read_text("utf-8"))
                if existing.get("gemini_api_key"):
                    self._e_gemini.set(existing["gemini_api_key"])
                if existing.get("groq_api_key"):
                    self._e_groq.set(existing["groq_api_key"])
                if existing.get("nvidia_api_key"):
                    self._e_nvidia.set(existing["nvidia_api_key"])
                if existing.get("hf_api_key"):
                    self._e_hf.set(existing["hf_api_key"])
        except Exception:
            pass

    # ── Step 2: Identity ─────────────────────────────────────────────
    def _build_identity(self):
        c = self._content

        tk.Label(c, text="IDENTITY", bg="#000000", fg=self._color,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Label(c, text="Jarvis will address you and refer to itself by these names.",
                 bg="#000000", fg=_dim(self._color, 0.55),
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 10))

        self._e_username = _StyledEntry(
            c, "YOUR NAME  *",
            placeholder="e.g. Tony",
            color=self._color)
        self._e_username.pack(fill="x", pady=4)

        self._e_jarvis_name = _StyledEntry(
            c, "WHAT DO YOU WANT TO CALL YOUR ASSISTANT?",
            placeholder="e.g. JARVIS  /  FRIDAY  /  MAX",
            color=self._color)
        self._e_jarvis_name.pack(fill="x", pady=4)

        self._e_wake = _StyledEntry(
            c, "WAKE WORD",
            placeholder="e.g. Hey Jarvis",
            color=self._color)
        self._e_wake.pack(fill="x", pady=4)

        # Voice selector
        tk.Label(c, text="VOICE STYLE", bg="#000000", fg=_dim(self._color, 0.7),
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(10, 4))

        self._voice_var = tk.StringVar(value=list(VOICES.keys())[0])
        vrow = tk.Frame(c, bg="#000000")
        vrow.pack(fill="x")
        for name in VOICES:
            rb = tk.Radiobutton(
                vrow, text=name,
                variable=self._voice_var, value=name,
                bg="#000000", fg=self._color,
                activebackground="#000000", activeforeground=self._color,
                selectcolor="#000d14",
                font=("Segoe UI", 9), cursor="hand2")
            rb.pack(side="left", padx=8)

        # Pre-fill if profile exists
        try:
            if _PROFILE_PATH.exists():
                p = json.loads(_PROFILE_PATH.read_text("utf-8"))
                n = p.get("personal_info", {}).get("name", "")
                if n and n != "User":
                    self._e_username.set(n)
                an = p.get("assistant_name", "")
                if an:
                    self._e_jarvis_name.set(an)
                ww = p.get("preferences", {}).get("wake_word", "")
                if ww:
                    self._e_wake.set(ww)
        except Exception:
            pass

    # ── Step 3: About You + Persona ───────────────────────────────────
    def _build_about(self):
        c = self._content

        tk.Label(c, text="ABOUT YOU", bg="#000000", fg=self._color,
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 4))
        tk.Label(c,
                 text="The more you share, the better Jarvis knows you.\n"
                      "This trains your personal memory from day one.",
                 bg="#000000", fg=_dim(self._color, 0.55),
                 font=("Segoe UI", 8), justify="left").pack(anchor="w", pady=(0, 8))

        self._bio_text = _StyledText(
            c,
            label="TELL JARVIS ABOUT YOURSELF",
            placeholder=(
                "Example:\n"
                "I'm a 19-year-old CS student who loves building AI projects.\n"
                "I wake up at 7 AM and commute to college daily.\n"
                "I'm into guitar, music, and Python. My goal this year is to\n"
                "launch 3 SaaS products. I prefer concise, smart responses\n"
                "and I love being reminded of my goals."
            ),
            height=6,
            color=self._color)
        self._bio_text.pack(fill="x", pady=(0, 10))

        # Persona picker
        tk.Label(c, text="PERSONA THEME", bg="#000000", fg=_dim(self._color, 0.7),
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 6))

        persona_row = tk.Frame(c, bg="#000000")
        persona_row.pack(fill="x")
        self._persona_var = tk.StringVar(value="J.A.R.V.I.S")

        self._persona_btns = {}
        for name, meta in PERSONAS.items():
            pc = meta["primary"]
            btn = tk.Button(
                persona_row, text=f"{name}\n{meta['desc']}",
                bg=_dim(pc, 0.12), fg=pc,
                activebackground=_dim(pc, 0.25), activeforeground="#ffffff",
                relief="flat", font=("Segoe UI", 8, "bold"),
                cursor="hand2", padx=8, pady=6,
                command=lambda n=name: self._select_persona(n))
            btn.pack(side="left", expand=True, fill="x", padx=4)
            self._persona_btns[name] = btn

        self._select_persona("J.A.R.V.I.S")

        # Pre-fill bio if profile exists
        try:
            if _PROFILE_PATH.exists():
                p = json.loads(_PROFILE_PATH.read_text("utf-8"))
                bio = p.get("bio_raw", "")
                if bio:
                    self._bio_text.text.delete("1.0", "end")
                    self._bio_text.text.insert("1.0", bio)
                    self._bio_text.text.config(fg=self._color)
        except Exception:
            pass

    def _select_persona(self, name: str):
        self._persona_var.set(name)
        meta = PERSONAS[name]
        self._persona_key = meta["key"]
        new_color = meta["primary"]
        self._color = new_color

        # Refresh logo colour
        self._logo.set_color(new_color)

        # Refresh persona button highlights
        for n, btn in self._persona_btns.items():
            pm = PERSONAS[n]
            pc = pm["primary"]
            if n == name:
                btn.config(bg=_dim(pc, 0.3), fg="#ffffff",
                           relief="solid")
            else:
                btn.config(bg=_dim(pc, 0.12), fg=pc, relief="flat")

        # Refresh nav buttons
        self._next_btn.config(
            bg=_dim(new_color, 0.2), fg=new_color,
            activebackground=_dim(new_color, 0.35))
        self._back_btn.config(fg=new_color)

        # Refresh border
        self._border.config(bg=_dim(new_color, 0.4))

        self._title_lbl.config(fg=new_color)

    # ──────────────────────────────────────────────────────────────────
    # Navigation
    # ──────────────────────────────────────────────────────────────────
    def _prev_step(self):
        if self._step > 0:
            self._show_step(self._step - 1)

    def _next_step(self):
        if self._step == 1 and not self._validate_api_keys():
            return
        if self._step == 2 and not self._validate_identity():
            return
        if self._step == 3:
            self._finalize()
            return
        # Save current step's values BEFORE _show_step destroys the widgets
        if self._step == 1:
            self._saved_gemini = self._e_gemini.get().strip()
            self._saved_groq   = self._e_groq.get().strip()
            self._saved_nvidia = self._e_nvidia.get().strip()
            self._saved_hf     = self._e_hf.get().strip()
        elif self._step == 2:
            self._saved_name  = self._e_username.get().strip()
            self._saved_aname = self._e_jarvis_name.get().strip()
            self._saved_wake  = self._e_wake.get().strip()
            self._saved_voice = self._voice_var.get()
        self._show_step(self._step + 1)

    # ──────────────────────────────────────────────────────────────────
    # Validation
    # ──────────────────────────────────────────────────────────────────
    def _validate_api_keys(self) -> bool:
        key = self._e_gemini.get().strip()
        if not key or len(key) < 15:
            messagebox.showerror(
                "API Key Required",
                "Please enter a valid Gemini API key to continue.",
                parent=self.root)
            return False
        return True

    def _validate_identity(self) -> bool:
        name = self._e_username.get().strip()
        if not name:
            messagebox.showerror(
                "Name Required",
                "Please enter your name so Jarvis can address you properly.",
                parent=self.root)
            return False
        return True

    # ──────────────────────────────────────────────────────────────────
    # Finalize — write config files
    # ──────────────────────────────────────────────────────────────────
    def _finalize(self):
        # Step 3 widgets are still alive — read them directly
        bio_raw     = self._bio_text.get()
        persona_key = self._persona_key

        # Steps 1 & 2 widgets are destroyed — read from saved strings
        user_name   = self._saved_name  or "User"
        jarvis_name = self._saved_aname or "J.A.R.V.I.S"
        wake_word   = self._saved_wake  or "Hey Jarvis"
        voice_key   = VOICES.get(self._saved_voice, "en-US-Neural2-J")

        # ── 1. Write api_keys.json ──────────────────────────────────
        _API_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Preserve any existing optional keys already in the file
        existing_api = {}
        try:
            if _API_PATH.exists():
                existing_api = json.loads(_API_PATH.read_text("utf-8"))
        except Exception:
            pass

        api_data = {
            **existing_api,
            "gemini_api_key":     self._saved_gemini or existing_api.get("gemini_api_key", ""),
            "groq_api_key":       self._saved_groq   or existing_api.get("groq_api_key", ""),
            "nvidia_api_key":     self._saved_nvidia or existing_api.get("nvidia_api_key", ""),
            "hf_api_key":         self._saved_hf     or existing_api.get("hf_api_key", ""),
            "openrouter_api_key": existing_api.get("openrouter_api_key", ""),
            "browser_type":       existing_api.get("browser_type", "firefox"),
        }
        _API_PATH.write_text(json.dumps(api_data, indent=4), encoding="utf-8")

        # ── 2. Parse bio into structured profile ────────────────────
        profile = self._build_profile(
            user_name=user_name,
            jarvis_name=jarvis_name,
            wake_word=wake_word,
            voice_key=voice_key,
            persona_key=persona_key,
            bio_raw=bio_raw,
        )

        _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False),
                                 encoding="utf-8")

        self._completed = True
        self.root.destroy()

    def _build_profile(self, *, user_name, jarvis_name, wake_word,
                       voice_key, persona_key, bio_raw) -> dict:
        """
        Build a user_profile.json structure from the setup data.
        The bio_raw string is stored as-is so Jarvis can read it directly
        as personalization context.  The profile_manager can parse it
        further over time.
        """
        # Try to load existing profile so we don't erase previously learned data
        existing = {}
        try:
            if _PROFILE_PATH.exists():
                existing = json.loads(_PROFILE_PATH.read_text("utf-8"))
        except Exception:
            pass

        now = datetime.now().strftime("%Y-%m-%d")

        profile = {
            **existing,   # preserve anything already learned
            "personal_info": {
                **existing.get("personal_info", {}),
                "name": user_name,
            },
            "assistant_name": jarvis_name,
            "bio_raw": bio_raw,
            "preferences": {
                **existing.get("preferences", {}),
                "wake_word":   wake_word,
                "voice_style": voice_key,
                "persona":     persona_key,
                "speech_style": "Hinglish" if persona_key == "jarvis" else "English",
                "tone": "Smart, premium, human-like, motivating",
                "vibe": "Respectful friend + elite assistant",
            },
            "skills":    existing.get("skills",    []),
            "interests": existing.get("interests", []),
            "personality": existing.get("personality", {
                "traits":      [],
                "description": bio_raw[:200] if bio_raw else "",
            }),
            "routine": existing.get("routine", {}),
            "goals":   existing.get("goals",   {}),
            "metadata": {
                **existing.get("metadata", {}),
                "setup_completed": True,
                "setup_date":      now,
                "last_updated":    now,
            },
        }
        return profile

    # ──────────────────────────────────────────────────────────────────
    # Window close
    # ──────────────────────────────────────────────────────────────────
    def _on_close(self):
        if not self._completed:
            if messagebox.askyesno(
                "Exit Setup",
                "Setup is not complete.\nJarvis cannot start without an API key.\n\nExit anyway?",
                parent=self.root):
                self.root.destroy()
                os._exit(0)
        else:
            self.root.destroy()

    # ──────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────
    def run(self):
        """Block until the user completes (or cancels) setup."""
        if self._is_toplevel:
            # We already have a running mainloop (from the hidden master root).
            # wait_window blocks until self.root is destroyed.
            self.root.wait_window(self.root)
        else:
            self.root.mainloop()
        return self._completed


# ──────────────────────────────────────────────────────────────────────────
# Public helper — called from main.py
# ──────────────────────────────────────────────────────────────────────────
def is_setup_needed() -> bool:
    """Return True if the Gemini API key is missing or blank."""
    try:
        if not _API_PATH.exists():
            return True
        data = json.loads(_API_PATH.read_text("utf-8"))
        key  = data.get("gemini_api_key", "").strip()
        return not key or len(key) < 10
    except Exception:
        return True


def show_setup_if_needed() -> bool:
    """
    Launch the setup wizard if needed.
    Returns True if Jarvis should continue booting,
    False if the user cancelled (process will have exited).
    """
    if not is_setup_needed():
        return True
    wizard = JarvisSetupScreen()
    wizard.run()
    # If we get here the wizard closed — check if it completed
    return is_setup_needed() is False


# ── Standalone test ───────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys as _sys
    force = "--force" in _sys.argv or "-f" in _sys.argv
    if force:
        # Show setup regardless of whether api_keys.json exists
        wizard = JarvisSetupScreen()
        result = wizard.run()
    else:
        result = show_setup_if_needed()
    print("Setup completed:", result)
