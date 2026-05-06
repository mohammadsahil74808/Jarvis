# actions/website_builder/codegen.py
# ══════════════════════════════════════════════════════════════
# JARVIS Website Builder — Code Generator
# Generates every file in the project using Gemini
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import re
import json
from pathlib import Path
from .brain import WebsitePlan, STACK_PROFILES
from core.ai_router import get_ai_router


class CodeGenerator:
    """
    Generates all project files.
    One Gemini call per logical unit — keeps quality high.
    """

    def __init__(self):
        self.router = get_ai_router()

    def _call(self, prompt: str) -> str:
        return self.router.generate(prompt)

    def _extract_code(self, text: str, lang: str = "") -> str:
        """Strip markdown fences from generated code."""
        pattern = rf"```(?:{lang})?\s*(.*?)```"
        match   = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        # No fences — return raw
        return text.strip()

    # ─────────────────────────────────────────────────────────
    # CONFIG FILES
    # ─────────────────────────────────────────────────────────

    def gen_package_json(self, plan: WebsitePlan) -> str:
        stack  = plan.get_stack()
        deps   = stack.get("deps", [])
        dev    = stack.get("dev_deps", [])

        deps_obj   = {d: "latest" for d in deps}
        dev_obj    = {d: "latest" for d in dev}

        framework  = stack["framework"]
        name_slug  = re.sub(r"[^a-z0-9-]", "-", plan.site_name.lower())

        if framework in ("react",):
            scripts = {
                "dev":     "vite",
                "build":   "vite build",
                "preview": "vite preview",
            }
        else:  # nextjs
            scripts = {
                "dev":   "next dev",
                "build": "next build",
                "start": "next start",
                "lint":  "next lint",
            }

        pkg = {
            "name":            name_slug or "jarvis-site",
            "version":         "1.0.0",
            "private":         True,
            "scripts":         scripts,
            "dependencies":    deps_obj,
            "devDependencies": dev_obj,
        }
        return json.dumps(pkg, indent=2)

    def gen_tailwind_config(self, plan: WebsitePlan) -> str:
        framework = plan.get_stack()["framework"]
        content   = (
            '"./src/**/*.{js,ts,jsx,tsx,mdx}",'
            '"./app/**/*.{js,ts,jsx,tsx,mdx}",'
            '"./pages/**/*.{js,ts,jsx,tsx,mdx}",'
            '"./components/**/*.{js,ts,jsx,tsx,mdx}"'
            if framework == "nextjs"
            else '"./index.html","./src/**/*.{js,ts,jsx,tsx}"'
        )
        return f"""/** @type {{import('tailwindcss').Config}} */
module.exports = {{
  content: [{content}],
  darkMode: 'class',
  theme: {{
    extend: {{
      colors: {{
        primary: '{plan.primary_color}',
        accent:  '{plan.accent_color}',
      }},
      fontFamily: {{
        display: ['var(--font-display)', 'sans-serif'],
        body:    ['var(--font-body)',    'sans-serif'],
      }},
      animation: {{
        'fade-in':    'fadeIn 0.6s ease forwards',
        'slide-up':   'slideUp 0.6s ease forwards',
        'slide-down': 'slideDown 0.5s ease forwards',
        'glow':       'glow 2s ease-in-out infinite alternate',
      }},
      keyframes: {{
        fadeIn:    {{ from: {{ opacity: '0' }},                    to: {{ opacity: '1' }} }},
        slideUp:   {{ from: {{ transform: 'translateY(30px)', opacity: '0' }}, to: {{ transform: 'translateY(0)', opacity: '1' }} }},
        slideDown: {{ from: {{ transform: 'translateY(-20px)', opacity: '0' }}, to: {{ transform: 'translateY(0)', opacity: '1' }} }},
        glow:      {{ from: {{ boxShadow: '0 0 20px {plan.primary_color}40' }}, to: {{ boxShadow: '0 0 40px {plan.primary_color}80' }} }},
      }},
    }},
  }},
  plugins: [],
}}
"""

    def gen_next_config(self, plan: WebsitePlan) -> str:
        return """/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  images: {
    domains: ['images.unsplash.com', 'via.placeholder.com'],
  },
  experimental: {
    appDir: true,
  },
}
module.exports = nextConfig
"""

    def gen_vite_config(self, plan: WebsitePlan) -> str:
        return """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    open: true,
  },
})
"""

    def gen_env_example(self, plan: WebsitePlan) -> str:
        lines = ["# Environment Variables — copy to .env.local"]
        if plan.has_auth:
            lines += [
                "NEXTAUTH_SECRET=your-secret-here",
                "NEXTAUTH_URL=http://localhost:3000",
            ]
        if plan.has_db:
            lines += ["DATABASE_URL=your-db-url-here"]
        if plan.has_ecommerce:
            lines += ["STRIPE_SECRET_KEY=sk_test_...", "STRIPE_PUBLISHABLE_KEY=pk_test_..."]
        lines += ["NEXT_PUBLIC_SITE_URL=http://localhost:3000"]
        return "\n".join(lines)

    # ─────────────────────────────────────────────────────────
    # MAIN CODE GENERATION
    # ─────────────────────────────────────────────────────────

    def gen_main_app(self, plan: WebsitePlan) -> str:
        """
        Generate the main app file with ALL sections.
        This is the most important generation call.
        """
        stack     = plan.get_stack()
        framework = stack["framework"]
        sections  = plan.sections

        anim_instructions = {
            "none":    "No animations. Clean, static layout.",
            "subtle":  "Subtle fade-ins using CSS transitions. No jarring motion.",
            "medium":  "Smooth scroll-triggered animations with Framer Motion. Section entrances.",
            "extreme": "Dramatic animations: parallax, magnetic cursor, text scramble, particle effects, GSAP timelines.",
        }.get(plan.animation_level, "medium")

        font_instructions = {
            "modern":  "Use Google Fonts: 'Space Grotesk' for headings, 'Plus Jakarta Sans' for body. Geometric, clean.",
            "classic": "Use Google Fonts: 'Playfair Display' for headings, 'Lora' for body. Elegant, editorial.",
            "minimal": "Use Google Fonts: 'DM Sans' throughout. Extremely clean, lots of whitespace.",
            "bold":    "Use Google Fonts: 'Anton' or 'Bebas Neue' for headings, 'Manrope' for body. High impact.",
        }.get(plan.font_style, "modern")

        sections_desc = "\n".join(
            f"  - {s.replace('_', ' ').title()}" for s in sections
        )

        if framework in ("react",):
            entry_file = "src/App.jsx"
            css_import = "import './index.css'"
            router_note = "Single page — all sections in one component. Use smooth scroll."
        else:
            entry_file = "app/page.tsx"
            css_import = ""
            router_note = "Next.js App Router. Use 'use client' if needed for animations."

        prompt = f"""You are a senior React/Next.js developer building a PRODUCTION-QUALITY website.

WEBSITE DETAILS:
- Type: {plan.site_type}
- Name: {plan.site_name}
- Tagline: {plan.site_tagline}
- Description: {plan.description}
- Target Audience: {plan.target_audience}

VISUAL DESIGN:
- Theme: {plan.color_theme} mode
- Primary Color: {plan.primary_color}
- Accent Color: {plan.accent_color}
- Fonts: {font_instructions}
- Animations: {anim_instructions}
- Has dark mode toggle: {plan.has_dark_mode}

TECH STACK: {stack['name']}
FILE: {entry_file}
NOTE: {router_note}

REQUIRED SECTIONS (in order):
{sections_desc}

DEPENDENCIES AVAILABLE: {', '.join(stack.get('deps', []))}

REQUIREMENTS:
1. Write COMPLETE, working {entry_file} code
2. Import Google Fonts via @import in CSS or <link> in _document
3. All sections must be FULLY implemented (not placeholder comments)
4. Mobile-first responsive design (sm: md: lg: breakpoints)
5. Use Tailwind classes for ALL styling
6. Use framer-motion for animations (if available in deps)
7. Hero section must be IMPRESSIVE — full viewport, striking typography
8. Navigation: sticky/floating with blur backdrop
9. Footer: comprehensive with links and social icons
10. Primary: {plan.primary_color} | Accent: {plan.accent_color}
11. NO placeholder text like "Lorem ipsum" — write REAL content
12. Make it look like a $10,000 professional website

IMPORTANT: Return ONLY the complete code file. No explanations. No markdown fences."""

        raw  = self._call(prompt)
        code = self._extract_code(raw, "tsx" if framework == "nextjs" else "jsx")
        return code if code else raw

    def gen_global_css(self, plan: WebsitePlan) -> str:
        """Generate global CSS with custom properties."""
        is_dark = plan.color_theme == "dark"
        bg      = "#0a0a0a"   if is_dark else "#ffffff"
        bg2     = "#111111"   if is_dark else "#f8fafc"
        text    = "#f1f5f9"   if is_dark else "#0f172a"
        muted   = "#94a3b8"   if is_dark else "#64748b"
        border  = "#1e293b"   if is_dark else "#e2e8f0"

        return f"""/* Global Styles — JARVIS Generated */
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Plus+Jakarta+Sans:ital,wght@0,300;0,400;0,500;0,600;0,700;1,400&family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=Anton&family=Manrope:wght@400;500;600;700;800&display=swap');

:root {{
  --primary:      {plan.primary_color};
  --accent:       {plan.accent_color};
  --bg:           {bg};
  --bg-secondary: {bg2};
  --text:         {text};
  --text-muted:   {muted};
  --border:       {border};
  --radius:       0.75rem;
  --shadow-glow:  0 0 40px {plan.primary_color}33;
}}

*, *::before, *::after {{
  box-sizing: border-box;
  margin:     0;
  padding:    0;
}}

html {{
  scroll-behavior: smooth;
  font-size: 16px;
  -webkit-font-smoothing: antialiased;
}}

body {{
  background-color: var(--bg);
  color:            var(--text);
  font-family:      'Plus Jakarta Sans', sans-serif;
  line-height:      1.6;
  overflow-x:       hidden;
}}

h1, h2, h3, h4, h5, h6 {{
  font-family: 'Space Grotesk', sans-serif;
  line-height: 1.2;
  font-weight: 700;
}}

::selection {{
  background: {plan.primary_color}55;
  color: var(--text);
}}

/* Scrollbar */
::-webkit-scrollbar       {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: var(--bg); }}
::-webkit-scrollbar-thumb {{ background: {plan.primary_color}88; border-radius: 3px; }}

/* Utility */
.gradient-text {{
  background: linear-gradient(135deg, {plan.primary_color}, {plan.accent_color});
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}}

.glass {{
  background:    rgba(255,255,255,0.05);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255,255,255,0.1);
}}

.glow-border {{
  border: 1px solid {plan.primary_color}44;
  box-shadow: 0 0 20px {plan.primary_color}22, inset 0 0 20px {plan.primary_color}0a;
}}

/* Animations */
@keyframes float {{
  0%, 100% {{ transform: translateY(0px); }}
  50%       {{ transform: translateY(-12px); }}
}}

@keyframes pulse-glow {{
  0%, 100% {{ opacity: 0.4; transform: scale(1); }}
  50%       {{ opacity: 0.8; transform: scale(1.05); }}
}}

@keyframes shimmer {{
  0%   {{ background-position: -200% center; }}
  100% {{ background-position:  200% center; }}
}}

.animate-float     {{ animation: float 4s ease-in-out infinite; }}
.animate-pulse-glow {{ animation: pulse-glow 3s ease-in-out infinite; }}
"""

    def gen_components(self, plan: WebsitePlan) -> dict[str, str]:
        """
        Generate reusable components that the main page uses.
        Returns dict of {filename: code}
        """
        stack     = plan.get_stack()
        framework = stack["framework"]
        ext       = "tsx" if framework == "nextjs" else "jsx"
        components = {}

        # ── Navbar ──────────────────────────────────────────
        prompt = f"""Write a complete, production-ready Navbar component for a {plan.site_type} website.

Requirements:
- Site name: {plan.site_name}
- Color theme: {plan.color_theme}
- Primary color: {plan.primary_color}
- Sticky with blur backdrop on scroll
- Mobile hamburger menu (fully working)
- Smooth scroll to sections
- Dark/light mode toggle button
- Glassmorphism effect when scrolled
- Framer Motion entrance animation
- Framework: {stack['name']}
- File extension: .{ext}

Return ONLY the complete Navbar.{ext} component code. No markdown."""

        raw = self._call(prompt)
        components[f"Navbar.{ext}"] = self._extract_code(raw, ext) or raw

        # ── Button ───────────────────────────────────────────
        components[f"Button.{ext}"] = self._gen_button_component(plan, ext)

        # ── Section wrapper ──────────────────────────────────
        components[f"Section.{ext}"] = self._gen_section_component(plan, ext)

        return components

    def _gen_button_component(self, plan: WebsitePlan, ext: str) -> str:
        return f"""import {{ motion }} from 'framer-motion'

const variants = {{
  primary:   'bg-[{plan.primary_color}] hover:bg-[{plan.accent_color}] text-white shadow-lg hover:shadow-[0_0_30px_{plan.primary_color}55]',
  secondary: 'border border-[{plan.primary_color}] text-[{plan.primary_color}] hover:bg-[{plan.primary_color}11]',
  ghost:     'text-white/70 hover:text-white hover:bg-white/5',
}}

export default function Button({{ children, variant = 'primary', className = '', onClick, href, ...props }}) {{
  const cls = `inline-flex items-center gap-2 px-6 py-3 rounded-xl font-semibold
    text-sm transition-all duration-300 cursor-pointer
    ${{variants[variant] || variants.primary}} ${{className}}`

  if (href) return (
    <motion.a href={{href}} className={{cls}}
      whileHover={{{{ scale: 1.03 }}}} whileTap={{{{ scale: 0.97 }}}}>
      {{children}}
    </motion.a>
  )

  return (
    <motion.button onClick={{onClick}} className={{cls}}
      whileHover={{{{ scale: 1.03 }}}} whileTap={{{{ scale: 0.97 }}}} {{...props}}>
      {{children}}
    </motion.button>
  )
}}
"""

    def _gen_section_component(self, plan: WebsitePlan, ext: str) -> str:
        return f"""import {{ motion }} from 'framer-motion'
import {{ useInView }} from 'framer-motion'
import {{ useRef }} from 'react'

export default function Section({{ id, className = '', children, delay = 0 }}) {{
  const ref = useRef(null)
  const isInView = useInView(ref, {{ once: true, margin: '-80px' }})

  return (
    <motion.section
      id={{id}}
      ref={{ref}}
      className={{`py-24 px-4 sm:px-6 lg:px-8 ${{className}}`}}
      initial={{{{ opacity: 0, y: 40 }}}}
      animate={{{{ opacity: isInView ? 1 : 0, y: isInView ? 0 : 40 }}}}
      transition={{{{ duration: 0.7, delay, ease: [0.25, 0.4, 0.25, 1] }}}}>
      <div className="max-w-7xl mx-auto">
        {{children}}
      </div>
    </motion.section>
  )
}}
"""

    def gen_3d_scene(self, plan: WebsitePlan) -> str:
        """Generate a Three.js / R3F 3D hero scene."""
        prompt = f"""Write a complete React Three Fiber 3D hero scene component.

Website: {plan.site_name} — {plan.description}
Primary color (hex): {plan.primary_color}
Accent color (hex): {plan.accent_color}
Theme: {plan.color_theme}

Requirements:
- Use @react-three/fiber Canvas
- Use @react-three/drei (OrbitControls, Float, Stars, Text3D if appropriate)
- Smooth, elegant 3D scene that fits the website type: {plan.site_type}
- Auto-rotating or floating elements
- Responsive canvas (full viewport width)
- Subtle particle/star field background
- Color scheme matches primary/accent colors
- Performance optimized (no heavy geometries)
- Fallback: if WebGL not available, show gradient background

Return ONLY the complete Scene3D.jsx component. No markdown."""

        raw = self._call(prompt)
        return self._extract_code(raw, "jsx") or raw

    def gen_readme(self, plan: WebsitePlan) -> str:
        stack = plan.get_stack()
        return f"""# {plan.site_name}

> {plan.site_tagline}

Built with **JARVIS Website Builder** — AI-powered next-gen site generator.

## Stack
{stack['name']}

## Quick Start

```bash
npm install
npm run dev
```

Then open [http://localhost:3000](http://localhost:3000)

## Build

```bash
npm run build
npm run start
```

## Features
{chr(10).join(f'- {s.replace("_", " ").title()}' for s in plan.sections)}

## Generated by JARVIS
This project was automatically generated by JARVIS AI Website Builder.
"""
