# actions/app_builder/builder.py
# ══════════════════════════════════════════════════════════════
# JARVIS Flutter App Builder — Main Entry Point
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
from pathlib import Path
from typing import Optional, Callable

from .brain  import AppBrain, AppPlan
from .engine import FlutterEngine


# Singleton engine
_engine: Optional[FlutterEngine] = None


def _get_engine(log_cb: Callable = None, widget = None) -> FlutterEngine:
    global _engine
    if _engine is not None:
        try:
            _engine.stop_dev_server()
        except Exception:
            pass
    _engine = FlutterEngine(log_callback=log_cb, widget=widget)
    return _engine


# ══════════════════════════════════════════════════════════════
# PRIMARY FUNCTION — JARVIS calls this
# ══════════════════════════════════════════════════════════════

def build_mobile_app(
    user_prompt: str,
    player=None,
    clarification_answers: dict = None,
    build_apk: bool = False,
    device_id: str = None,
    _widget_ref = None,
) -> str:
    """
    JARVIS main entry point for Flutter app building.

    Integration in main.py _execute_tool():
        from actions.app_builder import build_mobile_app
        result = await loop.run_in_executor(
            None, lambda: build_mobile_app(args.get("prompt"), player=self.ui))
    """
    def log(msg: str):
        print(f"[AppBuilder] {msg}")
        if player:
            try:
                player.write_log(f"[app_builder] {msg}")
            except Exception:
                pass

    engine = _get_engine(log_cb=log, widget=_widget_ref)
    brain  = AppBrain()

    log(f"Building app: '{user_prompt[:80]}'")

    # Step 1: Analyze intent
    plan = brain.create_plan(user_prompt, extra_answers=clarification_answers)
    log(f"Plan: {plan.app_name} | {plan.app_type} | {plan.get_arch()['name']}")

    # Step 2: Clarification check
    intent    = getattr(brain, '_last_intent', {})
    questions = brain.get_clarification_questions(intent)
    if questions and intent.get("confidence", 100) < 70 and not clarification_answers:
        q_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        return (
            f"Mujhe kuch aur details chahiye:\n\n{q_text}\n\n"
            f"_Jawab do, phir app build karunga._\n[NEEDS_CLARIFICATION]"
        )

    # Step 3: Create Flutter project
    log("Creating Flutter project...")
    try:
        proj_dir = engine.create_project(plan)
    except Exception as e:
        return f"Project creation failed: {e}"

    # Step 4: Scaffold all files
    log("Scaffolding all files...")
    try:
        engine.scaffold(proj_dir, plan)
    except Exception as e:
        return f"Scaffold failed: {e}"

    # Step 5: flutter pub get
    engine.pub_get(proj_dir)

    # Step 6: Analyze and auto-fix
    engine.analyze_and_fix(proj_dir, plan, max_rounds=2)

    # Step 7: Build APK (optional)
    apk_result = ""
    if build_apk:
        apk_result = engine.build_apk(proj_dir, release=False)

    # Step 8: Run on device / instructions
    run_result = engine.run_on_device(proj_dir, plan, device_id=device_id)

    # Final response
    arch      = plan.get_arch()
    dart_files = sum(1 for _ in (proj_dir / "lib").rglob("*.dart"))
    result = (
        f"✓ App ready!\n\n"
        f"  Name         : {plan.app_name}\n"
        f"  Type         : {plan.app_type.title()}\n"
        f"  Architecture : {arch['name']}\n"
        f"  Screens      : {', '.join(plan.screens)}\n"
        f"  Dart files   : {dart_files}\n"
        f"  Folder       : {proj_dir}\n\n"
        f"{run_result}\n"
    )
    if apk_result:
        result += f"\nAPK: {apk_result}"

    return result


# ── TOOL DECLARATION ──────────────────────────────────────────
APP_BUILDER_TOOL = {
    "name": "app_builder",
    "description": (
        "Build complete Flutter mobile apps with AI. Creates social, chat, "
        "ecommerce, fitness, finance, AI chat, news, todo, food delivery, "
        "music, dashboard, and utility apps. Full project with all screens, "
        "auth, theme, navigation. Use when user wants to build/create a mobile app."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Full description of the mobile app to build",
            },
            "build_apk": {
                "type": "boolean",
                "description": "Also build debug APK (default false)",
            },
            "use_template": {
                "type": "string",
                "description": "Template: social_app, chat_app, ecommerce_app, fitness_app, ai_chat_app, todo_app, music_app, dashboard_app",
            },
        },
        "required": ["prompt"],
    },
}


# ══════════════════════════════════════════════════════════════
# PLUGIN SYSTEM
# ══════════════════════════════════════════════════════════════

from dataclasses import dataclass, field
from typing import Optional as Opt


@dataclass
class AppPlugin:
    name:             str
    description:      str
    version:          str = "1.0.0"
    on_plan_ready:    Opt[Callable] = None
    on_scaffold_done: Opt[Callable] = None
    on_pub_get_done:  Opt[Callable] = None


class AppPluginRegistry:
    def __init__(self):
        self._plugins: list[AppPlugin] = []
        self._load_defaults()

    def register(self, plugin: AppPlugin):
        self._plugins = [p for p in self._plugins if p.name != plugin.name]
        self._plugins.append(plugin)

    def run_plan_ready(self, plan: AppPlan) -> AppPlan:
        for p in self._plugins:
            if p.on_plan_ready:
                try: plan = p.on_plan_ready(plan) or plan
                except Exception as e: print(f"[Plugin {p.name}] {e}")
        return plan

    def run_scaffold_done(self, proj_dir: Path, plan: AppPlan):
        for p in self._plugins:
            if p.on_scaffold_done:
                try: p.on_scaffold_done(proj_dir, plan)
                except Exception as e: print(f"[Plugin {p.name}] {e}")

    def _load_defaults(self):
        self.register(AppPlugin(
            name="gitignore",
            description="Adds .gitignore to every project",
            on_scaffold_done=lambda d, p: (d / ".gitignore").write_text(
                ".dart_tool/\n.flutter-plugins\n.flutter-plugins-dependencies\n"
                ".packages\nbuild/\n*.iml\n.idea/\nandroid/.gradle/\n"
                "android/local.properties\nandroid/captures/\n"
                "*.log\n.env\nkey.properties\n"
            ),
        ))
        self.register(AppPlugin(
            name="env_template",
            description="Creates .env.example",
            on_scaffold_done=self._create_env_template,
        ))

    @staticmethod
    def _create_env_template(proj_dir: Path, plan: AppPlan):
        lines = ["# Environment Variables"]
        if plan.use_firebase:
            lines += ["FIREBASE_API_KEY=",
                      "FIREBASE_APP_ID=",
                      "FIREBASE_PROJECT_ID="]
        if plan.has_payments:
            lines += ["STRIPE_PK=", "STRIPE_SK="]
        if plan.has_ai:
            lines += ["GEMINI_API_KEY=", "OPENAI_API_KEY="]
        lines += ["API_BASE_URL=https://api.example.com/v1"]
        (proj_dir / ".env.example").write_text("\n".join(lines))


plugin_registry = AppPluginRegistry()


# ══════════════════════════════════════════════════════════════
# TEMPLATE SYSTEM
# ══════════════════════════════════════════════════════════════

@dataclass
class AppTemplate:
    name:        str
    description: str
    tags:        list[str] = field(default_factory=list)
    plan_data:   dict      = field(default_factory=dict)

    def to_plan(self, overrides: dict = None) -> AppPlan:
        data = {**self.plan_data, **(overrides or {})}
        return AppPlan(**{k: v for k, v in data.items()
                          if k in AppPlan.__dataclass_fields__})


APP_TEMPLATES: dict[str, AppTemplate] = {
    "social_app": AppTemplate(
        name="Social Media App",
        description="Instagram/Twitter style social app with Firebase",
        tags=["social", "firebase", "feed", "profiles"],
        plan_data={
            "app_type": "social", "app_name": "SocialApp",
            "tagline": "Connect with the world",
            "color_theme": "dark",
            "primary_color": "0xFFE1306C", "accent_color": "0xFFC13584",
            "font_family": "Poppins", "arch_key": "firebase_mvvm",
            "state_mgmt": "riverpod", "use_firebase": True,
            "has_auth": True, "has_onboarding": True,
            "has_camera": True, "has_notifications": True,
            "screens": ["splash", "onboarding", "login", "signup",
                        "home", "explore", "notifications",
                        "profile", "settings"],
            "bottom_nav_tabs": ["home", "explore", "notifications", "profile"],
        }
    ),

    "chat_app": AppTemplate(
        name="Chat / Messaging App",
        description="WhatsApp style messaging with Firebase realtime",
        tags=["chat", "messaging", "realtime", "firebase"],
        plan_data={
            "app_type": "chat", "app_name": "ChatApp",
            "tagline": "Message anyone, anywhere",
            "color_theme": "dark",
            "primary_color": "0xFF25D366", "accent_color": "0xFF128C7E",
            "font_family": "Nunito", "arch_key": "firebase_mvvm",
            "state_mgmt": "riverpod", "use_firebase": True,
            "has_auth": True, "has_chat": True,
            "has_notifications": True, "has_camera": True,
            "screens": ["splash", "login", "signup",
                        "conversations", "chat_detail",
                        "contacts", "profile", "settings"],
            "bottom_nav_tabs": ["chat", "contacts", "profile"],
        }
    ),

    "ecommerce_app": AppTemplate(
        name="E-Commerce App",
        description="Full shopping app with cart, payments, orders",
        tags=["ecommerce", "shopping", "payments", "orders"],
        plan_data={
            "app_type": "ecommerce", "app_name": "ShopApp",
            "tagline": "Shop smarter",
            "color_theme": "light",
            "primary_color": "0xFF6366F1", "accent_color": "0xFFEC4899",
            "font_family": "Inter", "arch_key": "clean",
            "state_mgmt": "riverpod", "use_firebase": True,
            "has_auth": True, "has_payments": True,
            "has_camera": True, "has_offline": True,
            "screens": ["splash", "onboarding", "login", "signup",
                        "home", "product_list", "product_detail",
                        "cart", "checkout", "orders", "profile"],
            "bottom_nav_tabs": ["home", "explore", "cart", "profile"],
        }
    ),

    "fitness_app": AppTemplate(
        name="Fitness & Health App",
        description="Workout tracker with progress, nutrition, stats",
        tags=["fitness", "health", "workout", "tracking"],
        plan_data={
            "app_type": "fitness", "app_name": "FitApp",
            "tagline": "Your fitness journey starts here",
            "color_theme": "dark",
            "primary_color": "0xFF00C853", "accent_color": "0xFF69F0AE",
            "font_family": "Poppins", "arch_key": "riverpod",
            "state_mgmt": "riverpod", "use_firebase": True,
            "has_auth": True, "has_onboarding": True,
            "screens": ["splash", "onboarding", "login",
                        "dashboard", "workout", "progress",
                        "nutrition", "profile", "settings"],
            "bottom_nav_tabs": ["dashboard", "workout", "progress", "profile"],
        }
    ),

    "ai_chat_app": AppTemplate(
        name="AI Chat Assistant App",
        description="Gemini/GPT powered chat assistant with history",
        tags=["ai", "chatbot", "gemini", "assistant"],
        plan_data={
            "app_type": "ai_chat", "app_name": "AI Assistant",
            "tagline": "Your personal AI companion",
            "color_theme": "dark",
            "primary_color": "0xFF7C3AED", "accent_color": "0xFF06B6D4",
            "font_family": "Poppins", "arch_key": "clean",
            "state_mgmt": "riverpod", "use_firebase": False,
            "has_auth": False, "has_ai": True, "has_chat": True,
            "has_offline": True, "has_animations": True,
            "screens": ["splash", "onboarding", "home",
                        "chat", "history", "settings"],
            "bottom_nav_tabs": ["home", "chat", "history", "settings"],
        }
    ),

    "todo_app": AppTemplate(
        name="Task Manager App",
        description="Clean productivity app with categories and deadlines",
        tags=["todo", "tasks", "productivity", "minimal"],
        plan_data={
            "app_type": "todo", "app_name": "TaskFlow",
            "tagline": "Get things done",
            "color_theme": "light",
            "primary_color": "0xFF3B82F6", "accent_color": "0xFF8B5CF6",
            "font_family": "DM Sans", "arch_key": "simple",
            "state_mgmt": "riverpod", "use_firebase": False,
            "has_auth": False, "has_offline": True,
            "has_animations": True,
            "screens": ["splash", "home", "task_detail",
                        "categories", "calendar", "settings"],
            "bottom_nav_tabs": ["home", "calendar", "settings"],
        }
    ),

    "music_app": AppTemplate(
        name="Music Player App",
        description="Spotify-style music app with player, library, search",
        tags=["music", "audio", "player", "library"],
        plan_data={
            "app_type": "music", "app_name": "Harmony",
            "tagline": "Your music, everywhere",
            "color_theme": "dark",
            "primary_color": "0xFF1DB954", "accent_color": "0xFF1ED760",
            "font_family": "Circular", "arch_key": "riverpod",
            "state_mgmt": "riverpod", "use_firebase": True,
            "has_auth": True, "has_offline": True,
            "has_animations": True,
            "screens": ["splash", "onboarding", "login",
                        "home", "search", "library",
                        "player", "playlist", "profile"],
            "bottom_nav_tabs": ["home", "search", "library", "profile"],
        }
    ),

    "dashboard_app": AppTemplate(
        name="Admin Dashboard App",
        description="Analytics dashboard with charts, reports, users",
        tags=["dashboard", "admin", "analytics", "charts"],
        plan_data={
            "app_type": "dashboard", "app_name": "AdminPro",
            "tagline": "Insights at your fingertips",
            "color_theme": "dark",
            "primary_color": "0xFF6366F1", "accent_color": "0xFFF59E0B",
            "font_family": "Inter", "arch_key": "clean",
            "state_mgmt": "riverpod", "use_firebase": True,
            "has_auth": True, "has_offline": True,
            "screens": ["splash", "login",
                        "dashboard", "analytics",
                        "reports", "users", "settings", "profile"],
            "bottom_nav_tabs": ["dashboard", "analytics", "reports", "settings"],
        }
    ),
}


def get_app_template(name: str) -> Optional[AppTemplate]:
    name_l = name.lower().strip()
    if name_l in APP_TEMPLATES:
        return APP_TEMPLATES[name_l]
    for key, tmpl in APP_TEMPLATES.items():
        if name_l in key or name_l in tmpl.name.lower():
            return tmpl
    return None


def list_app_templates() -> str:
    lines = ["Available app templates:\n"]
    for key, tmpl in APP_TEMPLATES.items():
        lines.append(f"  {key:<20} — {tmpl.description}")
    return "\n".join(lines)
