# actions/jarvis_web_server.py
# ══════════════════════════════════════════════════════════════
# JARVIS LAN Web Server
# Access JARVIS from any browser on your local network
# Works on: phone, tablet, second PC — anything with a browser
#
# pip install flask flask-socketio
#
# How to use:
#   1. Add to main.py (see INTEGRATION section at bottom)
#   2. Run JARVIS normally
#   3. Console will show: [WebServer] http://192.168.x.x:5001
#   4. Open that URL on your phone browser
#   5. Tap "Start" — speak — JARVIS responds
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import base64
import threading
import socket
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────
# HTML page served to browser
# Uses Silero VAD (ONNX) running IN the browser —
# only confirmed speech is sent, NOT raw continuous audio
# ─────────────────────────────────────────────────────────────
_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JARVIS Remote</title>
  <style>
    :root { --bg: #0a0a0f; --card: #1a1a24; --cyan: #00d4ff;
            --green: #00ff88; --red: #ff4444; --text: #e2e8f0; --muted: #64748b; }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: var(--bg); color: var(--text);
           font-family: 'Segoe UI', monospace; min-height: 100vh;
           display: flex; flex-direction: column; align-items: center;
           padding: 24px 16px; }
    h1   { font-size: 28px; color: var(--cyan); margin-bottom: 6px; }
    .sub { color: var(--muted); font-size: 13px; margin-bottom: 28px; }

    .status-dot { width: 10px; height: 10px; border-radius: 50%;
                  background: var(--muted); display: inline-block;
                  margin-right: 8px; transition: background 0.3s; }
    .status-dot.connected  { background: var(--green); }
    .status-dot.listening  { background: var(--cyan); animation: pulse 1s infinite; }
    .status-dot.processing { background: orange; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }

    #statusText { font-size: 15px; color: var(--text); margin-bottom: 20px; }

    #toggleBtn {
      padding: 14px 36px; border-radius: 50px; border: none; cursor: pointer;
      font-size: 16px; font-weight: 700; transition: all 0.2s;
      background: var(--cyan); color: #000; margin-bottom: 28px;
    }
    #toggleBtn:disabled { background: var(--muted); cursor: not-allowed; }
    #toggleBtn.active   { background: var(--red); color: #fff; }

    #log {
      width: 100%; max-width: 520px; height: 320px;
      overflow-y: auto; background: var(--card);
      border-radius: 12px; padding: 14px 16px;
      font-size: 13px; line-height: 1.7;
      border: 1px solid #2a2a3a;
    }
    .log-jarvis { color: var(--cyan); }
    .log-you    { color: var(--green); }
    .log-sys    { color: var(--muted); font-style: italic; }
    .log-err    { color: var(--red); }

    #input-row { display: flex; gap: 8px; width: 100%; max-width: 520px; margin-top: 12px; }
    #textInput  { flex: 1; padding: 10px 14px; border-radius: 10px;
                  background: var(--card); border: 1px solid #2a2a3a;
                  color: var(--text); font-size: 14px; outline: none; }
    #sendBtn    { padding: 10px 20px; border-radius: 10px; background: var(--cyan);
                  color: #000; border: none; font-weight: 700; cursor: pointer; }
  </style>
</head>
<body>
  <h1>J.A.R.V.I.S</h1>
  <div class="sub">Remote Access Mode</div>

  <div id="statusText">
    <span class="status-dot" id="dot"></span>
    <span id="statusMsg">Connecting...</span>
  </div>

  <button id="toggleBtn" disabled onclick="toggleMic()">Start Listening</button>

  <div id="log"><div class="log-sys">Waiting for connection...</div></div>

  <div id="input-row">
    <input id="textInput" type="text" placeholder="Type a command..." />
    <button id="sendBtn" onclick="sendText()">Send</button>
  </div>

  <!-- Socket.IO -->
  <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
  <!-- Silero VAD (browser-side voice activity detection) -->
  <script src="https://cdn.jsdelivr.net/npm/onnxruntime-web/dist/ort.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/@ricky0123/vad-web@0.0.7/dist/bundle.min.js"></script>

  <script>
    const socket = io();
    let myvad    = null;
    let isActive = false;
    const log    = document.getElementById('log');
    const dot    = document.getElementById('dot');
    const msg    = document.getElementById('statusMsg');
    const btn    = document.getElementById('toggleBtn');

    function addLog(text, cls) {
      const div = document.createElement('div');
      div.className = cls || '';
      div.textContent = text;
      log.appendChild(div);
      log.scrollTop = log.scrollHeight;
    }

    // ── Socket events ──────────────────────────────────────
    socket.on('connect', () => {
      dot.className = 'status-dot connected';
      msg.textContent = 'Connected ✓';
      btn.disabled = false;
      addLog('Connected to JARVIS.', 'log-sys');
    });

    socket.on('disconnect', () => {
      dot.className = 'status-dot';
      msg.textContent = 'Disconnected — refresh to reconnect';
      btn.disabled = true;
      addLog('Disconnected.', 'log-err');
    });

    socket.on('jarvis_reply', (data) => {
      dot.className = 'status-dot connected';
      msg.textContent = 'Ready';
      addLog('JARVIS: ' + data, 'log-jarvis');
    });

    socket.on('transcription', (text) => {
      addLog('You: ' + text, 'log-you');
      dot.className = 'status-dot processing';
      msg.textContent = 'Processing...';
    });

    socket.on('error_msg', (err) => {
      addLog('Error: ' + err, 'log-err');
    });

    // ── Mic toggle ─────────────────────────────────────────
    async function toggleMic() {
      if (!isActive) {
        await startVAD();
      } else {
        stopVAD();
      }
    }

    async function startVAD() {
      try {
        addLog('Starting microphone...', 'log-sys');
        myvad = await vad.MicVAD.new({
          positiveSpeechThreshold:  0.8,
          negativeSpeechThreshold:  0.65,
          minSpeechFrames:          3,
          preSpeechPadFrames:       2,
          redemptionFrames:         3,
          onSpeechStart: () => {
            dot.className = 'status-dot listening';
            msg.textContent = 'Listening...';
          },
          onSpeechEnd: (audio) => {
            // Encode to WAV and send — only confirmed speech, not raw stream
            const wavBytes = vad.utils.encodeWAV(audio);
            const b64      = vad.utils.arrayBufferToBase64(wavBytes);
            socket.emit('voice_input', b64);
            addLog('→ Voice sent to JARVIS', 'log-sys');
          },
          onVADMisfire: () => {
            dot.className = 'status-dot connected';
            msg.textContent = 'Ready';
          }
        });
        myvad.start();
        isActive = true;
        btn.textContent = 'Stop Listening';
        btn.classList.add('active');
        dot.className = 'status-dot connected';
        msg.textContent = 'Listening (VAD active)';
        addLog('Voice detection active. Speak clearly.', 'log-sys');
      } catch (err) {
        addLog('Mic error: ' + err.message, 'log-err');
        console.error(err);
      }
    }

    function stopVAD() {
      if (myvad) { myvad.pause(); myvad = null; }
      isActive = false;
      btn.textContent = 'Start Listening';
      btn.classList.remove('active');
      dot.className = 'status-dot connected';
      msg.textContent = 'Ready';
      addLog('Voice detection stopped.', 'log-sys');
    }

    // ── Text input ─────────────────────────────────────────
    function sendText() {
      const input = document.getElementById('textInput');
      const text  = input.value.trim();
      if (!text) return;
      socket.emit('text_input', text);
      addLog('You (text): ' + text, 'log-you');
      input.value = '';
    }
    document.getElementById('textInput').addEventListener('keydown', e => {
      if (e.key === 'Enter') sendText();
    });
  </script>
</body>
</html>
"""


# ─────────────────────────────────────────────────────────────
# Server
# ─────────────────────────────────────────────────────────────

_jarvis_ref = None
_server_thread: Optional[threading.Thread] = None


def _get_local_ip() -> str:
    """Get machine's LAN IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


def start_web_server(jarvis_instance, port: int = 5001) -> None:
    """
    Start the JARVIS LAN web server.
    Call this from main.py after JARVIS initializes.

    Parameters
    ----------
    jarvis_instance : the JarvisLive instance (self in main.py)
    port            : port to listen on (default 5001)
    """
    global _jarvis_ref, _server_thread
    _jarvis_ref = jarvis_instance

    try:
        from flask import Flask, render_template_string
        from flask_socketio import SocketIO, emit
    except ImportError:
        print("[WebServer] flask/flask-socketio not installed.")
        print("           Run: pip install flask flask-socketio")
        return

    app       = Flask(__name__)
    socketio  = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

    @app.route("/")
    def index():
        return render_template_string(_HTML)

    @socketio.on("voice_input")
    def handle_voice(data):
        """Receive base64 WAV from browser VAD → transcribe → JARVIS."""
        try:
            audio_bytes = base64.b64decode(data)

            # Route through Whisper fallback transcription
            if (_jarvis_ref is not None
                    and hasattr(_jarvis_ref, "whisper_fb")
                    and _jarvis_ref.whisper_fb.is_ready):
                import numpy as np
                # base64 WAV → skip 44-byte WAV header → int16 numpy
                raw_pcm = audio_bytes[44:]
                audio   = np.frombuffer(raw_pcm, dtype=np.int16)
                text    = _jarvis_ref.whisper_fb.transcribe(audio)

                if text and text.strip():
                    emit("transcription", text)
                    # Route command to JARVIS
                    if hasattr(_jarvis_ref, "_on_text_command"):
                        _jarvis_ref._on_text_command(text)
                    else:
                        emit("error_msg", "JARVIS command handler not found")
                else:
                    emit("error_msg", "Could not transcribe audio — try speaking more clearly")
            else:
                emit("error_msg",
                     "Whisper fallback not ready yet — please wait a moment")
        except Exception as e:
            emit("error_msg", f"Server error: {str(e)[:100]}")

    @socketio.on("text_input")
    def handle_text(text: str):
        """Receive typed text command from browser → JARVIS."""
        if not text or not text.strip():
            return
        if _jarvis_ref and hasattr(_jarvis_ref, "_on_text_command"):
            _jarvis_ref._on_text_command(text.strip())
            emit("transcription", text.strip())
        else:
            emit("error_msg", "JARVIS not ready")

    def _run_server():
        local_ip = _get_local_ip()
        print(f"\n[WebServer] ✓ JARVIS web access ready!")
        print(f"[WebServer]   Local  : http://localhost:{port}")
        print(f"[WebServer]   Network: http://{local_ip}:{port}")
        print(f"[WebServer]   Open this on your phone/tablet ^\n")
        socketio.run(app, host="0.0.0.0", port=port, log_output=False)

    _server_thread = threading.Thread(target=_run_server, daemon=True)
    _server_thread.start()


# ══════════════════════════════════════════════════════════════
# INTEGRATION — Add to main.py
# ══════════════════════════════════════════════════════════════
"""
HOW TO ADD TO main.py:
══════════════════════════════════════════════════════

1. In JarvisLive.__init__() — after all other init code:

    # Optional: Start LAN web server
    web_enabled = config.get("web_server_enabled", False)
    if web_enabled:
        from actions.jarvis_web_server import start_web_server
        web_port = config.get("web_server_port", 5001)
        start_web_server(self, port=web_port)

2. In config/settings.json add:
    "web_server_enabled": true,
    "web_server_port": 5001

OR just call directly (always on):
    from actions.jarvis_web_server import start_web_server
    start_web_server(self, port=5001)

3. For reply back to browser, in _process_response() or wherever
   JARVIS generates text responses, add:
    try:
        from actions.jarvis_web_server import _socketio
        if _socketio:
            _socketio.emit('jarvis_reply', response_text)
    except Exception:
        pass
"""
