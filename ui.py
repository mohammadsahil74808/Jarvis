import os, json, time, math, random, threading, psutil, subprocess, shutil
try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import tkinter as tk
from collections import deque
from PIL import Image, ImageTk, ImageDraw
#: Error (duplicate): f.recv_excn is not implemet -> Fixed in backend summary, not UI.
import sys
from pathlib import Path


from core.config import get_base_dir, BASE_DIR, CONFIG_DIR, API_CONFIG_PATH as API_FILE

SYSTEM_NAME = "J.A.R.V.I.S"
MODEL_BADGE = "JARVIS"

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
C_MUTED  = "#ff3366"



class ConsolePanel(tk.Toplevel):
    """Futuristic Live Typing Console Panel"""
    def __init__(self, parent_ui):
        super().__init__(parent_ui.root)
        self.ui = parent_ui
        self.title("J.A.R.V.I.S | DATA CONSOLE")
        x = parent_ui.CX
        # Fixed geometry to match CW/CH
        self.geometry(f"{parent_ui.CW}x{parent_ui.CH}+{x}+50")
        self.overrideredirect(True)
        self.transient(parent_ui.root) # Attach to parent stacking order
        self.attributes("-alpha", 0.9)
        self.configure(bg=C_BG)

        self.canvas = tk.Canvas(self, bg=C_BG, highlightthickness=1, highlightbackground=C_MID)
        self.canvas.pack(fill="both", expand=True)

        self.text_area = tk.Text(
            self.canvas, fg=C_TEXT, bg=C_PANEL,
            insertbackground=C_TEXT, borderwidth=0,
            wrap="word", font=("Courier", 10), padx=8, pady=8
        )
        self.text_area.place(relx=0.05, rely=0.1, relwidth=0.9, relheight=0.85)
        self.text_area.configure(state="disabled")
        self.text_area.tag_config("you", foreground="#e8e8e8")
        self.text_area.tag_config("ai",  foreground=C_PRI)
        self.text_area.tag_config("sys", foreground=C_ACC2)
        self.text_area.tag_config("err", foreground=C_RED)

        self.canvas.create_text(parent_ui.CW//2, 15, text="LIVE DATA STREAM", fill=C_ACC, font=("Courier", 10, "bold"))
        self._typing_queue = deque()
        self._is_typing = False

    def write_log(self, text: str):
        self._typing_queue.append(text)
        if not self._is_typing:
            self._start_typing()

    def _start_typing(self):
        if not self._typing_queue:
            self._is_typing = False
            return
        self._is_typing = True
        text = self._typing_queue.popleft()
        tl = text.lower()
        if "you:" in tl or "jarvis:" in tl:
            clean = text.split(":", 1)[1].strip() if ":" in text else text
            self.ui.activity_feed.append(f"▸ {clean[:20]}...")

        tag = "you" if tl.startswith("you:") else ("ai" if (tl.startswith("jarvis:") or tl.startswith("ai:")) else ("err" if ("error" in tl or "failed" in tl) else "sys"))
        self.text_area.configure(state="normal")
        self._type_char(text, 0, tag)

    def _type_char(self, text, i, tag):
        if i < len(text):
            chunk = text[i:i+3]
            self.text_area.insert(tk.END, chunk, tag)
            self.text_area.see(tk.END)
            self.after(20, self._type_char, text, i + len(chunk), tag)
        else:
            self.text_area.insert(tk.END, "\n")
            self.text_area.configure(state="disabled")
            self._is_typing = False
            if self._typing_queue:
                self.after(100, self._start_typing)

class StatsPanel(tk.Toplevel):
    """Futuristic Real-Time System Stats & HUD Panel (v2)"""
    def __init__(self, parent_ui):
        super().__init__(parent_ui.root)
        self.ui = parent_ui
        self.title("J.A.R.V.I.S | HUD MODULE")
        # Vertically Centered relative to Main Window (Right Side)
        SY = parent_ui.root.winfo_y() + (parent_ui.H - parent_ui.SH) // 2
        self.geometry(f"{parent_ui.SW}x{parent_ui.SH}+{parent_ui.root.winfo_x() + parent_ui.W + 15}+{SY}")
        self.overrideredirect(True)
        self.transient(parent_ui.root) 
        self.attributes("-alpha", 0.95)
        self.configure(bg=C_BG)

        self.canvas = tk.Canvas(self, bg=C_BG, highlightthickness=1, highlightbackground=C_MID)
        self.canvas.pack(fill="both", expand=True)
        
        self.tick = 0
        self._animate()

    def _animate(self):
        self.tick += 1
        self.canvas.delete("dynamic")
        
        # 1. ── HUD Animation (Top) ──────────────────
        cx, cy = 190, 100
        # Rotating Scanner Arc
        self.canvas.create_arc(cx-80, cy-80, cx+80, cy+80, start=(self.tick*4)%360, extent=120, 
                               outline=C_PRI, width=3, style="arc", tags="dynamic")
        self.canvas.create_arc(cx-95, cy-95, cx+95, cy+95, start=(self.tick*-2)%360, extent=60, 
                               outline="#ff3333", width=2, style="arc", tags="dynamic")
        # Inner Rotating Lines
        angle = math.radians(self.tick * 6)
        x2, y2 = cx + 60 * math.cos(angle), cy + 60 * math.sin(angle)
        self.canvas.create_line(cx, cy, x2, y2, fill=C_PRI, width=1, tags="dynamic")
        self.canvas.create_oval(cx-6, cy-6, cx+6, cy+6, fill=C_PRI, outline="", tags="dynamic")

        # 2. ── Clock & Greeting ─────────────────────
        time_str = time.strftime("%I:%M:%S %p")
        date = time.strftime("%d %b %Y").upper()
        ty = 200
        self.canvas.create_text(cx+1, ty+1, text=time_str, fill=C_DIM, font=("Courier", 24, "bold"), tags="dynamic")
        self.canvas.create_text(cx, ty, text=time_str, fill="#ffffff", font=("Courier", 24, "bold"), tags="dynamic")
        self.canvas.create_text(cx, ty+35, text=date, fill=C_PRI, font=("Courier", 10), tags="dynamic")
        
        self.canvas.create_text(cx, ty+65, text="STATUS: READY", fill="#00ff88", font=("Courier", 9, "bold"), tags="dynamic")
        user_name = "USER"
        try:
            if self.ui.jarvis:
                user_name = self.ui.jarvis.profile_manager.get_profile().get("name", "USER").upper()
        except: pass
        self.canvas.create_text(cx, ty+82, text=f"WELCOME BACK, {user_name}", fill=C_MID, font=("Courier", 8), tags="dynamic")

        # 3. ── Live JARVIS Status ──────────────────
        status = self.ui._jarvis_state
        color = "#ffffff"
        if status == "LISTENING": color = "#00ff88"
        elif status == "THINKING": color = "#ffcc00"
        elif status == "SPEAKING": color = C_PRI
        elif status == "MUTED": color = "#ff3333"
        
        SY_RECT = 320
        self.canvas.create_rectangle(60, SY_RECT, 320, SY_RECT+35, outline=color, width=2, tags="dynamic")
        self.canvas.create_text(190, SY_RECT+17, text=status, fill=color, font=("Courier", 12, "bold"), tags="dynamic")

        # 4. ── Core Performance (Bars) ──────────────
        sy = 400
        stats = self.ui.stats
        self._draw_bar(sy, "CPU LOAD", stats.get('cpu', 0), "#ff3333" if stats.get('cpu',0)>80 else C_PRI)
        self._draw_bar(sy+65, "RAM USAGE", stats.get('ram', 0), "#ff3333" if stats.get('ram',0)>80 else "#00ff88")
        self.canvas.create_text(30, sy+120, text=f"NET CONNECTIVITY: {stats.get('net', '0 KB/s')}", fill="#ffffff", font=("Courier", 9), anchor="w", tags="dynamic")

        # 5. ── Mini Activity Feed ──────────────────
        fy = 580
        self.canvas.create_text(30, fy-25, text="LIVE SYSTEM LOG", fill=C_PRI, font=("Courier", 9, "bold"), anchor="w", tags="dynamic")
        for i, act in enumerate(list(self.ui.activity_feed)):
            self.canvas.create_text(30, fy + (i*18), text=act, fill="#aaaaaa", font=("Courier", 9), anchor="w", tags="dynamic")

        # 6. ── Voice Visualizer ────────────────────
        vy = 750
        N_BARS = 18
        for i in range(N_BARS):
            h = random.randint(10, 40) if status == "SPEAKING" else (random.randint(4, 12) if status == "LISTENING" else 5)
            x_pos = 65 + (i * 16)
            self.canvas.create_rectangle(x_pos, vy-h, x_pos+10, vy, fill=C_PRI if status != "MUTED" else "#330000", outline="", tags="dynamic")

        self.after(200, self._animate)

    def _draw_bar(self, y, label, val, col):
        self.canvas.create_text(30, y, text=label, fill="#ffffff", font=("Courier", 8), anchor="w", tags="dynamic")
        # Wider bars for 380px panel
        self.canvas.create_rectangle(30, y+10, 350, y+24, outline=C_DIM, width=1, tags="dynamic")
        w_max = 320
        w = int(w_max * (val/100.0))
        if w > 0:
            self.canvas.create_rectangle(30, y+10, 30+w, y+24, fill=col, outline="", tags="dynamic")
        self.canvas.create_text(360, y+17, text=f"{val:.0f}%", fill=col, font=("Courier", 8, "bold"), anchor="e", tags="dynamic")

class WebIntelManager:
    """Managed Edge Browser in App Mode (Left Bottom)"""
    def __init__(self, parent_ui):
        self.ui = parent_ui
        self.proc = None
        self.edge_path = self._find_edge()
        
    def _find_edge(self):
        # 1. Check PATH
        path = shutil.which("msedge")
        if path: return path
        
        # 2. Check common locations
        paths = [
            os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)") + "\\Microsoft\\Edge\\Application\\msedge.exe",
            os.environ.get("PROGRAMFILES", "C:\\Program Files") + "\\Microsoft\\Edge\\Application\\msedge.exe",
            os.path.expanduser("~") + "\\AppData\\Local\\Microsoft\\Edge\\Application\\msedge.exe"
        ]
        for p in paths:
            if os.path.exists(p): return p
        return "msedge.exe" # Last resort

    def search(self, query):
        if self.proc:
            try:
                self.proc.terminate()
            except: pass
        
        # Anchor to actual Console position
        try:
            # Bilkul niche aur left (Left panel ke niche)
            # Use hard coordinates for Bottom-Left focus
            x, y = 160, 920
        except Exception as e:
            print(f"[UI] [Browser] Pos calculation error: {e}")
            x, y = 200, 700
            
        w, h = 550, 600 # Smaller and Square-ish
        
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        
        # Wapas fixed profile par switch kar raha hoon taaki "Sync" popup na aaye
        data_dir = os.path.join(os.environ.get("LOCALAPPDATA", "C:\\Temp"), "JarvisEdgeProfile")
        
        flags = [
            self.edge_path,
            f"--app={url}",
            f"--window-position={x},{y}",
            f"--window-size={w},{h}",
            f"--user-data-dir={data_dir}",
            "--force-device-scale-factor=0.6", 
            "--new-window",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-first-run-ui",
            "--disable-sync",
            "--disable-features=msEdgeSocialSidebar,msEdgeInPrivateSync"
        ]
        
        print(f"[UI] [Browser] Launching Edge: {x},{y} {w}x{h}")
        try:
            self.proc = subprocess.Popen(flags, shell=False)
        except Exception as e:
            print(f"[UI] [Browser] Failed to launch Edge: {e}")

    def close(self):
        if self.proc:
            try:
                self.proc.terminate()
            except: pass
            self.proc = None

class JarvisUI:
    def __init__(self, face_path, size=None):
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S — MARK XXXV")
        self.root.resizable(False, False)

        # ── Layout Calculation ───────────────────────────────────────────────
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        
        # Panel Sizes (ULTRA-LARGE Scaling)
        self.W, self.H   = 950, 800  # Massive Main
        self.CW, self.CH = 320, 500  # Wide Console
        self.SW, self.SH = 380, 800  # Detailed Stats
        W, H, CW, CH, SW, SH = self.W, self.H, self.CW, self.CH, self.SW, self.SH
        
        # Margins & Spacing
        MARGIN = 30
        SPACING = (sw - W - CW - SW - 2*MARGIN) // 2
        SPACING = max(10, min(SPACING, 50)) # Clamp spacing
        
        # Positions (Above Center)
        RX = (sw - W) // 2
        RY = (sh - H) // 2 - 60
        
        CX = (RX - SPACING - CW)
        SX = (RX + W + SPACING)
        
        # Fallback for small screens
        if CX < MARGIN:
            CX = MARGIN
        if SX + SW > sw - MARGIN:
            SX = sw - SW - MARGIN

        self.root.geometry(f"{W}x{H}+{RX}+{RY}")
        self.root.configure(bg=C_BG)

        self.sw, self.sh = sw, sh
        self.CX, self.SX = CX, SX

        self.FACE_SZ = min(int(H * 0.52), 600)
        self.FCX     = W // 2
        # Offset for Ultra-Large H
        self.FCY     = int(H * 0.16) + self.FACE_SZ // 2

        # ── Durum ────────────────────────────────────────────────────────────
        config = self._get_config_internal()
        self.wake_word_enabled = config.get("wake_word_activation", True)
        self.speaking     = False
        self.muted        = self.wake_word_enabled  # Start muted if wake word is active
        self.scale        = 1.0
        self.target_scale = 1.0
        self.halo_a       = 60.0
        self.target_halo  = 60.0
        self.last_t       = time.time()
        self.tick         = 0
        self.scan_angle   = 0.0
        self.scan2_angle  = 180.0
        self.rings_spin   = [0.0, 120.0, 240.0]
        self.pulse_r      = [0.0, self.FACE_SZ * 0.26, self.FACE_SZ * 0.52]
        self.status_text  = "INITIALISING"
        self.status_blink = True

        self._jarvis_state = "INITIALISING"
        self.typing_queue = deque()
        self.activity_feed = deque(maxlen=5) # Last 5 activities
        self.is_typing    = False
        self.on_text_command = None

        # System Stats
        self.stats = {
            "cpu": 0, "ram": 0, "net": "0 KB/s", 
            "weather": "CLEAR", "status": "ONLINE"
        }
        self.last_net_bytes = psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
        self._sync_pending = False
        self._start_stats_thread()

        self._face_pil         = None
        self._has_face         = False
        self._face_scale_cache = None
        self._load_face(face_path)

        # ── Sync Panels ──────────────────────────────────────────────────────
        self.root.update_idletasks()
        
        # Position Console and Stats relative to Root
        self.console_panel = ConsolePanel(self)
        
        self.stats_panel   = StatsPanel(self)
        # Stats panel ko upar shift kiya (centered relative to screen)
        self.stats_panel.geometry(f"{SW}x{SH}+{SX}+{(sh - SH) // 2 - 60}")
        
        # New Real Browser Panel
        self.web_panel = WebIntelManager(self)

        # ── Canvas (arka plan animasyon) ─────────────────────────────────────
        self.bg = tk.Canvas(self.root, width=W, height=H,
                            bg=C_BG, highlightthickness=0)
        self.bg.place(x=0, y=0)

        # ── Log alanı (Shrunk) ────────────────────────────────────────────────────────
        LW = int(W * 0.65)
        LH = 80
        # Align interaction cluster higher
        INPUT_Y = H - 45 
        LOG_Y   = INPUT_Y - LH
        self.log_frame = tk.Frame(self.root, bg=C_PANEL,
                                  highlightbackground=C_MID,
                                  highlightthickness=1)
        self.log_frame.place(x=(W - LW) // 2, y=LOG_Y, width=LW, height=LH)
        self.log_text = tk.Text(self.log_frame, fg=C_TEXT, bg=C_PANEL,
                                insertbackground=C_TEXT, borderwidth=0,
                                wrap="word", font=("Courier", 10), padx=10, pady=8)
        self.log_text.pack(fill="both", expand=True)
        self.log_text.configure(state="disabled")
        self.log_text.tag_config("you", foreground="#e8e8e8")
        self.log_text.tag_config("ai",  foreground=C_PRI)
        self.log_text.tag_config("sys", foreground=C_ACC2)
        self.log_text.tag_config("err", foreground=C_RED)
        self.MAX_LOG_LINES = 1000

        # ── Klavye girişi ─────────────────────────────────────────────────────
        self._build_input_bar(LW, INPUT_Y)

        # ── Mute butonu ───────────────────────────────────────────────────────
        self._build_mute_button()

        # ── F4 kısayolu ───────────────────────────────────────────────────────
        self.root.bind("<F4>", lambda e: self._toggle_mute())

        # ── API key ───────────────────────────────────────────────────────────
        self._api_key_ready = self._api_keys_exist()
        self._log_lock = threading.Lock()
        if not self._api_key_ready:
            self._show_setup_ui()

        self._animate()
        
        # ── State Synchronization ────────────────────────────────────────────
        def sync_side_panels(event=None):
            if not self._sync_pending:
                self._sync_pending = True
                self.root.after(100, self._do_sync_and_reset)

        self.root.bind("<Unmap>", sync_side_panels)
        self.root.bind("<Map>", sync_side_panels)
        self.root.bind("<Configure>", sync_side_panels) # Detects state changes
        
        # Periodic "Heartbeat" removed to save CPU. Windows events handle sync.
        
        def on_closing():
            try:
                self.console_panel.destroy()
                self.stats_panel.destroy()
                self.root.destroy()
            finally:
                os._exit(0)
        
        self.root.protocol("WM_DELETE_WINDOW", on_closing)

    def _perform_sync(self):
        """Force side panels to match main window visibility"""
        try:
            state = self.root.state()
            # On Windows: 'iconic' = minimized, 'normal'/'zoomed' = visible
            if state == 'iconic':
                self.console_panel.withdraw()
                self.stats_panel.withdraw()
            else:
                self.console_panel.deiconify()
                self.stats_panel.deiconify()
                # Use lift to bring them up with the parent
                self.console_panel.lift()
                self.stats_panel.lift()
                if hasattr(self, "web_panel") and self.web_panel.proc is not None:
                    # browser_panel replaced by web_panel (WebIntelManager), which doesn't have .lift()
                    pass
        except Exception: pass

    def _do_sync_and_reset(self):
        self._sync_pending = False
        self._perform_sync()

    # _periodic_sync_check removed for performance.

    def open_browser_panel(self, query=None):
        """External hook to launch search terminal"""
        if query:
            self.web_panel.search(query)

    def _build_mute_button(self):
        self.BTN_W, self.BTN_H = 120, 30
        # Align to the left of the input bar (x0)
        lw = int(self.W * 0.65)
        x0 = (self.W - lw) // 2
        BTN_X = x0 - self.BTN_W - 10
        # Match Input bar Y exactly
        BTN_Y = self.H - 45 - 4 # Slight vertical center alignment

        self._mute_canvas = tk.Canvas(
            self.root, width=self.BTN_W, height=self.BTN_H,
            bg=C_BG, highlightthickness=0, cursor="hand2"
        )
        self._mute_canvas.place(x=BTN_X, y=BTN_Y)
        self._mute_canvas.bind("<Button-1>", lambda e: self._toggle_mute())
        self._draw_mute_button()

    def _draw_mute_button(self):
        c = self._mute_canvas
        c.delete("all")
        if self.muted:
            border, fill, icon, label, fg = C_MUTED, "#1a0008", "🔇", " MUTED", C_MUTED
        else:
            border, fill, icon, label, fg = C_MID, C_PANEL, "🎙", " LIVE", C_GREEN

        c.create_rectangle(0, 0, self.BTN_W, self.BTN_H, outline=border, fill=fill, width=1)
        c.create_text(self.BTN_W//2, self.BTN_H//2, text=f"{icon}{label}",
                      fill=fg, font=("Courier", 10, "bold"))

    def _toggle_mute(self):
        self.muted = not self.muted
        self._draw_mute_button()
        if self.muted:
            self.set_state("MUTED")
            self.write_log("SYS: Microphone muted.")
        else:
            self.set_state("LISTENING")
            self.write_log("SYS: Microphone active.")

    def _build_input_bar(self, lw: int, y: int):
        x0    = (self.W - lw) // 2
        BTN_W = 70
        INP_W = lw - BTN_W - 4

        self._input_var = tk.StringVar()
        self._input_entry = tk.Entry(
            self.root, textvariable=self._input_var, fg=C_TEXT, bg="#000d12",
            insertbackground=C_TEXT, borderwidth=0, font=("Courier", 8),
            highlightthickness=1, highlightbackground=C_DIM, highlightcolor=C_PRI,
        )
        self._input_entry.place(x=x0, y=y, width=INP_W, height=22)
        self._input_entry.bind("<Return>", self._on_input_submit)
        
        self._send_btn = tk.Button(
            self.root, text="SEND ▸", command=self._on_input_submit,
            fg=C_PRI, bg=C_PANEL, activeforeground=C_BG, activebackground=C_PRI,
            font=("Courier", 7, "bold"), borderwidth=0, cursor="hand2",
            highlightthickness=1, highlightbackground=C_MID,
        )
        self._send_btn.place(x=x0 + INP_W + 4, y=y, width=BTN_W, height=22)

    def _on_input_submit(self, event=None):
        text = self._input_var.get().strip()
        if not text: return
        self._input_var.set("")
        self.write_log(f"You: {text}")
        if self.on_text_command:
            threading.Thread(target=self.on_text_command, args=(text,), daemon=True).start()

    def set_state(self, state: str):
        self._jarvis_state = state
        if state == "MUTED":
            self.status_text, self.speaking = "MUTED", False
        elif state == "SPEAKING":
            self.status_text, self.speaking = "SPEAKING", True
        elif state == "THINKING":
            self.status_text, self.speaking = "THINKING", False
        elif state == "LISTENING":
            self.status_text, self.speaking = "LISTENING", False
        elif state == "PROCESSING":
            self.status_text, self.speaking = "PROCESSING", False
        else:
            self.status_text, self.speaking = "ONLINE", False
        self.stats["status"] = self.status_text

    def _start_stats_thread(self):
        def _update_loop():
            while True:
                try:
                    cpu = psutil.cpu_percent(interval=1)
                    ram = psutil.virtual_memory().percent
                    curr_bytes = psutil.net_io_counters().bytes_sent + psutil.net_io_counters().bytes_recv
                    diff = (curr_bytes - self.last_net_bytes) / 1024.0
                    self.last_net_bytes = curr_bytes
                    net_str = f"{diff:.1f} KB/s" if diff < 1024 else f"{diff/1024:.1f} MB/s"
                    self.stats.update({"cpu": cpu, "ram": ram, "net": net_str})
                    time.sleep(5) # Decreased frequency
                except Exception: time.sleep(10)
        threading.Thread(target=_update_loop, daemon=True).start()

    def _load_face(self, path):
        FW = self.FACE_SZ
        try:
            img  = Image.open(path).convert("RGBA").resize((FW, FW), Image.LANCZOS)
            mask = Image.new("L", (FW, FW), 0)
            ImageDraw.Draw(mask).ellipse((2, 2, FW - 2, FW - 2), fill=255)
            img.putalpha(mask)
            self._face_pil, self._has_face = img, True
        except Exception: self._has_face = False

    @staticmethod
    def _ac(r, g, b, a):
        f = a / 255.0
        return f"#{int(r*f):02x}{int(g*f):02x}{int(b*f):02x}"

    def _animate(self):
        self.tick += 1
        t = self.tick
        now = time.time()

        if now - self.last_t > (0.14 if self.speaking else 0.55):
            if self.speaking:
                self.target_scale = random.uniform(1.05, 1.11)
                self.target_halo  = random.uniform(138, 182)
            elif self.muted:
                self.target_scale = random.uniform(0.998, 1.001)
                self.target_halo  = random.uniform(20, 32)
            else:
                self.target_scale = random.uniform(1.001, 1.007)
                self.target_halo  = random.uniform(50, 68)
            self.last_t = now

        sp = 0.35 if self.speaking else 0.16
        self.scale  += (self.target_scale - self.scale) * sp
        self.halo_a += (self.target_halo  - self.halo_a) * sp

        for i, spd in enumerate([1.2, -0.8, 1.9] if self.speaking else [0.5, -0.3, 0.82]):
            self.rings_spin[i] = (self.rings_spin[i] + spd) % 360

        self.scan_angle  = (self.scan_angle  + (2.8 if self.speaking else 1.2)) % 360
        self.scan2_angle = (self.scan2_angle + (-1.7 if self.speaking else -0.68)) % 360

        pspd  = 3.8 if self.speaking else 1.8
        limit = self.FACE_SZ * 0.72
        new_p = [r + pspd for r in self.pulse_r if r + pspd < limit]
        if len(new_p) < 3 and random.random() < (0.06 if self.speaking else 0.022):
            new_p.append(0.0)
        self.pulse_r = new_p

        if t % 40 == 0: self.status_blink = not self.status_blink
        self._draw()
        self.root.after(50, self._animate) # Optimized to 20fps for performance

    def _draw(self):
        c = self.bg
        W, H, t = self.W, self.H, self.tick
        FCX, FCY, FW = self.FCX, self.FCY, self.FACE_SZ
        
        # Performance optimization: tagging objects
        c.delete("anim")

        # Static Grid
        if t == 1:
            for x in range(0, W, 44):
                for y in range(0, H, 44):
                    c.create_rectangle(x, y, x+1, y+1, fill=C_DIMMER, outline="", tags="grid")

        # Halo
        for r in range(int(FW * 0.54), int(FW * 0.28), -22):
            frac = 1.0 - (r - FW * 0.28) / (FW * 0.26)
            ga = max(0, min(255, int(self.halo_a * 0.09 * frac)))
            col = f"#{ga:02x}0011" if self.muted else f"#00{ga:02x}ff"
            c.create_oval(FCX-r, FCY-r, FCX+r, FCY+r, outline=col, width=2, tags="anim")

        # Pulse
        for pr in self.pulse_r:
            pa = max(0, int(220 * (1.0 - pr / (FW * 0.72))))
            r = int(pr)
            col = self._ac(255, 30, 80, pa//3) if self.muted else self._ac(0, 212, 255, pa)
            c.create_oval(FCX-r, FCY-r, FCX+r, FCY+r, outline=col, width=2, tags="anim")

        # Rings
        for idx, (r_frac, w_ring, arc_l, gap) in enumerate([(0.47,3,110,75), (0.39,2,75,55), (0.31,1,55,38)]):
            ring_r, base_a = int(FW * r_frac), self.rings_spin[idx]
            a_val = max(0, min(255, int(self.halo_a * (1.0 - idx * 0.18))))
            col = self._ac(255, 30, 80, a_val) if self.muted else self._ac(0, 212, 255, a_val)
            for s in range(360 // (arc_l + gap)):
                start = (base_a + s * (arc_l + gap)) % 360
                c.create_arc(FCX-ring_r, FCY-ring_r, FCX+ring_r, FCY+ring_r,
                             start=start, extent=arc_l, outline=col, width=w_ring, style="arc", tags="anim")

        # Scanners
        sr, scan_a = int(FW * 0.49), min(255, int(self.halo_a * 1.4))
        scan_col = self._ac(255, 30, 80, scan_a) if self.muted else self._ac(0, 212, 255, scan_a)
        c.create_arc(FCX-sr, FCY-sr, FCX+sr, FCY+sr, start=self.scan_angle, extent=70 if self.speaking else 42,
                     outline=scan_col, width=3, style="arc", tags="anim")
        c.create_arc(FCX-sr, FCY-sr, FCX+sr, FCY+sr, start=self.scan2_angle, extent=70 if self.speaking else 42,
                     outline=self._ac(255, 100, 0, scan_a//2), width=2, style="arc", tags="anim")

        # Markers
        t_out, t_in, a_mk = int(FW * 0.495), int(FW * 0.472), self._ac(0, 212, 255, 155)
        for deg in range(0, 360, 10):
            rad = math.radians(deg)
            inn = t_in if deg % 30 == 0 else t_in + 5
            c.create_line(FCX + t_out*math.cos(rad), FCY - t_out*math.sin(rad),
                          FCX + inn*math.cos(rad), FCY - inn*math.sin(rad), fill=a_mk, width=1, tags="anim")

        # Crosshair & Body
        ch_r, gap, ch_a = int(FW * 0.50), int(FW * 0.15), self._ac(0, 212, 255, int(self.halo_a * 0.55))
        for x1,y1,x2,y2 in [(FCX-ch_r, FCY, FCX-gap, FCY), (FCX+gap, FCY, FCX+ch_r, FCY),
                            (FCX, FCY-ch_r, FCX, FCY-gap), (FCX, FCY+gap, FCX, FCY+ch_r)]:
            c.create_line(x1, y1, x2, y2, fill=ch_a, width=1, tags="anim")
        
        # Face/Orb
        if self._has_face:
            fw = int(FW * self.scale)
            # Threshold 0.005 -> 0.02 to reduce resize calls
            if self._face_scale_cache is None or abs(self._face_scale_cache[0] - self.scale) > 0.02:
                scaled = self._face_pil.resize((fw, fw), Image.BILINEAR)
                
                # Explicitly delete old PhotoImage to prevent Tkinter memory leak
                if self._face_scale_cache is not None:
                    del self._face_scale_cache
                
                self._face_scale_cache = (self.scale, ImageTk.PhotoImage(scaled))
            c.create_image(FCX, FCY, image=self._face_scale_cache[1], tags="anim")
        else:
            orb_r = int(FW * 0.27 * self.scale)
            orb_color = (255, 30, 80) if self.muted else (0, 65, 120)
            for i in range(7, 0, -1):
                frac = i / 7
                c.create_oval(FCX-int(orb_r*frac), FCY-int(orb_r*frac), FCX+int(orb_r*frac), FCY+int(orb_r*frac),
                               fill=self._ac(int(orb_color[0]*frac), int(orb_color[1]*frac), int(orb_color[2]*frac), 
                                             max(0, min(255, int(self.halo_a*1.1*frac)))), outline="", tags="anim")
            c.create_text(FCX, FCY, text=SYSTEM_NAME, fill=self._ac(0, 212, 255, min(255, int(self.halo_a * 2))),
                          font=("Courier", 14, "bold"), tags="anim")

        # Header/Footer
        HDR = 45
        c.create_rectangle(0, 0, W, HDR, fill="#00080d", outline="", tags="anim")
        c.create_line(0, HDR, W, HDR, fill=C_MID, width=1, tags="anim")
        c.create_text(W//2, 28, text="Just A Rather Very Intelligent System", fill=C_MID, font=("Courier", 9), tags="anim")
        c.create_text(16, 28, text=MODEL_BADGE, fill=C_DIM, font=("Courier", 9), anchor="w", tags="anim")
        c.create_text(W-16, 28, text=time.strftime("%I:%M:%S %p"), fill=C_PRI, font=("Courier", 13, "bold"), anchor="e", tags="anim")

        # Status (Ultra-Scaled)
        sc = C_MUTED if self.muted else (C_ACC if self.speaking else (C_GREEN if self._jarvis_state=="LISTENING" else C_PRI))
        c.create_text(W//2, FCY + FW//2 + 70, text=f"{( '⊘' if self.muted else ('●' if self.status_blink else '○') )} {self.status_text}",
                      fill=sc, font=("Courier", 11, "bold"), tags="anim")

        # Soundwave (Ultra-Scaled)
        wy, N, BH, bw = FCY + FW//2 + 95, 48, 12, 10
        wx0 = (W - N*bw) // 2
        for i in range(N):
            hb = 2 if self.muted else (random.randint(3, BH) if self.speaking else int(3 + 2*math.sin(t*0.08 + i*0.55)))
            col = C_MUTED if self.muted else (C_PRI if self.speaking and hb > BH*0.6 else C_DIM)
            c.create_rectangle(wx0+i*bw, wy+BH-hb, wx0+i*bw+bw-1, wy+BH, fill=col, outline="", tags="anim")

        # Footer Lines
        c.create_rectangle(0, H-22, W, H, fill="#00080d", outline="", tags="anim")
        c.create_line(0, H-22, W, H-22, fill=C_DIM, width=1, tags="anim")
        c.create_text(W-16, H-11, fill=C_DIM, font=("Courier", 7), text="[F4] MUTE", anchor="e", tags="anim")
        c.create_text(W//2, H-11, fill=C_DIM, font=("Courier", 7), text="FatihMakes Industries  ·  MARK XXXV", tags="anim")

    def write_log(self, text: str):
        """Thread-safe way to log to the UI from any module."""
        self.root.after(0, self._write_log_main_thread, text)

    def _write_log_main_thread(self, text: str):
        """Internal handler that runs only on the main Tkinter thread."""
        with self._log_lock:
            # Redirect to side console
            if hasattr(self, 'console_panel'):
                self.console_panel.write_log(text)

            self.typing_queue.append(text)
            tl = text.lower()
            if tl.startswith("you:"): 
                self.set_state("PROCESSING")
            elif tl.startswith("jarvis:") or tl.startswith("ai:"): 
                self.set_state("SPEAKING")
            
            if not self.is_typing: 
                self._start_typing()

    def show_suggestion(self, text: str):
        """Displays a predictive suggestion in the console with a special prefix."""
        msg = f"JARVIS [PREDICTION]: {text}"
        self.write_log(msg)
        # We could also add a visual indicator in the activity feed
        if hasattr(self, "activity_feed"):
            self.activity_feed.append(f"✧ Suggestion: {text[:20]}...")

    def _start_typing(self):
        if not self.typing_queue:
            self.is_typing = False
            if not self.speaking and not self.muted: self.set_state("LISTENING")
            return
        self.is_typing = True
        text = self.typing_queue.popleft()
        tl = text.lower()
        tag = "you" if tl.startswith("you:") else ("ai" if (tl.startswith("jarvis:") or tl.startswith("ai:")) else ("err" if ("error" in tl or "failed" in tl) else "sys"))
        self.log_text.configure(state="normal")
        self._trim_log()
        self._type_char(text, 0, tag)

    def _trim_log(self):
        try:
            lines = int(self.log_text.index('end-1c').split('.')[0])
            if lines > self.MAX_LOG_LINES:
                self.log_text.delete('1.0', f'{lines - self.MAX_LOG_LINES + 1}.0')
        except Exception: pass

    def _type_char(self, text, i, tag):
        if i < len(text):
            self.root.after(0, self._type_char_gui, text, i, tag)
        else:
            self.is_typing = False
            if self.typing_queue: self.root.after(100, self._start_typing)

    def _type_char_gui(self, text, i, tag):
        if i < len(text):
            chunk = text[i:i+3]
            self.log_text.insert(tk.END, chunk, tag)
            self.log_text.see(tk.END)
            self.root.after(25, self._type_char, text, i + len(chunk), tag)
        else: self._type_char(text, i, tag)

    # Compat methods
    def start_speaking(self): self.set_state("SPEAKING")
    def stop_speaking(self): 
        if not self.muted: self.set_state("LISTENING")

    def _api_keys_exist(self): return API_FILE.exists()
    def wait_for_api_key(self):
        while not self._api_key_ready: time.sleep(0.1)

    def _show_setup_ui(self):
        self.setup_frame = tk.Frame(self.root, bg="#00080d", highlightbackground=C_PRI, highlightthickness=1)
        self.setup_frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(self.setup_frame, text="◈  INITIALISATION REQUIRED", fg=C_PRI, bg="#00080d", font=("Courier", 13, "bold")).pack(pady=(18, 4))
        tk.Label(self.setup_frame, text="Enter your Gemini API key to boot J.A.R.V.I.S.", fg=C_MID, bg="#00080d", font=("Courier", 9)).pack(pady=(0, 10))
        self.gemini_entry = tk.Entry(self.setup_frame, width=52, fg=C_TEXT, bg="#000d12", insertbackground=C_TEXT, borderwidth=0, font=("Courier", 10), show="*")
        self.gemini_entry.pack(pady=(0, 4))
        tk.Button(self.setup_frame, text="▸  INITIALISE SYSTEMS", command=self._save_api_keys, bg=C_BG, fg=C_PRI, activebackground="#003344", font=("Courier", 10), borderwidth=0, pady=8).pack(pady=14)

    def _get_config_internal(self):
        try:
            if API_FILE.exists():
                with open(API_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: pass
        return {}

    def _save_api_keys(self):
        gemini = self.gemini_entry.get().strip()
        if not gemini: return
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(API_FILE, "w", encoding="utf-8") as f: json.dump({"gemini_api_key": gemini}, f, indent=4)
        self.setup_frame.destroy()
        self._api_key_ready = True
        self.set_state("LISTENING")
        self.write_log("SYS: Systems initialised. JARVIS online.")
