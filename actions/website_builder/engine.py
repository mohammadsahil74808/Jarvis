# actions/website_builder/engine.py
# ══════════════════════════════════════════════════════════════
# JARVIS Website Builder — Project Engine
# Handles: folder creation, npm install, dev server,
#          error fixing, deployment
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import os
import re
import json
import time
import shutil
import signal
import subprocess
import threading
import webbrowser
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

from .brain   import WebsitePlan, STACK_PROFILES
from .codegen import CodeGenerator
from core.ai_router import get_ai_router
from core.config import get_desktop_path

# ── Where projects are saved ───────────────────────────────────
def _projects_dir() -> Path:
    p = get_desktop_path() / "JARVIS_Websites"
    p.mkdir(parents=True, exist_ok=True)
    return p

# ── Subprocess helper ──────────────────────────────────────────
def _run(cmd: list[str], cwd: Path, timeout: int = 300,
         env: dict = None) -> tuple[int, str, str]:
    """Run a command, return (returncode, stdout, stderr)."""
    merged_env = {**os.environ, **(env or {})}
    try:
        result = subprocess.run(
            cmd, cwd=str(cwd), capture_output=True,
            text=True, timeout=timeout, env=merged_env, shell=False
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout expired"
    except FileNotFoundError as e:
        return -1, "", str(e)


class WebsiteEngine:
    """
    Full project lifecycle manager.
    Creates, builds, runs, and optionally deploys.
    """

    def __init__(self, log_callback: Optional[Callable] = None, widget = None):
        self.gen        = CodeGenerator()
        self.router     = get_ai_router()
        self._log_cb    = log_callback or print
        self.widget     = widget
        self._server_proc: Optional[subprocess.Popen] = None
        self._server_port = 3000

    # ─────────────────────────────────────────────────────────
    def log(self, msg: str, level: str = "INFO"):
        ts  = datetime.now().strftime("%H:%M:%S")
        tag = {"INFO": "●", "OK": "✓", "ERR": "✗", "WARN": "⚠"}.get(level, "●")
        formatted = f"[{ts}] {tag} {msg}"
        self._log_cb(formatted)
        if self.widget:
            w_tag = {"INFO": "info", "OK": "ok", "ERR": "err", "WARN": "warn"}.get(level, "info")
            self.widget.log(msg, w_tag)

    # ─────────────────────────────────────────────────────────
    # STEP 1: Create project folder & all files
    # ─────────────────────────────────────────────────────────

    def scaffold(self, plan: WebsitePlan) -> Path:
        """
        Create complete project from scratch.
        Returns project folder path.
        """
        # Create unique folder name
        slug      = re.sub(r"[^a-z0-9]", "-", plan.site_name.lower()).strip("-")[:40].strip("-")
        timestamp = datetime.now().strftime("%m%d_%H%M")
        proj_dir  = _projects_dir() / f"{slug}_{timestamp}"
        proj_dir.mkdir(parents=True, exist_ok=True)
        if self.widget: self.widget.update_phase("SCAFFOLD")
        
        # Open in VS Code immediately so user can see it
        try:
            subprocess.run(["code", str(proj_dir)], shell=False)
            self.log("Opening VS Code for real-time visualization...", "OK")
        except Exception:
            pass

        self.log(f"Project folder: {proj_dir}")

        stack     = plan.get_stack()
        framework = stack["framework"]

        # ── Generate and write all files ──────────────────────
        self.log("Generating code with AI...")

        # 1. package.json
        self._write(proj_dir / "package.json",
                    self.gen.gen_package_json(plan))

        # 2. Config files
        if framework in ("react",):
            self._write(proj_dir / "vite.config.js",
                        self.gen.gen_vite_config(plan))
            self._write(proj_dir / "index.html",
                        self._gen_index_html(plan))
        else:
            self._write(proj_dir / "next.config.js",
                        self.gen.gen_next_config(plan))

        # 3. Tailwind + PostCSS
        self._write(proj_dir / "tailwind.config.js",
                    self.gen.gen_tailwind_config(plan))
        self._write(proj_dir / "postcss.config.js",
                    "module.exports = { plugins: { tailwindcss: {}, autoprefixer: {} } }")

        # 4. .env.example
        self._write(proj_dir / ".env.example",
                    self.gen.gen_env_example(plan))
        if plan.has_auth or plan.has_db:
            self._write(proj_dir / ".env.local",
                        self.gen.gen_env_example(plan))

        # 5. .gitignore
        self._write(proj_dir / ".gitignore",
                    "node_modules/\n.next/\n.env.local\ndist/\nbuild/\n.DS_Store\n")

        # 6. README
        self._write(proj_dir / "README.md",
                    self.gen.gen_readme(plan))

        # 7. Source files
        src_dir = self._create_src_structure(proj_dir, plan)

        # 8. Global CSS
        css_path = (src_dir / "globals.css" if framework == "nextjs"
                    else src_dir / "index.css")
        self._write(css_path, self.gen.gen_global_css(plan))

        # 9. Main app code
        self.log("Generating main page...")
        app_code = self.gen.gen_main_app(plan)
        ext       = "tsx" if framework == "nextjs" else "jsx"

        if framework == "nextjs":
            app_dir = proj_dir / "app"
            app_dir.mkdir(exist_ok=True)
            self._write(app_dir / f"page.{ext}", app_code)
            self._write(app_dir / f"layout.{ext}",
                        self._gen_layout(plan))
        else:
            self._write(src_dir / f"App.{ext}", app_code)
            self._write(src_dir / "main.jsx", self._gen_main_jsx(plan))

        # 10. Components
        self.log("Generating components...")
        components_dir = (proj_dir / "app" / "components"
                          if framework == "nextjs"
                          else src_dir / "components")
        components_dir.mkdir(parents=True, exist_ok=True)
        for fname, code in self.gen.gen_components(plan).items():
            self._write(components_dir / fname, code)

        # 11. 3D scene if needed
        if plan.has_3d:
            self.log("Generating 3D scene...")
            scene_code = self.gen.gen_3d_scene(plan)
            self._write(components_dir / "Scene3D.jsx", scene_code)

        # 12. Public folder
        (proj_dir / "public").mkdir(exist_ok=True)
        self._write(proj_dir / "public" / ".gitkeep", "")

        # 13. Save plan as JSON (for future improvements)
        self._write(proj_dir / ".jarvis_plan.json", plan.to_json())

        self.log(f"Scaffold complete — {sum(1 for _ in proj_dir.rglob('*') if _.is_file())} files created", "OK")
        return proj_dir

    # ─────────────────────────────────────────────────────────
    # STEP 2: Install dependencies
    # ─────────────────────────────────────────────────────────

    def install(self, proj_dir: Path) -> bool:
        """npm install — returns True on success."""
        if self.widget: self.widget.update_phase("INSTALL")
        self.log("Installing dependencies (may take 1-2 minutes)...")

        # Check if npm is available
        code, _, err = _run(["npm", "--version"], proj_dir, timeout=10)
        if code != 0:
            self.log("npm not found — install Node.js first", "ERR")
            return False

        code, out, err = _run(
            ["npm", "install", "--legacy-peer-deps"],
            proj_dir,
            timeout=300
        )

        if code == 0:
            self.log("Dependencies installed", "OK")
            return True
        else:
            self.log(f"npm install warning (proceeding): {err[:200]}", "WARN")
            # Try to auto-fix common issues
            return self._fix_install(proj_dir, err)

    def _fix_install(self, proj_dir: Path, error: str) -> bool:
        """Auto-fix install errors."""
        # Peer dependency issues — force install
        code, _, _ = _run(
            ["npm", "install", "--force"],
            proj_dir, timeout=300
        )
        if code == 0:
            self.log("Fixed: force install succeeded", "OK")
            return True

        self.log("Install failed — asking AI to fix package.json", "WARN")
        try:
            pkg_path = proj_dir / "package.json"
            pkg_text = pkg_path.read_text()

            resp    = self.router.generate(
                prompt=f"""Fix this package.json to resolve npm install errors.
Error: {error[:500]}
Current package.json:
{pkg_text}
Return ONLY the fixed package.json JSON. No markdown."""
            )
            fixed = resp.strip().replace("```json", "").replace("```", "").strip()
            json.loads(fixed)  # Validate
            pkg_path.write_text(fixed, encoding="utf-8")

            code, _, _ = _run(["npm", "install", "--legacy-peer-deps"],
                               proj_dir, timeout=300)
            return code == 0
        except Exception as e:
            self.log(f"Auto-fix failed: {e}", "ERR")
            return False

    # ─────────────────────────────────────────────────────────
    # STEP 3: Build check
    # ─────────────────────────────────────────────────────────

    def build_check(self, proj_dir: Path, plan: WebsitePlan,
                    max_attempts: int = 3) -> bool:
        """
        Try to build. If errors, ask AI to fix and retry.
        Returns True if build passes.
        """
        framework = plan.get_stack()["framework"]
        build_cmd = (["npm", "run", "build"]
                     if framework != "react"
                     else ["npm", "run", "build"])

        for attempt in range(1, max_attempts + 1):
            if self.widget: self.widget.update_phase("BUILD")
            self.log(f"Build check attempt {attempt}/{max_attempts}...")
            code, out, err = _run(build_cmd, proj_dir, timeout=180)

            if code == 0:
                self.log("Build passed ✓", "OK")
                return True

            error_text = (err + "\n" + out)[-2000:]
            self.log(f"Build error: {error_text[:300]}", "WARN")

            if attempt < max_attempts:
                self.log("AI fixing build errors...")
                self._ai_fix_build(proj_dir, error_text, plan)
                time.sleep(1)

        self.log("Build check failed after retries — dev server may still work", "WARN")
        return False  # Non-fatal — dev mode often works even if build fails

    def _ai_fix_build(self, proj_dir: Path, error: str,
                      plan: WebsitePlan):
        """Ask Gemini to fix build errors by patching source files."""
        try:
            # Find the most likely problematic file from error
            file_match = re.search(r"([\w/\\.-]+\.[jt]sx?)", error)
            if not file_match:
                return

            rel_path = file_match.group(1).replace("./", "")
            # Search for file in project
            candidates = list(proj_dir.rglob(Path(rel_path).name))
            if not candidates:
                return

            target_file = candidates[0]
            original    = target_file.read_text(encoding="utf-8", errors="ignore")

            resp   = self.router.generate(
                prompt=f"""Fix this {target_file.suffix} file to resolve build errors.

Build error:
{error[:1000]}

Current file content:
{original[:3000]}

Return ONLY the complete fixed file content. No markdown fences. No explanations."""
            )

            fixed = resp.strip()
            # Strip fences if present
            fixed = re.sub(r"```[a-z]*\n?", "", fixed).strip()

            # Backup original
            backup = target_file.with_suffix(target_file.suffix + ".bak")
            shutil.copy2(target_file, backup)

            target_file.write_text(fixed, encoding="utf-8")
            self.log(f"Auto-fixed: {target_file.name}")
        except Exception as e:
            self.log(f"AI fix attempt failed: {e}", "WARN")

    # ─────────────────────────────────────────────────────────
    # STEP 4: Run dev server
    # ─────────────────────────────────────────────────────────

    def start_dev_server(self, proj_dir: Path,
                         plan: WebsitePlan) -> str:
        """
        Start dev server in background.
        Returns the localhost URL.
        """
        if self.widget: self.widget.update_phase("PREVIEW")
        framework = plan.get_stack()["framework"]
        port      = self._find_free_port()
        self._server_port = port

        cmd = (["npm", "run", "dev", "--", f"--port={port}"]
               if framework in ("react",)
               else ["npm", "run", "dev", "--",
                     f"-p", str(port)])

        self.log(f"Starting dev server on port {port}...")

        env = {**os.environ, "PORT": str(port), "BROWSER": "none"}
        self._server_proc = subprocess.Popen(
            cmd, cwd=str(proj_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            text=True,
            shell=False
        )

        # Wait for server to be ready
        url = f"http://localhost:{port}"
        if self._wait_for_server(url, timeout=45):
            self.log(f"Dev server ready: {url}", "OK")
            # Open in browser
            webbrowser.open(url)
            return url
        else:
            self.log("Server started (may take a moment to load)", "WARN")
            return url

    def stop_dev_server(self):
        """Stop the running dev server."""
        if self._server_proc:
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID",
                         str(self._server_proc.pid)],
                        capture_output=True
                    )
                else:
                    os.killpg(os.getpgid(self._server_proc.pid), signal.SIGTERM)
                self._server_proc = None
                self.log("Dev server stopped")
            except Exception as e:
                self.log(f"Stop server: {e}", "WARN")

    def _find_free_port(self) -> int:
        import socket
        for port in range(3000, 3020):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("localhost", port)) != 0:
                    return port
        return 3000

    def _wait_for_server(self, url: str, timeout: int = 45) -> bool:
        import urllib.request
        end = time.time() + timeout
        while time.time() < end:
            try:
                urllib.request.urlopen(url, timeout=2)
                return True
            except Exception:
                time.sleep(1.5)
        return False

    # ─────────────────────────────────────────────────────────
    # DEPLOYMENT
    # ─────────────────────────────────────────────────────────

    def deploy(self, proj_dir: Path, target: str = "vercel") -> str:
        """Deploy to Vercel, Netlify, or Docker."""
        self.log(f"Deploying to {target}...")

        if target == "vercel":
            return self._deploy_vercel(proj_dir)
        elif target == "netlify":
            return self._deploy_netlify(proj_dir)
        elif target == "docker":
            return self._deploy_docker(proj_dir)
        else:
            return "Unknown deploy target"

    def _deploy_vercel(self, proj_dir: Path) -> str:
        # Check vercel CLI
        code, out, _ = _run(["npx", "vercel", "--version"], proj_dir, timeout=30)
        if code != 0:
            _run(["npm", "install", "-g", "vercel"], proj_dir, timeout=120)
        code, out, err = _run(
            ["npx", "vercel", "--yes", "--prod"],
            proj_dir, timeout=180
        )
        if code == 0:
            url_match = re.search(r"https://\S+\.vercel\.app", out)
            url = url_match.group(0) if url_match else "Deployed to Vercel"
            self.log(f"Deployed: {url}", "OK")
            return url
        return f"Vercel deploy error: {err[:200]}"

    def _deploy_netlify(self, proj_dir: Path) -> str:
        code, out, err = _run(
            ["npx", "netlify-cli", "deploy", "--prod", "--dir=dist"],
            proj_dir, timeout=180
        )
        if code == 0:
            url_match = re.search(r"https://\S+\.netlify\.app", out)
            return url_match.group(0) if url_match else "Deployed to Netlify"
        return f"Netlify error: {err[:200]}"

    def _deploy_docker(self, proj_dir: Path) -> str:
        dockerfile = """FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install --legacy-peer-deps
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
"""
        self._write(proj_dir / "Dockerfile", dockerfile)
        self._write(proj_dir / ".dockerignore",
                    "node_modules\n.next\n.git\n")
        self.log("Dockerfile created — run: docker build -t my-site . && docker run -p 3000:3000 my-site")
        return "Docker: Dockerfile created in project folder"

    # ─────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────

    def _write(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _create_src_structure(self, proj_dir: Path,
                               plan: WebsitePlan) -> Path:
        """Create src/ directory structure."""
        framework = plan.get_stack()["framework"]

        if framework == "nextjs":
            src = proj_dir / "src"
            src.mkdir(exist_ok=True)
            (src / "components").mkdir(exist_ok=True)
            (src / "lib").mkdir(exist_ok=True)
            (src / "styles").mkdir(exist_ok=True)
            if plan.has_auth:
                (src / "app" / "api" / "auth").mkdir(parents=True, exist_ok=True)
            return src
        else:
            src = proj_dir / "src"
            src.mkdir(exist_ok=True)
            (src / "components").mkdir(exist_ok=True)
            (src / "hooks").mkdir(exist_ok=True)
            (src / "utils").mkdir(exist_ok=True)
            return src

    def _gen_index_html(self, plan: WebsitePlan) -> str:
        return f"""<!doctype html>
<html lang="en" class="{'dark' if plan.color_theme == 'dark' else ''}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="description" content="{plan.site_tagline or plan.description[:120]}" />
    <title>{plan.site_name}</title>
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""

    def _gen_main_jsx(self, plan: WebsitePlan) -> str:
        is_dark = plan.color_theme == "dark"
        return f"""import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

// Set initial theme
if ({str(is_dark).lower()}) {{
  document.documentElement.classList.add('dark')
}}

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
"""

    def _gen_layout(self, plan: WebsitePlan) -> str:
        is_dark = plan.color_theme == "dark"
        return f"""import type {{ Metadata }} from 'next'
import './globals.css'

export const metadata: Metadata = {{
  title:       '{plan.site_name}',
  description: '{plan.site_tagline or plan.description[:120]}',
  openGraph: {{
    title:       '{plan.site_name}',
    description: '{plan.site_tagline}',
  }},
}}

export default function RootLayout({{
  children,
}}: {{
  children: React.ReactNode
}}) {{
  return (
    <html lang="en" className="{'dark' if is_dark else ''}">
      <body className="bg-[{plan.primary_color if False else '#0a0a0a' if is_dark else '#ffffff'}] text-white antialiased">
        {{children}}
      </body>
    </html>
  )
}}
"""
