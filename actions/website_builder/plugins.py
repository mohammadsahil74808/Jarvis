# actions/website_builder/plugins.py
# ══════════════════════════════════════════════════════════════
# JARVIS Website Builder — Plugin & Template System
#
# Plugins: extend builder with new capabilities
# Templates: pre-built site blueprints for instant use
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import json
from pathlib import Path
from typing import Callable, Optional
from dataclasses import dataclass, field
from .brain import WebsitePlan


# ══════════════════════════════════════════════════════════════
# PLUGIN SYSTEM
# ══════════════════════════════════════════════════════════════

@dataclass
class Plugin:
    """
    A plugin extends the builder with new capabilities.
    Hook into any stage of the build pipeline.
    """
    name:        str
    description: str
    version:     str = "1.0.0"
    author:      str = "JARVIS"

    # Hooks — set to None to skip
    on_plan_ready:    Optional[Callable[[WebsitePlan], WebsitePlan]] = None
    on_files_created: Optional[Callable[[Path, WebsitePlan], None]]  = None
    on_install_done:  Optional[Callable[[Path, WebsitePlan], None]]  = None
    on_server_start:  Optional[Callable[[str, WebsitePlan], None]]   = None
    on_build_error:   Optional[Callable[[str, Path], str]]           = None

    def __repr__(self):
        return f"Plugin({self.name} v{self.version})"


class PluginRegistry:
    """Global plugin registry."""

    def __init__(self):
        self._plugins: list[Plugin] = []
        self._load_defaults()

    def register(self, plugin: Plugin):
        """Register a plugin."""
        existing = [p for p in self._plugins if p.name == plugin.name]
        if existing:
            self._plugins.remove(existing[0])
        self._plugins.append(plugin)
        print(f"[PluginRegistry] Registered: {plugin}")

    def unregister(self, name: str):
        """Remove a plugin by name."""
        self._plugins = [p for p in self._plugins if p.name != name]

    def get(self, name: str) -> Optional[Plugin]:
        return next((p for p in self._plugins if p.name == name), None)

    def list_plugins(self) -> list[str]:
        return [f"{p.name} v{p.version} — {p.description}" for p in self._plugins]

    # ── Hook runners ──────────────────────────────────────────
    def run_plan_ready(self, plan: WebsitePlan) -> WebsitePlan:
        for p in self._plugins:
            if p.on_plan_ready:
                try:
                    plan = p.on_plan_ready(plan) or plan
                except Exception as e:
                    print(f"[Plugin {p.name}] on_plan_ready error: {e}")
        return plan

    def run_files_created(self, proj_dir: Path, plan: WebsitePlan):
        for p in self._plugins:
            if p.on_files_created:
                try:
                    p.on_files_created(proj_dir, plan)
                except Exception as e:
                    print(f"[Plugin {p.name}] on_files_created error: {e}")

    def run_install_done(self, proj_dir: Path, plan: WebsitePlan):
        for p in self._plugins:
            if p.on_install_done:
                try:
                    p.on_install_done(proj_dir, plan)
                except Exception as e:
                    print(f"[Plugin {p.name}] on_install_done error: {e}")

    def run_server_start(self, url: str, plan: WebsitePlan):
        for p in self._plugins:
            if p.on_server_start:
                try:
                    p.on_server_start(url, plan)
                except Exception as e:
                    print(f"[Plugin {p.name}] on_server_start error: {e}")

    def _load_defaults(self):
        """Register built-in plugins."""
        self.register(SEOPlugin())
        self.register(PerformancePlugin())
        self.register(AccessibilityPlugin())





# ── Built-in Plugins ──────────────────────────────────────────

def SEOPlugin() -> Plugin:
    """Adds sitemap.xml and robots.txt to every project."""
    def on_files_created(proj_dir: Path, plan: WebsitePlan):
        public = proj_dir / "public"
        public.mkdir(exist_ok=True)

        # robots.txt
        (public / "robots.txt").write_text(
            "User-agent: *\nAllow: /\nSitemap: /sitemap.xml\n")

        # sitemap.xml
        sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://example.com/</loc>
    <lastmod>{__import__('datetime').date.today()}</lastmod>
    <priority>1.0</priority>
  </url>
</urlset>"""
        (public / "sitemap.xml").write_text(sitemap)

    return Plugin(
        name="seo",
        description="Auto-adds robots.txt and sitemap.xml",
        on_files_created=on_files_created,
    )


def PerformancePlugin() -> Plugin:
    """Adds performance-related config tweaks."""
    def on_plan_ready(plan: WebsitePlan) -> WebsitePlan:
        # Force reasonable animation level for performance
        if plan.animation_level == "extreme" and plan.has_3d:
            plan.animation_level = "medium"
            print("[PerformancePlugin] Reduced animation level (3D + extreme = lag)")
        return plan

    return Plugin(
        name="performance",
        description="Optimizes animation levels and build config",
        on_plan_ready=on_plan_ready,
    )


def AccessibilityPlugin() -> Plugin:
    """Adds aria-label reminders to generated code (post-gen hook)."""
    def on_files_created(proj_dir: Path, plan: WebsitePlan):
        # Create a11y checklist
        checklist = """# Accessibility Checklist (Generated by JARVIS)
- [ ] All images have alt text
- [ ] Color contrast ratio >= 4.5:1 for normal text
- [ ] Keyboard navigation works (Tab through all interactive elements)
- [ ] Focus indicators visible
- [ ] Form inputs have labels
- [ ] Headings in correct order (h1 → h2 → h3)
- [ ] Skip navigation link present
- [ ] ARIA landmarks: header, main, footer, nav
"""
        (proj_dir / "A11Y_CHECKLIST.md").write_text(checklist)

    return Plugin(
        name="accessibility",
        description="Adds accessibility checklist to project",
        on_files_created=on_files_created,
    )



# Singleton
plugin_registry = PluginRegistry()


# ══════════════════════════════════════════════════════════════
# TEMPLATE SYSTEM
# ══════════════════════════════════════════════════════════════

@dataclass
class SiteTemplate:
    """
    Pre-built plan blueprint.
    Users can say "use portfolio template" to get instant config.
    """
    name:        str
    description: str
    preview_url: str = ""
    tags:        list[str] = field(default_factory=list)
    plan_data:   dict = field(default_factory=dict)

    def to_plan(self, overrides: dict = None) -> WebsitePlan:
        """Convert template to WebsitePlan, apply user overrides."""
        data = {**self.plan_data, **(overrides or {})}
        return WebsitePlan(**{
            k: v for k, v in data.items()
            if k in WebsitePlan.__dataclass_fields__
        })


TEMPLATES: dict[str, SiteTemplate] = {

    "dev_portfolio": SiteTemplate(
        name="Developer Portfolio",
        description="Dark, minimal portfolio for developers/engineers",
        tags=["portfolio", "developer", "dark"],
        plan_data={
            "site_type":       "portfolio",
            "site_name":       "My Portfolio",
            "site_tagline":    "Building the future, one commit at a time",
            "color_theme":     "dark",
            "primary_color":   "#00d4ff",
            "accent_color":    "#7c3aed",
            "font_style":      "modern",
            "animation_level": "medium",
            "stack_key":       "react_basic",
            "sections": ["hero", "about", "skills", "projects", "contact"],
            "has_dark_mode":   True,
            "has_contact":     True,
        }
    ),

    "saas_landing": SiteTemplate(
        name="SaaS Landing Page",
        description="High-converting SaaS product landing with pricing",
        tags=["saas", "startup", "conversion"],
        plan_data={
            "site_type":       "saas",
            "site_name":       "ProductName",
            "site_tagline":    "The smarter way to get things done",
            "color_theme":     "dark",
            "primary_color":   "#6366f1",
            "accent_color":    "#ec4899",
            "font_style":      "modern",
            "animation_level": "medium",
            "stack_key":       "nextjs",
            "sections": ["hero", "features", "how_it_works",
                         "pricing", "testimonials", "faq", "cta"],
            "has_dark_mode":   True,
            "has_contact":     True,
        }
    ),

    "creative_agency": SiteTemplate(
        name="Creative Agency",
        description="Bold, animated agency site with 3D elements",
        tags=["agency", "creative", "3d", "bold"],
        plan_data={
            "site_type":       "agency",
            "site_name":       "Studio Name",
            "site_tagline":    "We craft digital experiences",
            "color_theme":     "dark",
            "primary_color":   "#ff6b35",
            "accent_color":    "#f7c59f",
            "font_style":      "bold",
            "animation_level": "extreme",
            "stack_key":       "nextjs_3d",
            "has_3d":          True,
            "sections": ["hero_3d", "services", "work",
                         "process", "team", "contact"],
            "has_dark_mode":   True,
        }
    ),

    "minimal_blog": SiteTemplate(
        name="Minimal Blog",
        description="Clean, typographic blog with light theme",
        tags=["blog", "minimal", "light", "typography"],
        plan_data={
            "site_type":       "blog",
            "site_name":       "The Journal",
            "site_tagline":    "Thoughts, ideas, and stories",
            "color_theme":     "light",
            "primary_color":   "#1a1a1a",
            "accent_color":    "#d97706",
            "font_style":      "classic",
            "animation_level": "subtle",
            "stack_key":       "nextjs",
            "has_blog":        True,
            "sections": ["hero", "recent_posts",
                         "categories", "newsletter"],
            "has_dark_mode":   True,
        }
    ),

    "ai_tool": SiteTemplate(
        name="AI Tool",
        description="Futuristic AI product UI with glow effects",
        tags=["ai", "tool", "futuristic", "dark"],
        plan_data={
            "site_type":       "ai_tool",
            "site_name":       "AI Tool",
            "site_tagline":    "Intelligence at your fingertips",
            "color_theme":     "dark",
            "primary_color":   "#00ff88",
            "accent_color":    "#00d4ff",
            "font_style":      "modern",
            "animation_level": "extreme",
            "stack_key":       "nextjs",
            "sections": ["hero", "demo",
                         "features", "how_it_works", "cta"],
            "has_dark_mode":   True,
            "has_contact":     True,
        }
    ),

    "ecommerce": SiteTemplate(
        name="E-Commerce Store",
        description="Full e-commerce with cart, products, Stripe",
        tags=["ecommerce", "store", "stripe"],
        plan_data={
            "site_type":       "ecommerce",
            "site_name":       "Shop",
            "site_tagline":    "Shop the finest collection",
            "color_theme":     "light",
            "primary_color":   "#111827",
            "accent_color":    "#6366f1",
            "font_style":      "minimal",
            "animation_level": "subtle",
            "stack_key":       "nextjs_full",
            "has_ecommerce":   True,
            "has_auth":        True,
            "has_db":          True,
            "sections": ["hero", "categories",
                         "featured_products", "deals", "newsletter"],
            "has_dark_mode":   True,
        }
    ),

    "3d_portfolio": SiteTemplate(
        name="3D Portfolio",
        description="Immersive 3D portfolio with Three.js",
        tags=["portfolio", "3d", "threejs", "immersive"],
        plan_data={
            "site_type":       "3d",
            "site_name":       "3D Portfolio",
            "site_tagline":    "An experience, not just a website",
            "color_theme":     "dark",
            "primary_color":   "#a855f7",
            "accent_color":    "#06b6d4",
            "font_style":      "modern",
            "animation_level": "extreme",
            "stack_key":       "nextjs_3d",
            "has_3d":          True,
            "sections": ["hero_3d", "about",
                         "work", "skills", "contact"],
            "has_dark_mode":   True,
        }
    ),

    "restaurant": SiteTemplate(
        name="Restaurant Website",
        description="Elegant restaurant site with menu and reservations",
        tags=["restaurant", "food", "elegant"],
        plan_data={
            "site_type":       "restaurant",
            "site_name":       "Restaurant Name",
            "site_tagline":    "Fine dining, unforgettable moments",
            "color_theme":     "dark",
            "primary_color":   "#d4a853",
            "accent_color":    "#8b1a1a",
            "font_style":      "classic",
            "animation_level": "subtle",
            "stack_key":       "react_basic",
            "sections": ["hero", "menu", "about",
                         "reservations", "gallery", "location"],
            "has_contact":     True,
        }
    ),
}


def get_template(name: str) -> Optional[SiteTemplate]:
    """Get template by name (fuzzy match)."""
    name_lower = name.lower().strip()
    # Exact match
    if name_lower in TEMPLATES:
        return TEMPLATES[name_lower]
    # Fuzzy match
    for key, tmpl in TEMPLATES.items():
        if name_lower in key or name_lower in tmpl.name.lower():
            return tmpl
    return None


def list_templates() -> str:
    """Return formatted list of all templates."""
    lines = ["Available website templates:\n"]
    for key, tmpl in TEMPLATES.items():
        tags = ", ".join(tmpl.tags)
        lines.append(f"  {key:<20} — {tmpl.description}")
        lines.append(f"  {'':20}   Tags: {tags}\n")
    return "\n".join(lines)
