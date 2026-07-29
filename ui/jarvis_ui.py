import os, time, math, random
import tkinter as tk
from pathlib import Path
from functools import lru_cache

try:
    from core.config import API_CONFIG_PATH as API_FILE
except Exception:
    API_FILE = Path("config/api_keys.json")

C_BG = "#000000"

@lru_cache(maxsize=512)
def _hex_to_rgb(h):
    return tuple(int(h.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))

@lru_cache(maxsize=512)
def _rgb_to_hex_fast(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"

def _rgb_to_hex(r, g, b):
    return _rgb_to_hex_fast(int(r), int(g), int(b))

def _lerp_color(c1, c2, t):
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    return _rgb_to_hex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)

def _blend_to_black(color, alpha):
    r, g, b = _hex_to_rgb(color)
    return _rgb_to_hex(r * alpha, g * alpha, b * alpha)

class Particle:
    def __init__(self):
        self.angle = random.uniform(0, 360)
        self.dist = random.uniform(50, 100)
        self.speed = random.uniform(10, 30)
        self.size = random.uniform(1.0, 2.5)
        self.alpha = 0.0
        self.target_alpha = random.uniform(0.3, 0.8)
        self.dr = random.uniform(-5, 5)

class JarvisUI:
    def __init__(self, face_path=None, size=None):
        self.root = tk.Tk()
        self.root.title("J.A.R.V.I.S")
        self.W, self.H = 240, 240
        self.CX, self.CY = 120, 105
        
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        RX = sw - self.W - 60
        RY = 60
        self.root.geometry(f"{self.W}x{self.H}+{RX}+{RY}")
        self.root.configure(bg=C_BG)
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.current_persona = "jarvis"
        
        try:
            self.root.wm_attributes("-transparentcolor", C_BG)
        except:
            pass

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H, bg=C_BG, highlightthickness=0)
        self.canvas.place(x=0, y=0)
        
        self._jarvis_state = "ONLINE"
        self.speaking = False
        self.muted = False
        self.on_text_command = None
        self.jarvis = None
        
        self.color_map = {
            "ONLINE": "#0088ff",
            "LISTENING": "#00ffff",
            "THINKING": "#aa00ff",
            "SPEAKING": "#e0ffff",
            "MUTED": "#ff3366",
            "ERROR": "#ff0000"
        }
        self.current_color = self.color_map["ONLINE"]
        self.target_color = self.color_map["ONLINE"]
        
        self.scale = 1.0
        self.target_scale = 1.0
        self.rotation_speed = 30.0
        self.base_angles = [0.0, 120.0, 240.0]
        self.time_elapsed = 0.0
        self.last_time = time.time()
        
        # Audio Energy
        self.raw_mic_energy = 0.0
        self.raw_speaker_energy = 0.0
        self.smooth_mic_energy = 0.0
        self.smooth_speaker_energy = 0.0
        
        self.eye_look_x = 0.0
        self.eye_look_y = 0.0
        self.target_look_x = 0.0
        self.target_look_y = 0.0
        self.eye_open = 1.0
        self.eye_scale_w = 1.0
        self.eye_scale_h = 1.0
        self.eye_smile = 0.0
        self.last_blink_time = time.time()
        self.next_blink_delay = random.uniform(4.0, 8.0)
        self.is_blinking = False
        self.blink_phase = 0.0
        self.last_look_time = time.time()
        
        self.particles = [Particle() for _ in range(10)]
        
        self.hover_eye = False
        self.hover_mic = False
        self.mic_scale = 1.0
        self._drag_data = {"x": 0, "y": 0}
        
        self.type_box_visible = False
        self.type_frame = tk.Frame(
            self.root, 
            bg="#00111a", 
            highlightbackground="#0088ff", 
            highlightcolor="#00ffff", 
            highlightthickness=1
        )
        
        self.type_entry = tk.Entry(
            self.type_frame,
            bg="#000d14",
            fg="#00ffff",
            insertbackground="#00ffff",
            relief="flat",
            font=("Segoe UI", 9)
        )
        self.type_entry.pack(side="left", fill="both", expand=True, padx=4, pady=2)
        self.type_entry.bind("<Return>", self._on_type_submit)
        
        self.send_btn = tk.Button(
            self.type_frame,
            text="➔",
            bg="#003344",
            fg="#00ffff",
            activebackground="#005577",
            activeforeground="#ffffff",
            relief="flat",
            font=("Segoe UI", 9, "bold"),
            command=self._on_type_submit
        )
        self.send_btn.pack(side="right", padx=2, pady=2)

        self.canvas.bind("<ButtonPress-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.canvas.bind("<Leave>", self._on_mouse_leave)
        self.root.bind("<Button-3>", self._show_context_menu)
        self.root.bind("<F4>", lambda e: self.set_mute(not self.muted))
        
        self.menu = tk.Menu(self.root, tearoff=0, bg="#00111a", fg="#00d4ff", activebackground="#005577", activeforeground="#ffffff", borderwidth=0)
        self.menu.add_command(label="Type Box: Show", command=self.toggle_type_box)
        
        self.persona_menu = tk.Menu(self.menu, tearoff=0, bg="#00111a", fg="#00d4ff", activebackground="#005577", activeforeground="#ffffff", borderwidth=0)
        self.persona_menu.add_command(label="J.A.R.V.I.S", command=lambda: self.set_theme("jarvis"))
        self.persona_menu.add_command(label="F.R.I.D.A.Y", command=lambda: self.set_theme("friday"))
        self.menu.add_cascade(label="Persona", menu=self.persona_menu)
        
        self.menu.add_command(label="Settings", state="disabled")
        self.menu.add_command(label="Mute / Unmute", command=lambda: self.set_mute(not self.muted))
        self.menu.add_command(label="Restart", state="disabled")
        self.menu.add_command(label="Exit", command=self._exit_app)
        
        self._animate()

    def _api_keys_exist(self): return API_FILE.exists()
    
    def wait_for_api_key(self):
        while not self._api_keys_exist():
            print("Waiting for API key in config/api_keys.json...")
            time.sleep(2)
        return True
        
    def write_log(self, text: str): print(f"[JARVIS LOG] {text}")
    def show_suggestion(self, text: str): print(f"[PROACTIVE SUGGESTION] {text}")
    def open_browser_panel(self, query: str = ""): print(f"[JARVIS LOG] SYS: Opening web search for '{query}'...")
    
    def set_state(self, state: str):
        self._jarvis_state = state
        self.speaking = (state == "SPEAKING")
        if self.muted:
            self.target_color = self.color_map["MUTED"]
        else:
            self.target_color = self.color_map.get(state, self.color_map["ONLINE"])

    def set_theme(self, persona: str):
        self.current_persona = persona
        if persona == "friday":
            self.color_map.update({
                "ONLINE": "#ff3300",
                "LISTENING": "#ff6600",
                "THINKING": "#ff0066",
                "SPEAKING": "#ffcc99",
            })
            self.root.title("F.R.I.D.A.Y")
            try:
                self.menu.config(bg="#1a0a00", fg="#ff6600")
                if hasattr(self, "term_text"):
                    self.term_text.config(bg="#1a0a00", fg="#ff6600", insertbackground="#ff6600")
                if hasattr(self, "term_frame"):
                    self.term_frame.config(bg="#1a0a00", highlightbackground="#ff3300", highlightcolor="#ff6600")
                if hasattr(self, "type_entry"):
                    self.type_entry.config(bg="#1a0a00", fg="#ff6600", insertbackground="#ff6600")
                if hasattr(self, "type_frame"):
                    self.type_frame.config(bg="#1a0a00", highlightbackground="#ff3300", highlightcolor="#ff6600")
            except Exception:
                pass
        else:
            self.color_map.update({
                "ONLINE": "#0088ff",
                "LISTENING": "#00ffff",
                "THINKING": "#aa00ff",
                "SPEAKING": "#e0ffff",
            })
            self.root.title("J.A.R.V.I.S")
            try:
                self.menu.config(bg="#00111a", fg="#00d4ff")
                if hasattr(self, "term_text"):
                    self.term_text.config(bg="#000d14", fg="#00ffff", insertbackground="#00ffff")
                if hasattr(self, "term_frame"):
                    self.term_frame.config(bg="#00111a", highlightbackground="#0088ff", highlightcolor="#00ffff")
                if hasattr(self, "type_entry"):
                    self.type_entry.config(bg="#00111a", fg="#00ffff", insertbackground="#00ffff")
                if hasattr(self, "type_frame"):
                    self.type_frame.config(bg="#00111a", highlightbackground="#0088ff", highlightcolor="#00ffff")
            except Exception:
                pass
        self.set_state(self._jarvis_state)

    def start_speaking(self): self.set_state("SPEAKING")
    def stop_speaking(self): self.set_state("ONLINE")
    
    def set_mic_energy(self, energy):
        self.raw_mic_energy = energy

    def set_speaker_energy(self, energy):
        self.raw_speaker_energy = energy
    
    def set_mute(self, is_muted: bool):
        self.muted = is_muted
        if self.muted:
            self.set_state("MUTED")
            self.write_log("SYS: Microphone muted.")
        else:
            self.set_state("LISTENING")
            self.write_log("SYS: Microphone active.")

    def _exit_app(self):
        if self.jarvis and hasattr(self.jarvis, "shutdown"):
            try:
                self.jarvis.shutdown()
            except Exception as e:
                print(f"[JARVIS UI] Shutdown error: {e}")
        self.root.destroy()
        os._exit(0)

    def _show_context_menu(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def toggle_type_box(self):
        if self.type_box_visible:
            self.hide_type_box()
        else:
            self.show_type_box()

    def show_type_box(self):
        self.type_box_visible = True
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f"{self.W}x{self.H + 40}+{x}+{y}")
        self.type_frame.place(x=10, y=self.H + 5, width=self.W - 20, height=30)
        self.type_entry.focus_set()
        try:
            self.menu.entryconfigure(0, label="Type Box: Hide")
        except Exception:
            pass

    def hide_type_box(self):
        self.type_box_visible = False
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.type_frame.place_forget()
        self.root.geometry(f"{self.W}x{self.H}+{x}+{y}")
        try:
            self.menu.entryconfigure(0, label="Type Box: Show")
        except Exception:
            pass

    def _on_type_submit(self, event=None):
        text = self.type_entry.get().strip()
        if text:
            self.write_log(f"You (typed): {text}")
            self.type_entry.delete(0, tk.END)
            if self.on_text_command:
                self.on_text_command(text)

    def _on_mouse_move(self, event):
        dx_eye = event.x - self.CX
        dy_eye = event.y - self.CY
        self.hover_eye = ((dx_eye * dx_eye + dy_eye * dy_eye) < (65 * 65))
        
        dx_mic = event.x - self.CX
        dy_mic = event.y - 210
        self.hover_mic = ((dx_mic * dx_mic + dy_mic * dy_mic) < (20 * 20))

    def _on_mouse_leave(self, event):
        self.hover_eye = False
        self.hover_mic = False

    def _on_click(self, event):
        if self.hover_mic:
            self.set_mute(not self.muted)
            self.mic_scale = 0.7 
        else:
            self._drag_data["x"] = event.x_root - self.root.winfo_x()
            self._drag_data["y"] = event.y_root - self.root.winfo_y()

    def _on_drag(self, event):
        if not self.hover_mic:
            x = event.x_root - self._drag_data["x"]
            y = event.y_root - self._drag_data["y"]
            self.root.geometry(f"+{x}+{y}")

    def _update_physics(self, dt):
        self.time_elapsed += dt
        
        # Smooth Audio Energy
        self.smooth_mic_energy += (self.raw_mic_energy - self.smooth_mic_energy) * dt * 15.0
        self.smooth_speaker_energy += (self.raw_speaker_energy - self.smooth_speaker_energy) * dt * 15.0
        
        # Decay the raw values quickly so they fall back to 0 when audio stops
        self.raw_mic_energy *= max(0, 1.0 - dt * 10.0)
        self.raw_speaker_energy *= max(0, 1.0 - dt * 10.0)
        
        self.current_color = _lerp_color(self.current_color, self.target_color, min(1.0, dt * 5.0))
        state = self._jarvis_state if not self.muted else "MUTED"
        
        base_scale = 1.0
        if self.hover_eye: base_scale = 1.05
        
        now = time.time()
        
        if not self.is_blinking and (now - self.last_blink_time > self.next_blink_delay):
            self.is_blinking = True
            self.blink_phase = -1.0
            
        target_open = 1.0
        if state == "MUTED":
            target_open = 0.5
        elif state == "ERROR":
            target_open = 0.8
            
        if self.is_blinking:
            self.blink_phase += dt * 15.0
            if self.blink_phase < 0:
                target_open = 0.1
            else:
                target_open = 1.0
                if self.blink_phase > 1.0:
                    self.is_blinking = False
                    self.last_blink_time = now
                    self.next_blink_delay = random.uniform(4.0, 8.0)
                    
        self.eye_open += (target_open - self.eye_open) * dt * 25.0
        
        if state == "THINKING":
            self.target_look_y = -8.0
            self.target_look_x = math.sin(self.time_elapsed * 2.0) * 5.0
        elif state == "LISTENING":
            self.target_look_x = 0.0
            self.target_look_y = 0.0
        else:
            if now - self.last_look_time > random.uniform(2.0, 5.0):
                self.target_look_x = random.uniform(-6.0, 6.0)
                self.target_look_y = random.uniform(-4.0, 4.0)
                self.last_look_time = now
                
        if state == "SPEAKING":
            jitter_y = math.sin(self.time_elapsed * 40.0) * 1.5
            self.target_look_y = jitter_y
            
        target_scale_w = 1.0
        target_scale_h = 1.0
        target_smile = 0.0
        
        if state == "THINKING":
            target_scale_w = 0.8
            target_scale_h = 0.7
        elif state == "LISTENING":
            target_scale_w = 1.2
            target_scale_h = 1.2
            
        if self.hover_eye:
            target_smile = 1.0
            
        self.eye_scale_w += (target_scale_w - self.eye_scale_w) * dt * 10.0
        self.eye_scale_h += (target_scale_h - self.eye_scale_h) * dt * 10.0
        self.eye_smile += (target_smile - self.eye_smile) * dt * 15.0
        
        self.eye_look_x += (self.target_look_x - self.eye_look_x) * dt * 8.0
        self.eye_look_y += (self.target_look_y - self.eye_look_y) * dt * 8.0
        
        if state == "SPEAKING":
            self.rotation_speed = 80.0
            self.target_scale = base_scale + (self.smooth_speaker_energy * 0.8)
        elif state == "THINKING":
            self.rotation_speed = 120.0
            self.target_scale = base_scale
        elif state == "LISTENING":
            self.rotation_speed = 60.0
            self.target_scale = base_scale + (self.smooth_mic_energy * 0.6)
        elif state == "ERROR":
            self.rotation_speed = random.uniform(-150.0, 150.0)
            self.target_scale = base_scale
        else:
            self.rotation_speed = 20.0
            self.target_scale = base_scale + math.sin(self.time_elapsed * 2.0) * 0.02
            
        self.scale += (self.target_scale - self.scale) * dt * 6.0
        
        for i in range(len(self.base_angles)):
            mult = 1.0 if i % 2 == 0 else -1.5
            self.base_angles[i] = (self.base_angles[i] + self.rotation_speed * mult * dt) % 360
            
        for p in self.particles:
            p.angle = (p.angle + p.speed * dt) % 360
            p.dist += p.dr * dt
            if p.dist > 90 or p.dist < 60: p.dr *= -1
            
            if random.random() < 0.01:
                p.target_alpha = random.uniform(0.1, 0.8) if random.random() > 0.3 else 0.0
            p.alpha += (p.target_alpha - p.alpha) * dt * 2.0
            
        target_mic = 1.2 if self.hover_mic else 1.0
        self.mic_scale += (target_mic - self.mic_scale) * dt * 12.0

    def _draw(self):
        c = self.canvas
        c.delete("all")
        CX, CY = self.CX, self.CY
        base_r = 65 * self.scale
        
        part_col = _blend_to_black(self.current_color, 1.0)
        for p in self.particles:
            if p.alpha > 0.05:
                rad = math.radians(p.angle)
                px = CX + p.dist * math.cos(rad)
                py = CY + p.dist * math.sin(rad)
                fill_c = _blend_to_black(part_col, p.alpha)
                c.create_oval(px-p.size, py-p.size, px+p.size, py+p.size, fill=fill_c, outline="")
        
        ring_r = base_r + 4
        bloom_layers = 4
        for i in range(bloom_layers):
            r = ring_r + (i * 3)
            alpha = (1.0 - i/bloom_layers) * 0.4
            if self.hover_eye: alpha *= 1.2
            col = _blend_to_black(self.current_color, alpha)
            c.create_oval(CX-r, CY-r, CX+r, CY+r, outline=col, width=2)
            
        is_friday = getattr(self, "current_persona", "jarvis") == "friday"
        
        arcs = []
        if is_friday:
            # Friday has sharper, faster looking arcs with different gaps
            arcs = [
                (1.0, 2, 90, 30, self.base_angles[0]),
                (1.08, 3, 40, 20, self.base_angles[1] * -1.5),
                (1.15, 1, 15, 15, self.base_angles[2] * 2.0)
            ]
        else:
            arcs = [
                (1.0, 3, 140, 40, self.base_angles[0]),
                (1.05, 2, 80, 40, self.base_angles[1]),
                (1.12, 1, 40, 80, self.base_angles[2])
            ]
            
        arc_col = _blend_to_black(self.current_color, 0.9)
        for r_mult, width, extent, gap, angle in arcs:
            r = base_r * r_mult
            for s in range(360 // (extent + gap)):
                start = (angle + s * (extent + gap)) % 360
                c.create_arc(CX-r, CY-r, CX+r, CY+r, start=start, extent=extent, outline=arc_col, width=width, style="arc")
                
        c.create_oval(CX-base_r, CY-base_r, CX+base_r, CY+base_r, fill="#050505", outline="")
        c.create_oval(CX-base_r+1, CY-base_r+1, CX+base_r-1, CY+base_r-1, outline=_blend_to_black(self.current_color, 0.3), width=2)
        
        eye_w = 7 * self.eye_scale_w
        eye_h = 16 * max(0.1, self.eye_open) * self.eye_scale_h
        eye_spacing = 16
        
        if is_friday:
            # Friday has sharper, narrower eyes
            eye_w = 5 * self.eye_scale_w
            eye_h = 18 * max(0.1, self.eye_open) * self.eye_scale_h
            
        ex = CX + self.eye_look_x
        ey = CY + self.eye_look_y
        
        eye_color = "#ffffff"
        if is_friday:
            eye_color = "#ffeecc" # Slight warm tint for Friday
            
        if self._jarvis_state == "ERROR": eye_color = "#ffdddd"
        elif self.muted: eye_color = "#ffcccc"
        
        c.create_oval(ex - eye_spacing - eye_w, ey - eye_h, ex - eye_spacing + eye_w, ey + eye_h, fill=eye_color, outline="")
        c.create_oval(ex + eye_spacing - eye_w, ey - eye_h, ex + eye_spacing + eye_w, ey + eye_h, fill=eye_color, outline="")
        
        # Emotional Smile Cutout
        if self.eye_smile > 0.01:
            cut_y = ey + eye_h - (self.eye_smile * eye_h * 1.2)
            c.create_oval(ex - eye_spacing - eye_w*1.5, cut_y, ex - eye_spacing + eye_w*1.5, cut_y + eye_h*2, fill="#050505", outline="")
            c.create_oval(ex + eye_spacing - eye_w*1.5, cut_y, ex + eye_spacing + eye_w*1.5, cut_y + eye_h*2, fill="#050505", outline="")
        

        MX, MY = self.CX, 210
        MR = 15 * self.mic_scale
        mic_alpha = 0.8 if self.hover_mic else 0.3
        
        if self.muted:
            mic_fill = _blend_to_black("#ff3366", mic_alpha)
            mic_out = "#ff3366"
        else:
            mic_fill = _blend_to_black(self.current_color, mic_alpha)
            mic_out = _blend_to_black(self.current_color, 0.8)
            
        c.create_oval(MX-MR, MY-MR, MX+MR, MY+MR, fill=mic_fill, outline=mic_out, width=2)
        
        icon_col = "#ffffff" if self.hover_mic else _blend_to_black("#ffffff", 0.7)
        if self.muted: icon_col = "#ffaaaa"
        
        mw, mh = 3, 6
        c.create_oval(MX-mw, MY-mh-2, MX+mw, MY+mh-4, fill=icon_col, outline="") 
        c.create_arc(MX-mw-2, MY-2, MX+mw+2, MY+6, start=180, extent=180, outline=icon_col, width=1.5, style="arc") 
        c.create_line(MX, MY+6, MX, MY+9, fill=icon_col, width=1.5) 
        c.create_line(MX-3, MY+9, MX+3, MY+9, fill=icon_col, width=1.5) 

    def _animate(self):
        now = time.time()
        dt = now - self.last_time
        self.last_time = now
        if dt > 0.1: dt = 0.1 
        
        self._update_physics(dt)
        self._draw()
        
        state = self._jarvis_state if not self.muted else "MUTED"
        fps_map = {
            "SPEAKING": 16,
            "LISTENING": 16,
            "THINKING": 20,
            "ONLINE": 22,
            "IDLE": 22,
            "MUTED": 22,
            "ERROR": 20
        }
        delay = fps_map.get(state, 22)
        self.root.after(delay, self._animate)

if __name__ == "__main__":
    ui = JarvisUI()
    ui.root.mainloop()
