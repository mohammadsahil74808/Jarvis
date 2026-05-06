# actions/app_builder/brain.py
# ══════════════════════════════════════════════════════════════
# JARVIS Flutter App Builder — AI Brain
# Intent analysis, architecture decisions, project planning
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Optional
from core.ai_router import get_ai_router

# ── App types ─────────────────────────────────────────────────
APP_TYPES = {
    "social":      "Social media / community app",
    "chat":        "Messaging / chat application",
    "ecommerce":   "Shopping / e-commerce app",
    "fitness":     "Health, fitness & wellness",
    "finance":     "Finance, banking, wallet",
    "ai_chat":     "AI-powered chatbot / assistant",
    "news":        "News / content reader",
    "todo":        "Task manager / productivity",
    "food":        "Food delivery / restaurant",
    "travel":      "Travel / booking app",
    "education":   "Learning / edtech app",
    "music":       "Music / audio player",
    "dashboard":   "Admin / analytics dashboard",
    "utility":     "General utility / tool",
    "saas":        "SaaS mobile client",
    "game":        "Casual game / gamified app",
}

# ── Architecture profiles ──────────────────────────────────────
ARCHITECTURES = {
    "simple": {
        "name":        "Simple (setState + Provider)",
        "description": "Best for small apps, fast development",
        "state_mgmt":  "provider",
        "pattern":     "mvc",
        "use_for":     ["todo", "utility", "game"],
    },
    "riverpod": {
        "name":        "Riverpod Architecture",
        "description": "Modern, testable, scalable",
        "state_mgmt":  "riverpod",
        "pattern":     "mvvm",
        "use_for":     ["social", "chat", "news", "music", "education"],
    },
    "clean": {
        "name":        "Clean Architecture",
        "description": "Enterprise-grade, fully decoupled",
        "state_mgmt":  "riverpod",
        "pattern":     "clean",
        "use_for":     ["ecommerce", "finance", "saas", "dashboard", "ai_chat"],
    },
    "firebase_mvvm": {
        "name":        "Firebase + MVVM",
        "description": "Rapid full-stack development",
        "state_mgmt":  "riverpod",
        "pattern":     "mvvm",
        "use_for":     ["social", "chat", "food", "travel", "fitness"],
    },
}

# ── App type → architecture mapping ───────────────────────────
APP_TO_ARCH = {
    "social":    "firebase_mvvm",
    "chat":      "firebase_mvvm",
    "ecommerce": "clean",
    "fitness":   "riverpod",
    "finance":   "clean",
    "ai_chat":   "clean",
    "news":      "riverpod",
    "todo":      "simple",
    "food":      "firebase_mvvm",
    "travel":    "clean",
    "education": "riverpod",
    "music":     "riverpod",
    "dashboard": "clean",
    "utility":   "simple",
    "saas":      "clean",
    "game":      "simple",
}

# ── Flutter packages by feature ────────────────────────────────
FEATURE_PACKAGES = {
    "auth":           ["firebase_auth", "google_sign_in"],
    "firestore":      ["cloud_firestore", "firebase_core"],
    "storage":        ["firebase_storage"],
    "notifications":  ["firebase_messaging", "flutter_local_notifications"],
    "local_db":       ["sqflite", "path"],
    "http":           ["dio", "retrofit"],
    "state_riverpod": ["flutter_riverpod", "riverpod_annotation",
                       "riverpod_generator"],
    "state_provider": ["provider"],
    "navigation":     ["go_router"],
    "ui_extras":      ["flutter_animate", "lottie", "shimmer",
                       "cached_network_image", "flutter_svg"],
    "forms":          ["reactive_forms", "flutter_form_builder"],
    "camera":         ["image_picker", "camera"],
    "maps":           ["google_maps_flutter", "geolocator"],
    "payments":       ["pay", "flutter_stripe"],
    "charts":         ["fl_chart", "syncfusion_flutter_charts"],
    "chat_ui":        ["dash_chat_2", "bubble"],
    "audio":          ["just_audio", "audio_session"],
    "video":          ["video_player", "chewie"],
    "ai":             ["dart_openai", "google_generative_ai"],
    "utils":          ["intl", "uuid", "shared_preferences",
                       "flutter_secure_storage", "connectivity_plus",
                       "permission_handler"],
    "animations":     ["flutter_animate", "rive", "lottie"],
}


@dataclass
class AppPlan:
    """Complete plan for a Flutter app."""
    # Identity
    app_type:        str = "utility"
    app_name:        str = "MyApp"
    app_description: str = ""
    package_name:    str = "com.jarvis.myapp"
    tagline:         str = ""

    # Architecture
    arch_key:        str = "riverpod"
    state_mgmt:      str = "riverpod"
    pattern:         str = "mvvm"

    # Backend
    use_firebase:    bool = True
    use_custom_api:  bool = False
    api_base_url:    str  = ""

    # Features
    has_auth:        bool = True
    has_onboarding:  bool = True
    has_dark_mode:   bool = True
    has_notifications: bool = False
    has_offline:     bool = False
    has_camera:      bool = False
    has_maps:        bool = False
    has_payments:    bool = False
    has_chat:        bool = False
    has_ai:          bool = False
    has_animations:  bool = True

    # UI Design
    color_theme:     str = "dark"
    primary_color:   str = "0xFF6366F1"   # Flutter Color hex format
    accent_color:    str = "0xFFEC4899"
    font_family:     str = "Poppins"
    ui_style:        str = "material3"    # material3 | cupertino | adaptive

    # Screens
    screens:         list[str] = field(default_factory=list)
    bottom_nav_tabs: list[str] = field(default_factory=list)

    # Target
    target_platform: str = "android"     # android | ios | both
    min_sdk:         int = 21
    target_audience: str = "general"

    # Extra
    extra_context:   str = ""

    def get_arch(self) -> dict:
        return ARCHITECTURES.get(self.arch_key, ARCHITECTURES["riverpod"])

    def get_packages(self) -> list[str]:
        pkgs = []
        pkgs += FEATURE_PACKAGES["navigation"]
        pkgs += FEATURE_PACKAGES["ui_extras"]
        pkgs += FEATURE_PACKAGES["utils"]

        if self.state_mgmt == "riverpod":
            pkgs += FEATURE_PACKAGES["state_riverpod"]
        else:
            pkgs += FEATURE_PACKAGES["state_provider"]

        if self.use_firebase:
            pkgs += FEATURE_PACKAGES["firestore"]
        if self.has_auth:
            pkgs += FEATURE_PACKAGES["auth"]
        if self.use_firebase and self.has_notifications:
            pkgs += FEATURE_PACKAGES["notifications"]
        if self.has_offline:
            pkgs += FEATURE_PACKAGES["local_db"]
        if self.use_custom_api:
            pkgs += FEATURE_PACKAGES["http"]
        if self.has_camera:
            pkgs += FEATURE_PACKAGES["camera"]
        if self.has_maps:
            pkgs += FEATURE_PACKAGES["maps"]
        if self.has_payments:
            pkgs += FEATURE_PACKAGES["payments"]
        if self.has_chat:
            pkgs += FEATURE_PACKAGES["chat_ui"]
        if self.has_ai:
            pkgs += FEATURE_PACKAGES["ai"]
        if self.has_animations:
            pkgs += FEATURE_PACKAGES["animations"]
        if self.app_type in ("dashboard",):
            pkgs += FEATURE_PACKAGES["charts"]

        return list(dict.fromkeys(pkgs))   # deduplicate, preserve order

    def to_json(self) -> str:
        import dataclasses
        return json.dumps(dataclasses.asdict(self), indent=2)


# ══════════════════════════════════════════════════════════════
class AppBrain:
    """AI brain — analyzes prompt, picks architecture, builds plan."""

    def __init__(self):
        self.router = get_ai_router()

    def _call(self, prompt: str) -> str:
        text = self.router.generate(prompt)
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
        return text

    # ─────────────────────────────────────────────────────────
    def analyze_intent(self, user_prompt: str) -> dict:
        prompt = f"""Analyze this Flutter mobile app request:
"{user_prompt}"

Return ONLY valid JSON:
{{
  "app_type": "<one of: {', '.join(APP_TYPES.keys())}>",
  "app_name": "<name of the app>",
  "tagline": "<short tagline>",
  "app_description": "<what this app does>",
  "package_name": "<reverse domain e.g. com.sahil.appname>",
  "color_theme": "<dark|light>",
  "primary_color": "<Flutter hex e.g. 0xFF6366F1>",
  "accent_color": "<Flutter hex e.g. 0xFFEC4899>",
  "font_family": "<Google font e.g. Poppins|Nunito|Inter|Roboto>",
  "ui_style": "<material3|cupertino|adaptive>",
  "use_firebase": <true|false>,
  "has_auth": <true|false>,
  "has_onboarding": <true|false>,
  "has_dark_mode": <true|false>,
  "has_notifications": <true|false>,
  "has_offline": <true|false>,
  "has_camera": <true|false>,
  "has_maps": <true|false>,
  "has_payments": <true|false>,
  "has_chat": <true|false>,
  "has_ai": <true|false>,
  "has_animations": <true|false>,
  "target_platform": "<android|ios|both>",
  "target_audience": "<who uses this>",
  "screens": ["<screen1>", "<screen2>", ...],
  "bottom_nav_tabs": ["<tab1>", "<tab2>", ...],
  "missing_info": ["<what is still needed>"],
  "confidence": <0-100>
}}

Rules:
- screens: list all screens needed (e.g. splash, onboarding, home, profile, settings)
- bottom_nav_tabs: 3-5 main navigation items
- package_name: based on app_name, lowercase, no spaces
- confidence 100 = complete info, 0 = too vague"""

        raw = self._call(prompt)
        try:
            return json.loads(raw)
        except Exception:
            return self._fallback_intent(user_prompt)

    def _fallback_intent(self, prompt: str) -> dict:
        return {
            "app_type": "utility", "app_name": "MyApp",
            "tagline": "Built with JARVIS",
            "app_description": prompt[:200],
            "package_name": "com.jarvis.myapp",
            "color_theme": "dark",
            "primary_color": "0xFF6366F1", "accent_color": "0xFFEC4899",
            "font_family": "Poppins", "ui_style": "material3",
            "use_firebase": True, "has_auth": True,
            "has_onboarding": True, "has_dark_mode": True,
            "has_notifications": False, "has_offline": False,
            "has_camera": False, "has_maps": False,
            "has_payments": False, "has_chat": False,
            "has_ai": False, "has_animations": True,
            "target_platform": "android", "target_audience": "general",
            "screens": ["splash", "onboarding", "home", "profile", "settings"],
            "bottom_nav_tabs": ["home", "explore", "profile"],
            "missing_info": [], "confidence": 50,
        }

    # ─────────────────────────────────────────────────────────
    def get_clarification_questions(self, intent: dict) -> list[str]:
        questions = []
        confidence = intent.get("confidence", 100)
        missing    = intent.get("missing_info", [])
        app_type   = intent.get("app_type", "utility")

        if confidence >= 80 and not missing:
            return []

        if not intent.get("app_name") or intent["app_name"] == "MyApp":
            questions.append("App ka naam kya rakhna hai?")

        if app_type in ("social", "chat") and not intent.get("has_auth"):
            questions.append("Login/signup system chahiye? (haan/nahi)")

        if app_type == "ecommerce":
            questions.append("Payment gateway chahiye? (Stripe/Razorpay/nahi)")

        if app_type in ("ai_chat",) and not intent.get("has_ai"):
            questions.append("Kaunsa AI use karna hai? (Gemini/OpenAI/nahi)")

        if not intent.get("primary_color") or intent["primary_color"] == "0xFF6366F1":
            questions.append("Color theme kaisa chahiye? (dark/light, primary color like blue/green/purple)")

        for item in missing[:2]:
            questions.append(f"{item}?")

        return questions[:4]

    # ─────────────────────────────────────────────────────────
    def decide_architecture(self, intent: dict) -> str:
        app_type = intent.get("app_type", "utility")
        has_auth = intent.get("has_auth", False)
        has_ai   = intent.get("has_ai",   False)
        use_fb   = intent.get("use_firebase", True)

        if has_ai or app_type in ("finance", "ecommerce", "saas", "dashboard"):
            return "clean"
        if use_fb and app_type in ("social", "chat", "food", "travel"):
            return "firebase_mvvm"
        return APP_TO_ARCH.get(app_type, "riverpod")

    # ─────────────────────────────────────────────────────────
    def create_plan(self, user_prompt: str,
                    extra_answers: Optional[dict] = None) -> AppPlan:
        full_prompt = user_prompt
        if extra_answers:
            extras = "\n".join(f"- {k}: {v}" for k, v in extra_answers.items())
            full_prompt += f"\n\nAdditional details:\n{extras}"

        intent   = self.analyze_intent(full_prompt)
        arch_key = self.decide_architecture(intent)

        screens = intent.get("screens") or self._default_screens(
            intent.get("app_type", "utility"),
            intent.get("has_auth", True),
            intent.get("has_onboarding", True)
        )
        tabs = intent.get("bottom_nav_tabs") or ["home", "explore", "profile"]

        plan = AppPlan(
            app_type        = intent.get("app_type",        "utility"),
            app_name        = intent.get("app_name",        "MyApp"),
            app_description = intent.get("app_description", full_prompt[:300]),
            package_name    = intent.get("package_name",    "com.jarvis.myapp"),
            tagline         = intent.get("tagline",         ""),
            arch_key        = arch_key,
            state_mgmt      = ARCHITECTURES[arch_key]["state_mgmt"],
            pattern         = ARCHITECTURES[arch_key]["pattern"],
            use_firebase    = intent.get("use_firebase",    True),
            has_auth        = intent.get("has_auth",        True),
            has_onboarding  = intent.get("has_onboarding",  True),
            has_dark_mode   = intent.get("has_dark_mode",   True),
            has_notifications = intent.get("has_notifications", False),
            has_offline     = intent.get("has_offline",     False),
            has_camera      = intent.get("has_camera",      False),
            has_maps        = intent.get("has_maps",        False),
            has_payments    = intent.get("has_payments",    False),
            has_chat        = intent.get("has_chat",        False),
            has_ai          = intent.get("has_ai",          False),
            has_animations  = intent.get("has_animations",  True),
            color_theme     = intent.get("color_theme",     "dark"),
            primary_color   = intent.get("primary_color",   "0xFF6366F1"),
            accent_color    = intent.get("accent_color",    "0xFFEC4899"),
            font_family     = intent.get("font_family",     "Poppins"),
            ui_style        = intent.get("ui_style",        "material3"),
            screens         = screens,
            bottom_nav_tabs = tabs,
            target_platform = intent.get("target_platform", "android"),
            target_audience = intent.get("target_audience", "general"),
            extra_context   = full_prompt,
        )
        return plan

    def _default_screens(self, app_type: str, has_auth: bool,
                          has_onboarding: bool) -> list[str]:
        base = []
        if True:              base.append("splash")
        if has_onboarding:    base.append("onboarding")
        if has_auth:          base += ["login", "signup"]

        screens_by_type = {
            "social":    ["home", "explore", "notifications", "profile", "settings"],
            "chat":      ["conversations", "chat_detail", "contacts", "profile"],
            "ecommerce": ["home", "product_list", "product_detail", "cart",
                          "checkout", "orders", "profile"],
            "fitness":   ["dashboard", "workout", "progress", "nutrition", "profile"],
            "finance":   ["dashboard", "transactions", "send_money", "cards", "profile"],
            "ai_chat":   ["home", "chat", "history", "settings", "profile"],
            "news":      ["home", "category", "article_detail", "bookmarks", "profile"],
            "todo":      ["home", "task_detail", "categories", "calendar", "settings"],
            "food":      ["home", "restaurant_list", "menu", "cart", "orders", "profile"],
            "music":     ["home", "search", "library", "player", "profile"],
            "dashboard": ["dashboard", "analytics", "reports", "settings", "profile"],
            "utility":   ["home", "settings"],
            "education": ["home", "courses", "lesson", "quiz", "profile", "progress"],
        }
        base += screens_by_type.get(app_type,
                                     ["home", "detail", "profile", "settings"])
        return base
