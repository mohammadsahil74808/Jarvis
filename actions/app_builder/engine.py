# actions/app_builder/engine.py
# ══════════════════════════════════════════════════════════════
# JARVIS Flutter App Builder — Project Engine
# Scaffold project, flutter pub get, run on emulator, build APK
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import os
import re
import shutil
import subprocess
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable

from .brain   import AppPlan
from .codegen import FlutterCodeGen
from core.ai_router import get_ai_router
from core.config import get_desktop_path


def _projects_dir() -> Path:
    p = get_desktop_path() / "JARVIS_Apps"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _run(cmd: list[str], cwd: Path, timeout: int = 300,
         env: dict = None) -> tuple[int, str, str]:
    merged = {**os.environ, **(env or {})}
    try:
        r = subprocess.run(cmd,
                           cwd=str(cwd), capture_output=True,
                           text=True, timeout=timeout, env=merged, shell=False)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except FileNotFoundError as e:
        return -1, "", str(e)


class FlutterEngine:
    """Full Flutter project lifecycle manager."""

    def __init__(self, log_callback: Optional[Callable] = None, widget = None):
        self.gen     = FlutterCodeGen()
        self.router  = get_ai_router()
        self._log_cb = log_callback or print
        self.widget  = widget
        self._flutter_path = self._find_flutter()

    # ─────────────────────────────────────────────────────────
    def log(self, msg: str, level: str = "INFO"):
        tag = {"INFO": "●", "OK": "✓", "ERR": "✗", "WARN": "⚠"}.get(level, "●")
        self._log_cb(f"[{datetime.now().strftime('%H:%M:%S')}] {tag} {msg}")
        if self.widget:
            w_tag = {"INFO": "info", "OK": "ok", "ERR": "err", "WARN": "warn"}.get(level, "info")
            self.widget.log(msg, w_tag)

    def _find_flutter(self) -> str:
        """Find flutter executable path."""
        # Common Flutter installation paths
        candidates = [
            "flutter",
            r"C:\flutter\bin\flutter",
            r"C:\src\flutter\bin\flutter",
            os.path.expanduser("~/flutter/bin/flutter"),
            os.path.expanduser("~/snap/flutter/common/flutter/bin/flutter"),
            "/usr/local/bin/flutter",
            "/opt/flutter/bin/flutter",
        ]
        for path in candidates:
            code, _, _ = _run([path, "--version"], Path.home(), timeout=15)
            if code == 0:
                return path
        return "flutter"   # Hope it's in PATH

    def flutter_available(self) -> bool:
        code, out, _ = _run([self._flutter_path, "--version"],
                             Path.home(), timeout=15)
        return code == 0

    # ─────────────────────────────────────────────────────────
    # STEP 1: Create Flutter project
    # ─────────────────────────────────────────────────────────

    def create_project(self, plan: AppPlan) -> Path:
        """
        Create a new Flutter project using `flutter create`.
        Returns project directory path.
        """
        slug      = re.sub(r"[^a-z0-9_]", "_",
                           plan.app_name.lower()).strip("_")[:40].strip("_")
        timestamp = datetime.now().strftime("%m%d_%H%M")
        proj_name = f"{slug}_{timestamp}"
        proj_dir  = _projects_dir() / proj_name

        self.log(f"Creating Flutter project: {proj_name}")
        if self.widget: self.widget.update_phase("PLAN")

        if self.flutter_available():
            code, out, err = _run(
                [self._flutter_path, "create",
                 f"--org={'.'.join(plan.package_name.split('.')[:-1])}",
                 f"--project-name={slug}",
                 "--platforms=android,ios",
                 proj_name],
                cwd=_projects_dir(),
                timeout=120,
            )
            if code != 0:
                self.log(f"flutter create warning: {err[:200]}", "WARN")
                proj_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.log("Flutter not found — creating project structure manually", "WARN")
            proj_dir.mkdir(parents=True, exist_ok=True)

        # Open in VS Code immediately so user can see it
        try:
            subprocess.run(["code", str(proj_dir)], shell=False)
            self.log("Opening VS Code for real-time visualization...", "OK")
        except Exception:
            pass

        self.log(f"Project at: {proj_dir}", "OK")
        return proj_dir

    # ─────────────────────────────────────────────────────────
    # STEP 2: Scaffold all files
    # ─────────────────────────────────────────────────────────

    def scaffold(self, proj_dir: Path, plan: AppPlan):
        """Generate and write all project files."""
        if self.widget: self.widget.update_phase("SCAFFOLD")
        self.log("Scaffolding project structure...")

        pkg = re.sub(r'[^a-z0-9_]', '_', plan.app_name.lower())
        lib = proj_dir / "lib"
        lib.mkdir(exist_ok=True)

        # ── Create directory tree ──────────────────────────
        dirs = [
            lib / "core" / "theme",
            lib / "core" / "router",
            lib / "core" / "constants",
            lib / "core" / "utils",
            lib / "core" / "extensions",
            lib / "shared" / "widgets",
            lib / "shared" / "models",
            lib / "shared" / "services",
        ]
        for screen in plan.screens:
            feature = screen.replace("_screen", "")
            dirs += [
                lib / "features" / feature / "presentation" / "screens",
                lib / "features" / feature / "presentation" / "widgets",
                lib / "features" / feature / "data",
                lib / "features" / feature / "domain",
            ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

        # ── Assets folders ─────────────────────────────────
        for asset in ["assets/images", "assets/animations",
                      "assets/icons", "assets/fonts"]:
            (proj_dir / asset).mkdir(parents=True, exist_ok=True)

        # ── pubspec.yaml ───────────────────────────────────
        self.log("Generating pubspec.yaml...")
        self._write(proj_dir / "pubspec.yaml",
                    self.gen.gen_pubspec(plan))

        # ── main.dart ──────────────────────────────────────
        self.log("Generating main.dart...")
        self._write(lib / "main.dart",
                    self.gen.gen_main_dart(plan))

        # ── Theme ──────────────────────────────────────────
        self.log("Generating theme...")
        self._write(lib / "core" / "theme" / "app_theme.dart",
                    self.gen.gen_theme(plan))

        # ── Router ─────────────────────────────────────────
        self.log("Generating router...")
        self._write(lib / "core" / "router" / "app_router.dart",
                    self.gen.gen_router(plan))

        # ── Constants ──────────────────────────────────────
        self._write(lib / "core" / "constants" / "app_constants.dart",
                    self.gen.gen_constants(plan))

        # ── Screens ────────────────────────────────────────
        self.log(f"Generating {len(plan.screens)} screens...")
        for screen in plan.screens:
            self.log(f"  Generating: {screen}...")
            code      = self.gen.gen_screen(screen, plan)
            feat_dir  = (lib / "features" / screen /
                         "presentation" / "screens")
            feat_dir.mkdir(parents=True, exist_ok=True)
            self._write(feat_dir / f"{screen}_screen.dart", code)

        # ── Bottom Nav Shell ───────────────────────────────
        if plan.bottom_nav_tabs:
            self.log("Generating navigation shell...")
            self._write(lib / "shared" / "widgets" / "app_shell.dart",
                        self.gen.gen_nav_shell(plan))

        # ── Auth Service ───────────────────────────────────
        if plan.has_auth:
            self.log("Generating auth service...")
            self._write(lib / "shared" / "services" / "auth_service.dart",
                        self.gen.gen_auth_service(plan))

        # ── Firebase options placeholder ───────────────────
        if plan.use_firebase:
            self._write(lib / "firebase_options.dart",
                        self._gen_firebase_options_placeholder(plan))

        # ── Utility extensions ─────────────────────────────
        self._write(lib / "core" / "extensions" / "context_ext.dart",
                    self._gen_context_extensions())
        self._write(lib / "core" / "utils" / "validators.dart",
                    self._gen_validators())

        # ── Android config ─────────────────────────────────
        self._patch_android_manifest(proj_dir, plan)
        self._patch_build_gradle(proj_dir, plan)

        # ── README ─────────────────────────────────────────
        self._write(proj_dir / "README.md",
                    self.gen.gen_readme(plan))

        # ── Save plan ──────────────────────────────────────
        self._write(proj_dir / ".jarvis_plan.json", plan.to_json())

        total = sum(1 for _ in (lib).rglob("*.dart"))
        self.log(f"Scaffold complete — {total} Dart files generated", "OK")

    # ─────────────────────────────────────────────────────────
    # STEP 3: flutter pub get
    # ─────────────────────────────────────────────────────────

    def pub_get(self, proj_dir: Path) -> bool:
        if self.widget: self.widget.update_phase("INSTALL")
        self.log("Running flutter pub get...")
        if not self.flutter_available():
            self.log("Flutter not found — skipping pub get", "WARN")
            return False

        code, out, err = _run(
            [self._flutter_path, "pub", "get"],
            proj_dir, timeout=180
        )
        if code == 0:
            self.log("flutter pub get complete", "OK")
            return True

        self.log(f"pub get warning: {err[:300]}", "WARN")
        return self._fix_pub_get(proj_dir, err)

    def _fix_pub_get(self, proj_dir: Path, error: str) -> bool:
        """Auto-fix pub get errors."""
        # Version conflicts — try with --no-example
        code, _, _ = _run(
            [self._flutter_path, "pub", "get", "--no-example"],
            proj_dir, timeout=180
        )
        if code == 0:
            return True

        # Ask AI to fix pubspec
        self.log("AI fixing pubspec.yaml...", "WARN")
        try:
            pub_text = (proj_dir / "pubspec.yaml").read_text()
            resp = self.client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"""Fix pubspec.yaml to resolve dependency errors.
Error: {error[:500]}
Current pubspec.yaml:
{pub_text}
Return ONLY the fixed pubspec.yaml content. No markdown."""
            )
            fixed = resp.text.strip().replace("```yaml", "").replace("```", "").strip()
            (proj_dir / "pubspec.yaml").write_text(fixed)
            code, _, _ = _run([self._flutter_path, "pub", "get"],
                               proj_dir, timeout=180)
            return code == 0
        except Exception as e:
            self.log(f"AI fix failed: {e}", "ERR")
            return False

    # ─────────────────────────────────────────────────────────
    # STEP 4: Build check + auto-fix
    # ─────────────────────────────────────────────────────────

    def analyze_and_fix(self, proj_dir: Path, plan: AppPlan,
                         max_rounds: int = 3) -> bool:
        """Run flutter analyze, auto-fix errors iteratively."""
        if not self.flutter_available():
            return True

        for rnd in range(1, max_rounds + 1):
            if self.widget: self.widget.update_phase("BUILD")
            self.log(f"Analyzing code (round {rnd}/{max_rounds})...")
            code, out, err = _run(
                [self._flutter_path, "analyze", "--no-pub"],
                proj_dir, timeout=120
            )
            if code == 0:
                self.log("Analysis clean ✓", "OK")
                return True

            issues = (out + err)[-3000:]
            error_count = issues.count("error •")
            if error_count == 0:
                self.log("Only warnings — acceptable", "OK")
                return True

            self.log(f"Found {error_count} errors — AI fixing...", "WARN")
            self._ai_fix_analysis(proj_dir, issues, plan)
            time.sleep(0.5)

        self.log("Some issues remain — app may still run", "WARN")
        return False

    def _ai_fix_analysis(self, proj_dir: Path, analysis_output: str,
                          plan: AppPlan):
        """Ask Gemini to fix Dart analysis errors."""
        # Extract affected files from analysis output
        file_pattern = re.compile(r"lib/([^\s:]+\.dart)")
        files_to_fix  = list(dict.fromkeys(
            file_pattern.findall(analysis_output)
        ))[:3]  # Fix max 3 files at once

        for rel_path in files_to_fix:
            full_path = proj_dir / "lib" / rel_path
            if not full_path.exists():
                continue
            try:
                original = full_path.read_text(encoding="utf-8")
                resp     = self.router.generate(
                    prompt=f"""Fix the Dart/Flutter analysis errors in this file.

Analysis output (errors for this file):
{analysis_output[:1500]}

Current file ({rel_path}):
{original[:4000]}

Return ONLY the complete fixed Dart file. No markdown. No explanations."""
                )
                fixed = resp.strip()
                fixed = re.sub(r"```dart\n?", "", fixed)
                fixed = re.sub(r"```\n?",     "", fixed).strip()

                if "class " in fixed or "void main" in fixed:
                    shutil.copy2(full_path, full_path.with_suffix(".dart.bak"))
                    full_path.write_text(fixed, encoding="utf-8")
                    self.log(f"Auto-fixed: {rel_path}", "OK")
            except Exception as e:
                self.log(f"Fix attempt failed for {rel_path}: {e}", "WARN")

    # ─────────────────────────────────────────────────────────
    # STEP 5: Run on emulator / device
    # ─────────────────────────────────────────────────────────

    def get_devices(self) -> list[dict]:
        """List available emulators and devices."""
        if not self.flutter_available():
            return []
        code, out, _ = _run(
            [self._flutter_path, "devices", "--machine"],
            Path.home(), timeout=30
        )
        if code == 0:
            try:
                devices = json.loads(out)
                return [{"id": d.get("id"), "name": d.get("name"),
                         "platform": d.get("targetPlatform")}
                        for d in devices]
            except Exception:
                pass
        return []

    def run_on_device(self, proj_dir: Path, plan: AppPlan,
                       device_id: str = None) -> str:
        """
        Run app on emulator or device.
        Returns instruction string (can't stay connected in sync mode).
        """
        if not self.flutter_available():
            return self._manual_run_instructions(proj_dir, plan)

        devices = self.get_devices()

        if not devices:
            return (
                f"No emulator/device found.\n"
                f"{self._manual_run_instructions(proj_dir, plan)}"
            )

        target = device_id or devices[0]["id"]
        device_name = next(
            (d["name"] for d in devices if d["id"] == target),
            target
        )

        self.log(f"Launching on: {device_name}")
        if self.widget: self.widget.update_phase("PREVIEW")

        # Launch in background (non-blocking)
        env = {**os.environ}
        try:
            cmd_list = [self._flutter_path, "run", f"--device-id={target}", "--debug"]
            self._run_proc = subprocess.Popen(
                cmd_list, cwd=str(proj_dir),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                shell=False
            )
            return (
                f"App launching on: {device_name}\n"
                f"Hot reload: press 'r' in terminal\n"
                f"Hot restart: press 'R'\n"
                f"Quit: press 'q'\n\n"
                f"Project folder: {proj_dir}"
            )
        except Exception as e:
            return f"Launch failed: {e}\n\n{self._manual_run_instructions(proj_dir, plan)}"

    def stop_dev_server(self):
        """Stop the running app process."""
        if hasattr(self, "_run_proc") and self._run_proc:
            try:
                if os.name == "nt":
                    import subprocess
                    subprocess.run(["taskkill", "/F", "/T", "/PID", str(self._run_proc.pid)], capture_output=True)
                else:
                    os.killpg(os.getpgid(self._run_proc.pid), 15)
                self._run_proc = None
                self.log("App process stopped")
            except Exception as e:
                self.log(f"Stop app error: {e}", "WARN")

    def _manual_run_instructions(self, proj_dir: Path,
                                  plan: AppPlan) -> str:
        return (
            f"\nManual Run Instructions:\n"
            f"1. Open Android Studio or VS Code\n"
            f"2. Start an Android emulator\n"
            f"3. Open terminal and run:\n"
            f"   cd '{proj_dir}'\n"
            f"   flutter pub get\n"
            f"   flutter run\n\n"
            f"Or build APK:\n"
            f"   flutter build apk --debug\n"
            f"   # APK at: build/app/outputs/flutter-apk/app-debug.apk"
        )

    # ─────────────────────────────────────────────────────────
    # STEP 6: Build APK / AAB
    # ─────────────────────────────────────────────────────────

    def build_apk(self, proj_dir: Path,
                   release: bool = False) -> str:
        if not self.flutter_available():
            return f"Flutter not found.\nManual: cd '{proj_dir}' && flutter build apk"

        mode = "--release" if release else "--debug"
        self.log(f"Building APK ({mode})...")

        code, out, err = _run(
            [self._flutter_path, "build", "apk", mode],
            proj_dir, timeout=600
        )
        if code == 0:
            apk_path = (proj_dir / "build" / "app" / "outputs" /
                        "flutter-apk" /
                        ("app-release.apk" if release else "app-debug.apk"))
            self.log(f"APK built: {apk_path}", "OK")

            # Open containing folder
            try:
                if os.name == "nt":
                    subprocess.Popen(
                        ["explorer", str(apk_path.parent)])
            except Exception:
                pass

            return f"APK built!\nPath: {apk_path}\nSize: {apk_path.stat().st_size // (1024*1024):.1f} MB"

        return f"Build failed:\n{err[-500:]}\n\nTry manually: flutter build apk"

    def build_aab(self, proj_dir: Path) -> str:
        if not self.flutter_available():
            return "Flutter not found."
        self.log("Building AAB (Play Store)...")
        code, out, err = _run(
            [self._flutter_path, "build", "appbundle", "--release"],
            proj_dir, timeout=600
        )
        if code == 0:
            aab = (proj_dir / "build" / "app" / "outputs" /
                   "bundle" / "release" / "app-release.aab")
            return f"AAB built!\nPath: {aab}"
        return f"AAB build failed:\n{err[-400:]}"

    # ─────────────────────────────────────────────────────────
    # ANDROID PATCHES
    # ─────────────────────────────────────────────────────────

    def _patch_android_manifest(self, proj_dir: Path, plan: AppPlan):
        manifest_path = (proj_dir / "android" / "app" / "src" /
                         "main" / "AndroidManifest.xml")
        if not manifest_path.exists():
            return

        perms = ['<uses-permission android:name="android.permission.INTERNET"/>']
        if plan.has_camera:
            perms.append('<uses-permission android:name="android.permission.CAMERA"/>')
        if plan.has_maps:
            perms.append('<uses-permission android:name="android.permission.ACCESS_FINE_LOCATION"/>')
            perms.append('<uses-permission android:name="android.permission.ACCESS_COARSE_LOCATION"/>')
        if plan.has_notifications:
            perms.append('<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>')

        content = manifest_path.read_text(encoding="utf-8")
        perm_block = "\n    ".join(perms)
        content = content.replace(
            "<manifest xmlns:android",
            f"<manifest xmlns:android"
        )
        if "INTERNET" not in content:
            content = content.replace(
                "<application",
                f"{perm_block}\n\n    <application"
            )
        manifest_path.write_text(content, encoding="utf-8")

    def _patch_build_gradle(self, proj_dir: Path, plan: AppPlan):
        gradle_path = proj_dir / "android" / "app" / "build.gradle"
        if not gradle_path.exists():
            return

        content = gradle_path.read_text(encoding="utf-8")
        # Set minimum SDK
        content = re.sub(
            r"minSdkVersion\s+\d+",
            f"minSdkVersion {plan.min_sdk}",
            content
        )
        # Set target SDK
        content = re.sub(
            r"targetSdkVersion\s+\d+",
            "targetSdkVersion 34",
            content
        )
        # Set package name
        if plan.package_name and "com.example" in content:
            content = content.replace(
                "com.example.flutter_app",
                plan.package_name
            ).replace(
                "com.example.app",
                plan.package_name
            )
        gradle_path.write_text(content, encoding="utf-8")

    # ─────────────────────────────────────────────────────────
    # UTILITY FILES
    # ─────────────────────────────────────────────────────────

    def _gen_context_extensions(self) -> str:
        return r"""import 'package:flutter/material.dart';

extension ContextExtensions on BuildContext {
  // Theme shortcuts
  ThemeData  get theme        => Theme.of(this);
  ColorScheme get colorScheme => Theme.of(this).colorScheme;
  TextTheme  get textTheme    => Theme.of(this).textTheme;

  // Media query
  Size   get screenSize   => MediaQuery.of(this).size;
  double get screenWidth  => MediaQuery.of(this).size.width;
  double get screenHeight => MediaQuery.of(this).size.height;
  double get statusBarH   => MediaQuery.of(this).padding.top;
  double get bottomPadH  => MediaQuery.of(this).padding.bottom;

  // Responsive breakpoints
  bool get isMobile  => screenWidth < 600;
  bool get isTablet  => screenWidth >= 600 && screenWidth < 1200;
  bool get isDesktop => screenWidth >= 1200;

  // Navigation
  void pop<T>([T? result]) => Navigator.of(this).pop(result);

  // Snackbar
  void showSnack(String msg, {bool isError = false}) {
    ScaffoldMessenger.of(this).showSnackBar(SnackBar(
      content: Text(msg),
      backgroundColor: isError ? colorScheme.error : colorScheme.primary,
      behavior: SnackBarBehavior.floating,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
    ));
  }
}
"""

    def _gen_validators(self) -> str:
        return r"""class Validators {
  static String? email(String? val) {
    if (val == null || val.trim().isEmpty) return 'Email required';
    final regex = RegExp(r'^[\\w.]+@[\\w]+\\.[\\w]+\$');
    if (!regex.hasMatch(val.trim())) return 'Enter valid email';
    return null;
  }

  static String? password(String? val) {
    if (val == null || val.isEmpty) return 'Password required';
    if (val.length < 6) return 'Min 6 characters';
    return null;
  }

  static String? name(String? val) {
    if (val == null || val.trim().isEmpty) return 'Name required';
    if (val.trim().length < 2) return 'Too short';
    return null;
  }

  static String? required(String? val, [String field = 'Field']) {
    if (val == null || val.trim().isEmpty) return '\$field required';
    return null;
  }

  static String? phone(String? val) {
    if (val == null || val.trim().isEmpty) return 'Phone required';
    final digits = val.replaceAll(RegExp(r'[^0-9]'), '');
    if (digits.length < 10) return 'Enter valid phone number';
    return null;
  }
}
"""

    def _gen_firebase_options_placeholder(self, plan: AppPlan) -> str:
        return f"""// IMPORTANT: Replace with your actual Firebase config
// Run: flutterfire configure
// See: https://firebase.google.com/docs/flutter/setup

import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart' show defaultTargetPlatform, TargetPlatform;

class DefaultFirebaseOptions {{
  static FirebaseOptions get currentPlatform {{
    switch (defaultTargetPlatform) {{
      case TargetPlatform.android:
        return android;
      default:
        return android;
    }}
  }}

  // TODO: Replace with your Firebase Android config
  static const FirebaseOptions android = FirebaseOptions(
    apiKey:            'YOUR-API-KEY',
    appId:             'YOUR-APP-ID',
    messagingSenderId: 'YOUR-SENDER-ID',
    projectId:         'YOUR-PROJECT-ID',
    storageBucket:     'YOUR-STORAGE-BUCKET',
  );
}}
"""

    def _write(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
