import pytest
from playwright.sync_api import Page, expect

def test_jarvis_browser_page_title(page: Page):
    """
    Test that the playwright environment is properly configured.
    """
    page.goto("https://example.com")
    expect(page).to_have_title("Example Domain")

def test_jarvis_browser_interaction(page: Page):
    """
    Test basic interaction.
    """
    page.goto("https://example.com")
    element = page.locator("h1")
    expect(element).to_have_text("Example Domain")
