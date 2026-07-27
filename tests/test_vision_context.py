from vision.context import ScreenContext
from vision.context_store import get_screen_context, update_screen_context


def test_screen_context_prompt_includes_structured_fields():
    ctx = ScreenContext(
        status="ok",
        timestamp="2026-07-27T00:00:00Z",
        active_application="Code",
        active_window_title="main.py - Jarvis - Visual Studio Code",
        visible_text="Traceback\nRuntimeError: build failed",
        error_popups=["RuntimeError: build failed"],
        git_branch="feature/vision",
        current_project="Jarvis",
    )

    prompt = ctx.to_prompt()

    assert "Active app: Code" in prompt
    assert "RuntimeError: build failed" in prompt
    assert "Git Branch: feature/vision" in prompt


def test_screen_context_store_exposes_latest_context():
    ctx = ScreenContext(status="ok", active_application="Terminal")

    update_screen_context(ctx)

    assert get_screen_context().active_application == "Terminal"
