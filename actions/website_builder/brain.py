# actions/website_builder/brain.py
# ══════════════════════════════════════════════════════════════
# JARVIS Website Builder — AI Brain
# Handles: intent analysis, clarification questions,
#          tech stack decisions, project planning
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import Optional
from core.ai_router import get_ai_router

# ── Website types the brain can detect ────────────────────────
SITE_TYPES = {
    "portfolio":   "Personal portfolio / resume site",
    "saas":        "SaaS product landing / dashboard",
    "ecommerce":   "E-commerce / product store",
    "blog":        "Blog / content site",
    "dashboard":   "Admin / analytics dashboard",
    "landing":     "Marketing / product landing page",
    "ai_tool":     "AI-powered web tool / chatbot UI",
    "3d":          "3D immersive / interactive experience",
    "agency":      "Creative / design agency site",
    "docs":        "Documentation / developer portal",
    "restaurant":  "Restaurant / food business site",
    "event":       "Event / conference landing page",
}

# ── Tech stack profiles ────────────────────────────────────────
STACK_PROFILES = {
    "static": {
        "name":        "Static (HTML + CSS + JS)",
        "framework":   "vanilla",
        "why":         "Fast, zero overhead, best for simple sites",
        "has_backend": False,
        "has_db":      False,
        "pkg_manager": "none",
    },
    "react_basic": {
        "name":        "React + Tailwind",
        "framework":   "react",
        "why":         "Component-based, fast dev, great ecosystem",
        "has_backend": False,
        "has_db":      False,
        "pkg_manager": "npm",
        "deps": ["react", "react-dom", "tailwindcss",
                 "framer-motion", "lucide-react"],
        "dev_deps": ["@vitejs/plugin-react", "vite",
                     "autoprefixer", "postcss"],
    },
    "nextjs": {
        "name":        "Next.js + Tailwind",
        "framework":   "nextjs",
        "why":         "SSR, SEO, routing, full-stack ready",
        "has_backend": True,
        "has_db":      False,
        "pkg_manager": "npm",
        "deps": ["next", "react", "react-dom", "tailwindcss",
                 "framer-motion", "lucide-react", "@next/font"],
        "dev_deps": ["autoprefixer", "postcss"],
    },
    "nextjs_3d": {
        "name":        "Next.js + Three.js + R3F",
        "framework":   "nextjs",
        "why":         "3D experiences with React Three Fiber",
        "has_backend": False,
        "has_db":      False,
        "pkg_manager": "npm",
        "deps": ["next", "react", "react-dom", "tailwindcss",
                 "three", "@react-three/fiber", "@react-three/drei",
                 "framer-motion", "gsap", "leva"],
        "dev_deps": ["autoprefixer", "postcss", "@types/three"],
    },
    "nextjs_full": {
        "name":        "Next.js + Prisma + Auth",
        "framework":   "nextjs",
        "why":         "Full-stack with DB, auth, API routes",
        "has_backend": True,
        "has_db":      True,
        "pkg_manager": "npm",
        "deps": ["next", "react", "react-dom", "tailwindcss",
                 "framer-motion", "lucide-react", "next-auth",
                 "prisma", "@prisma/client", "bcryptjs", "zod"],
        "dev_deps": ["autoprefixer", "postcss", "@types/bcryptjs"],
    },
}

# ── Site type → recommended stack mapping ─────────────────────
SITE_TO_STACK = {
    "portfolio":  "react_basic",
    "saas":       "nextjs_full",
    "ecommerce":  "nextjs_full",
    "blog":       "nextjs",
    "dashboard":  "nextjs",
    "landing":    "react_basic",
    "ai_tool":    "nextjs",
    "3d":         "nextjs_3d",
    "agency":     "react_basic",
    "docs":       "nextjs",
    "restaurant": "react_basic",
    "event":      "react_basic",
}


@dataclass
class WebsitePlan:
    """Complete plan for a website — output of the AI brain."""
    # Core identity
    site_type:       str = "landing"
    site_name:       str = "My Website"
    site_tagline:    str = ""
    description:     str = ""

    # Visual design
    color_theme:     str = "dark"          # dark | light | auto
    primary_color:   str = "#6366f1"
    accent_color:    str = "#a855f7"
    font_style:      str = "modern"        # modern | classic | minimal | bold
    animation_level: str = "medium"        # none | subtle | medium | extreme

    # Features
    has_3d:          bool = False
    has_auth:        bool = False
    has_db:          bool = False
    has_blog:        bool = False
    has_ecommerce:   bool = False
    has_contact:     bool = True
    has_dark_mode:   bool = True
    has_animations:  bool = True

    # Tech
    stack_key:       str = "react_basic"
    target_audience: str = "general"

    # Sections (ordered list)
    sections: list[str] = field(default_factory=list)

    # Raw AI extras
    extra_context:   str = ""
    deploy_target:   str = "none"     # none | vercel | netlify | docker

    def get_stack(self) -> dict:
        return STACK_PROFILES.get(self.stack_key, STACK_PROFILES["react_basic"])

    def to_json(self) -> str:
        import dataclasses
        return json.dumps(dataclasses.asdict(self), indent=2)


# ══════════════════════════════════════════════════════════════
class WebsiteBrain:
    """
    AI brain — analyzes user prompt, asks clarification,
    decides stack, produces WebsitePlan.
    """

    def __init__(self):
        self.router = get_ai_router()

    def _call(self, prompt: str, json_mode: bool = True) -> str:
        text = self.router.generate(prompt)
        if json_mode:
            # Strip markdown fences
            text = re.sub(r"```(?:json)?\s*", "", text)
            text = re.sub(r"```\s*$", "", text).strip()
        return text

    # ─────────────────────────────────────────────────────────
    def analyze_intent(self, user_prompt: str) -> dict:
        """
        Step 1: Analyze user prompt.
        Returns dict with detected intent + missing info.
        """
        prompt = f"""You are a website planning AI. Analyze this request:
"{user_prompt}"

Return ONLY valid JSON (no markdown, no extra text):
{{
  "site_type": "<one of: {', '.join(SITE_TYPES.keys())}>",
  "site_name": "<extracted or suggested name>",
  "site_tagline": "<short tagline>",
  "description": "<what this site does>",
  "color_theme": "<dark|light|auto>",
  "primary_color": "<hex color that fits the vibe>",
  "accent_color": "<hex accent color>",
  "font_style": "<modern|classic|minimal|bold>",
  "animation_level": "<none|subtle|medium|extreme>",
  "has_3d": <true|false>,
  "has_auth": <true|false>,
  "has_db": <true|false>,
  "has_blog": <true|false>,
  "has_ecommerce": <true|false>,
  "has_contact": <true|false>,
  "has_dark_mode": <true|false>,
  "target_audience": "<who will use this>",
  "sections": ["<section1>", "<section2>", ...],
  "missing_info": ["<what info is still needed to proceed>"],
  "confidence": <0-100 how confident about requirements>
}}

Rules:
- sections: list page sections in order (e.g. hero, about, features, pricing, contact)
- missing_info: list things user didn't mention but are needed. Empty [] if confident.
- confidence: 100 = user gave complete info, 0 = too vague
- Be smart about inferring from context. "cool dark portfolio for developer" = high confidence"""

        raw = self._call(prompt)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Emergency fallback
            return {
                "site_type":       "landing",
                "site_name":       "My Website",
                "site_tagline":    "Built with JARVIS",
                "description":     user_prompt[:200],
                "color_theme":     "dark",
                "primary_color":   "#6366f1",
                "accent_color":    "#a855f7",
                "font_style":      "modern",
                "animation_level": "medium",
                "has_3d":          False,
                "has_auth":        False,
                "has_db":          False,
                "has_blog":        False,
                "has_ecommerce":   False,
                "has_contact":     True,
                "has_dark_mode":   True,
                "target_audience": "general",
                "sections":        ["hero", "features", "about", "contact"],
                "missing_info":    [],
                "confidence":      60,
            }

    # ─────────────────────────────────────────────────────────
    def generate_clarification_questions(self, intent: dict) -> list[str]:
        """
        Step 2: If confidence < 70 or missing_info exists,
        generate smart questions to ask user.
        """
        missing = intent.get("missing_info", [])
        confidence = intent.get("confidence", 100)

        if confidence >= 80 and not missing:
            return []

        questions = []

        # Always-useful questions based on site type
        site_type = intent.get("site_type", "landing")

        if site_type == "portfolio" and not intent.get("site_name"):
            questions.append("Apna naam kya hai? (portfolio mein dikhana hai)")

        if site_type in ("saas", "ai_tool") and not intent.get("description"):
            questions.append("Tumhara product kya karta hai? (1-2 lines mein)")

        if site_type == "ecommerce":
            questions.append("Kya bechna hai? (products ka type)")

        if not intent.get("primary_color") or intent["primary_color"] == "#6366f1":
            questions.append("Color theme kaisa chahiye? (dark/light, ya specific color like blue/red/green)")

        if site_type in ("portfolio", "agency"):
            questions.append("Koi specific skills, projects, ya work dikhane hain?")

        if intent.get("has_auth") is None:
            if site_type in ("saas", "dashboard", "ecommerce"):
                questions.append("Login/signup system chahiye? (haan/nahi)")

        # Add AI-generated questions for missing items
        for item in missing[:2]:  # Max 2 extra
            questions.append(f"{item}?")

        return questions[:4]  # Max 4 questions total

    # ─────────────────────────────────────────────────────────
    def decide_stack(self, intent: dict) -> str:
        """Step 3: Pick best tech stack based on requirements."""
        site_type  = intent.get("site_type",     "landing")
        has_3d     = intent.get("has_3d",         False)
        has_auth   = intent.get("has_auth",        False)
        has_db     = intent.get("has_db",          False)
        has_ecom   = intent.get("has_ecommerce",   False)
        animations = intent.get("animation_level", "medium")

        # 3D overrides everything
        if has_3d or site_type == "3d":
            return "nextjs_3d"

        # Full stack needed
        if has_auth or has_db or has_ecom or site_type in ("saas", "ecommerce"):
            return "nextjs_full"

        # SEO-critical sites
        if site_type in ("blog", "docs", "saas"):
            return "nextjs"

        # Simple + fast
        return SITE_TO_STACK.get(site_type, "react_basic")

    # ─────────────────────────────────────────────────────────
    def create_plan(self, user_prompt: str,
                    extra_answers: Optional[dict] = None) -> WebsitePlan:
        """
        Master method: analyze → decide → return complete plan.
        extra_answers: dict of clarification answers from user.
        """
        # Merge answers into prompt
        full_prompt = user_prompt
        if extra_answers:
            extras = "\n".join(f"- {k}: {v}" for k, v in extra_answers.items())
            full_prompt += f"\n\nAdditional details:\n{extras}"

        intent    = self.analyze_intent(full_prompt)
        stack_key = self.decide_stack(intent)

        # Build sections if not detected
        sections = intent.get("sections") or []
        if not sections:
            sections = self._default_sections(intent.get("site_type", "landing"))

        plan = WebsitePlan(
            site_type       = intent.get("site_type",       "landing"),
            site_name       = intent.get("site_name",       "My Website"),
            site_tagline    = intent.get("site_tagline",    ""),
            description     = intent.get("description",     full_prompt[:300]),
            color_theme     = intent.get("color_theme",     "dark"),
            primary_color   = intent.get("primary_color",   "#6366f1"),
            accent_color    = intent.get("accent_color",    "#a855f7"),
            font_style      = intent.get("font_style",      "modern"),
            animation_level = intent.get("animation_level", "medium"),
            has_3d          = intent.get("has_3d",          False),
            has_auth        = intent.get("has_auth",        False),
            has_db          = intent.get("has_db",          False),
            has_blog        = intent.get("has_blog",        False),
            has_ecommerce   = intent.get("has_ecommerce",   False),
            has_contact     = intent.get("has_contact",     True),
            has_dark_mode   = intent.get("has_dark_mode",   True),
            has_animations  = intent.get("animation_level", "medium") != "none",
            stack_key       = stack_key,
            target_audience = intent.get("target_audience", "general"),
            sections        = sections,
            extra_context   = full_prompt,
        )
        return plan

    def _default_sections(self, site_type: str) -> list[str]:
        defaults = {
            "portfolio":  ["hero", "about", "skills", "projects", "contact"],
            "saas":       ["hero", "features", "how_it_works", "pricing", "testimonials", "cta"],
            "ecommerce":  ["hero", "categories", "featured_products", "deals", "newsletter"],
            "blog":       ["hero", "recent_posts", "categories", "newsletter"],
            "dashboard":  ["sidebar", "stats_overview", "charts", "recent_activity"],
            "landing":    ["hero", "features", "about", "testimonials", "cta", "contact"],
            "ai_tool":    ["hero", "demo", "features", "how_it_works", "cta"],
            "3d":         ["hero_3d", "about", "work", "contact"],
            "agency":     ["hero", "services", "work", "team", "contact"],
            "docs":       ["hero", "quick_start", "guides", "api_reference"],
            "restaurant": ["hero", "menu", "about", "reservations", "location"],
            "event":      ["hero", "schedule", "speakers", "venue", "register"],
        }
        return defaults.get(site_type, ["hero", "features", "about", "contact"])

    # ─────────────────────────────────────────────────────────
    def suggest_improvements(self, plan: WebsitePlan,
                              current_code: str) -> str:
        """
        AI UI improver — looks at generated code and suggests
        specific improvements.
        """
        prompt = f"""You are a senior UI/UX engineer reviewing a website.

Website type: {plan.site_type}
Stack: {plan.stack_key}
Color theme: {plan.color_theme}
Animation level: {plan.animation_level}

Current code snippet (first 2000 chars):
{current_code[:2000]}

Give 3-5 SPECIFIC, actionable UI improvements as JSON array:
[
  {{
    "area": "typography",
    "issue": "body text too small",
    "fix": "change text-sm to text-base on paragraphs"
  }},
  ...
]

Focus on: visual hierarchy, spacing, contrast, animations, mobile responsiveness."""

        raw = self._call(prompt)
        try:
            return json.loads(raw)
        except Exception:
            return []
