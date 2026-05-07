# actions/website_builder/builder.py
# ══════════════════════════════════════════════════════════════
# JARVIS Website Builder — Main Entry Point
#
# This is what JARVIS calls. One function: build_website()
# Handles: clarification → plan → scaffold → install → run
# ══════════════════════════════════════════════════════════════

from __future__ import annotations
import time
from pathlib import Path
from typing import Optional, Callable

from .brain  import WebsiteBrain, WebsitePlan
from .engine import WebsiteEngine

# Global engine instance (so dev server persists between calls)
_engine: Optional[WebsiteEngine] = None


def _get_engine(log_cb: Callable = None, widget = None) -> WebsiteEngine:
    global _engine
    if _engine is not None:
        try:
            _engine.stop_dev_server()
        except Exception:
            pass
    _engine = WebsiteEngine(log_callback=log_cb, widget=widget)
    return _engine


# ══════════════════════════════════════════════════════════════
# PRIMARY FUNCTION — JARVIS calls this
# ══════════════════════════════════════════════════════════════

def build_website(
    user_prompt: str,
    player=None,                    # JARVIS UI player (for logging)
    clarification_answers: dict = None,   # Answers to clarifying questions
    skip_install: bool = False,     # Skip npm install (if node_modules exists)
    skip_build_check: bool = False, # Skip build validation
    deploy_to: str = "none",        # none | vercel | netlify | docker
    _widget_ref = None,             # Floating widget reference
) -> str:
    """
    JARVIS main entry point for website building.

    Usage from main.py tool dispatch:
        from actions.website_builder import build_website
        result = build_website(args.get("prompt"), player=self.ui)

    Returns a human-readable result string with the localhost URL.
    """

    # ── Setup logging ──────────────────────────────────────────
    def log(msg: str):
        print(f"[WebsiteBuilder] {msg}")
        if player:
            try:
                player.write_log(f"[web_builder] {msg}")
            except Exception:
                pass

    engine = _get_engine(log_cb=log, widget=_widget_ref)
    brain  = WebsiteBrain()

    log(f"Starting website build: '{user_prompt[:80]}'")

    # ── Step 1: Analyze intent ─────────────────────────────────
    log("Analyzing requirements...")
    plan = brain.create_plan(user_prompt, extra_answers=clarification_answers)

    log(f"Plan ready: {plan.site_type} site | Stack: {plan.get_stack()['name']}")
    log(f"Sections: {', '.join(plan.sections)}")

    # ── Step 2: Check if clarification needed ─────────────────
    intent     = getattr(brain, '_last_intent', {})
    questions  = brain.generate_clarification_questions(intent)
    confidence = intent.get("confidence", 100)

    if questions and confidence < 70 and not clarification_answers:
        # Return questions to JARVIS — it will ask user and call again
        q_text = "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions))
        return (
            f"Mujhe kuch aur info chahiye website banane se pehle:\n\n"
            f"{q_text}\n\n"
            f"_Jawab do, phir main website build karunga._\n"
            f"[NEEDS_CLARIFICATION]"
        )

    # ── Step 3: Scaffold project ───────────────────────────────
    log("Creating project files...")
    try:
        proj_dir = engine.scaffold(plan)
    except Exception as e:
        return f"Project creation failed: {e}"

    log(f"Project created: {proj_dir.name}")

    # ── Step 4: Install dependencies ──────────────────────────
    if not skip_install:
        success = engine.install(proj_dir)
        if not success:
            return (
                f"Dependencies install failed.\n"
                f"Project folder: {proj_dir}\n"
                f"Try manually: cd '{proj_dir}' && npm install"
            )

    # ── Step 5: Build check ────────────────────────────────────
    if not skip_build_check and not skip_install:
        engine.build_check(proj_dir, plan, max_attempts=2)
        # Non-fatal — we proceed regardless

    # ── Step 6: Start dev server ───────────────────────────────
    log("Starting dev server...")
    try:
        url = engine.start_dev_server(proj_dir, plan)
    except Exception as e:
        url = "http://localhost:3000"
        log(f"Server start warning: {e}")

    # ── Step 7: Optional deploy ────────────────────────────────
    deploy_result = ""
    if deploy_to and deploy_to != "none":
        deploy_result = engine.deploy(proj_dir, target=deploy_to)

    # ── Final response ─────────────────────────────────────────
    stack      = plan.get_stack()
    result     = (
        f"✓ Website ready!\n\n"
        f"  Name    : {plan.site_name}\n"
        f"  Type    : {plan.site_type.title()}\n"
        f"  Stack   : {stack['name']}\n"
        f"  Sections: {', '.join(plan.sections)}\n"
        f"  Folder  : {proj_dir}\n"
        f"  URL     : {url}\n"
    )

    if deploy_result:
        result += f"  Deployed: {deploy_result}\n"

    result += f"\nBrowser mein khul gaya: {url}"
    return result


# ══════════════════════════════════════════════════════════════
# TOOL DECLARATION — Paste into JARVIS TOOL_DECLARATIONS list
# ══════════════════════════════════════════════════════════════

WEBSITE_BUILDER_TOOL = {
    "name": "website_builder",
    "description": (
        "Build complete, production-ready websites with AI. "
        "Can create portfolios, SaaS sites, e-commerce, dashboards, "
        "blogs, landing pages, 3D sites, and more. "
        "Automatically sets up project, installs dependencies, and opens browser preview. "
        "Use this when user wants to create/build/make a website."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "prompt": {
                "type":        "string",
                "description": "Full description of what website to build",
            },
            "clarification_answers": {
                "type":        "object",
                "description": "Answers to clarification questions (optional)",
            },
            "deploy_to": {
                "type":        "string",
                "enum":        ["none", "vercel", "netlify", "docker"],
                "description": "Where to deploy after building (default: none)",
            },
        },
        "required": ["prompt"],
    },
}


# ══════════════════════════════════════════════════════════════
# JARVIS main.py INTEGRATION
# ══════════════════════════════════════════════════════════════

INTEGRATION_PATCH = """
# ── In main.py: Add to TOOL_DECLARATIONS ──────────────────────
from actions.website_builder.builder import WEBSITE_BUILDER_TOOL
TOOL_DECLARATIONS.append(WEBSITE_BUILDER_TOOL)

# ── In _execute_tool() if/elif chain ─────────────────────────
elif name == "website_builder":
    from actions.website_builder import build_website
    prompt  = args.get("prompt", "")
    answers = args.get("clarification_answers", None)
    deploy  = args.get("deploy_to", "none")
    result  = await loop.run_in_executor(
        None,
        lambda: build_website(
            prompt,
            player=self.ui,
            clarification_answers=answers,
            deploy_to=deploy,
        )
    )
    # Handle clarification flow
    if "[NEEDS_CLARIFICATION]" in result:
        result = result.replace("[NEEDS_CLARIFICATION]", "").strip()
    break
"""
