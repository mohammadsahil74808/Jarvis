# tests/test_search_result_selection.py
"""
Focused unit tests for structured Google search result identification, filtering,
ordinal/title resolution, and session-preserved search context retention.
"""

import pytest
from unittest.mock import patch, MagicMock
from jarvis.browser.search_resolver import build_structured_search_results, resolve_search_result_target, is_search_result_request
from jarvis.browser.browser_controller import BrowserController
from jarvis.browser.browser_state import BrowserState


@pytest.fixture
def sample_raw_results():
    return [
        # Google navigation & Ads (Should be ignored by Test #6)
        {"title": "Google Accounts", "url": "https://accounts.google.com/signin", "snippet": "Sign in to your Google Account"},
        {"title": "Sponsored - Best AI Tools 2026", "url": "https://ai-promo-example.com", "snippet": "Sponsored advertisement for AI services"},
        {"title": "OpenAI Ad", "url": "https://openai-reseller.ru", "snippet": "Advertisement why this ad"},
        {"title": "People also ask", "url": "https://www.google.com/search?q=what+is+ai", "snippet": "Accordion more questions"},
        
        # Organic Results (Ranks 1, 2, 3...)
        {"title": "OpenAI: Creating safe AGI", "url": "https://openai.com", "snippet": "OpenAI is an AI research and deployment company."},
        {"title": "OpenAI - GitHub", "url": "https://github.com/openai", "snippet": "Official GitHub repositories and code for OpenAI tools."},
        {"title": "ChatGPT Web Inactive", "url": "https://chat.openai.com", "snippet": "Experience ChatGPT, a sophisticated language AI model."},
        {"title": "Netlify: Develop & deploy web apps", "url": "https://netlify.com", "snippet": "Modern frontend development platforms and cloud deployment."}
    ]


def test_google_ads_and_navigation_ignored(sample_raw_results):
    """Test 6: Google ads, sponsored sections, people also ask, and Google navigation links are ignored."""
    structured = build_structured_search_results(sample_raw_results)
    urls = [r["url"] for r in structured]

    # Verify ads, sponsored, Google accounts, and "People also ask" are excluded
    assert "https://accounts.google.com/signin" not in urls
    assert "https://ai-promo-example.com" not in urls
    assert "https://openai-reseller.ru" not in urls
    assert "https://www.google.com/search?q=what+is+ai" not in urls

    # Verify only pure organic links remain
    assert len(structured) == 4
    assert structured[0]["url"] == "https://openai.com"
    assert structured[0]["rank"] == 1
    assert structured[1]["url"] == "https://github.com/openai"
    assert structured[1]["rank"] == 2


def test_first_organic_result(sample_raw_results):
    """Test 1: first organic result selection via ordinals in English & Hindi."""
    structured = build_structured_search_results(sample_raw_results)
    
    for prompt in ["pehla result kholo", "first result kholo", "open the first result", "1st result", "pehla"]:
        match = resolve_search_result_target(prompt, structured)
        assert match is not None, f"Failed to match for prompt: {prompt}"
        assert match["rank"] == 1
        assert match["url"] == "https://openai.com"


def test_second_organic_result(sample_raw_results):
    """Test 2: second organic result selection."""
    structured = build_structured_search_results(sample_raw_results)
    
    for prompt in ["doosra result kholo", "second result kholo", "open the second search result", "2nd result"]:
        match = resolve_search_result_target(prompt, structured)
        assert match is not None, f"Failed to match for prompt: {prompt}"
        assert match["rank"] == 2
        assert match["url"] == "https://github.com/openai"


def test_third_organic_result(sample_raw_results):
    """Test 3: third organic result selection."""
    structured = build_structured_search_results(sample_raw_results)
    
    for prompt in ["teesra result kholo", "third result", "open the third result", "tisra result"]:
        match = resolve_search_result_target(prompt, structured)
        assert match is not None, f"Failed to match for prompt: {prompt}"
        assert match["rank"] == 3
        assert match["url"] == "https://chat.openai.com"


def test_result_number_parsing(sample_raw_results):
    """Test 4: result-number parsing (e.g., 'result number 2', 'result 4', '#3')."""
    structured = build_structured_search_results(sample_raw_results)
    
    test_cases = {
        "result number 2": 2,
        "result 4 kholo": 4,
        "open result no. 1": 1,
        "#3": 3,
        "result 2": 2
    }
    for prompt, expected_rank in test_cases.items():
        match = resolve_search_result_target(prompt, structured)
        assert match is not None, f"Failed on prompt: '{prompt}'"
        assert match["rank"] == expected_rank


def test_title_based_result_selection(sample_raw_results):
    """Test 5: title-based result selection (e.g., 'Open the GitHub result', 'result about Netlify')."""
    structured = build_structured_search_results(sample_raw_results)
    
    match_gh = resolve_search_result_target("Open the GitHub result", structured)
    assert match_gh is not None
    assert match_gh["url"] == "https://github.com/openai"
    assert match_gh["rank"] == 2

    match_net = resolve_search_result_target("Open the result about Netlify", structured)
    assert match_net is not None
    assert match_net["url"] == "https://netlify.com"
    assert match_net["rank"] == 4


def test_search_context_retention_and_execution():
    """Test 7: search context being retained between 'search' and 'open result' in BrowserController without changing browser architecture."""
    controller = BrowserController()
    controller.state = BrowserState()

    mock_structured = [
        {"rank": 1, "number": 1, "title": "OpenAI Official", "url": "https://openai.com", "snippet": "AI research", "target": 'a[href="https://openai.com"]'},
        {"rank": 2, "number": 2, "title": "OpenAI GitHub", "url": "https://github.com/openai", "snippet": "Code repositories", "target": 'a[href="https://github.com/openai"]'},
    ]

    with patch("jarvis.browser.search_resolver.extract_organic_search_results", return_value=mock_structured), \
         patch.object(controller, "open_website", return_value="Successfully opened website") as mock_open:
        
        # Step 1: Execute search
        search_res = controller.search_web("OpenAI")
        assert "Found 2 structured results" in search_res
        assert controller.state.last_search_query == "OpenAI"
        assert len(controller.state.search_results) == 2
        assert "results" in controller.state.search_context

        # Step 2: Open first result in subsequent command using retained context
        open_res = controller.open_search_result("pehla result kholo")
        assert "Opened search result #1: OpenAI Official" in open_res
        
        # Verify open_website was called with the exact verified organic link
        mock_open.assert_called_with("https://openai.com")

        # Step 3: Test action routing via click_element and open_website interception
        assert is_search_result_request("doosra result kholo")
        res2 = controller.click_element("doosra result kholo")
        assert "Opened search result #2: OpenAI GitHub" in res2
        mock_open.assert_called_with("https://github.com/openai")


def test_no_wrong_fallback():
    """Test 8: Ensure deterministic error message when result is unavailable without guessing URLs or converting queries."""
    controller = BrowserController()
    controller.state = BrowserState()
    
    # Test out of bounds result on existing state
    res = controller.open_search_result("99")
    assert "Search result #99 is not available because Google results could not be inspected" in res
    assert "DO NOT guess a URL" in res

    # Test when memory is empty and cannot be inspected
    with patch.object(controller.state, "load_persistent_state", return_value=None), \
         patch("json.loads", side_effect=Exception("No disk memory")):
        controller.state.search_results = []
        res2 = controller.open_search_result("2")
        assert "Search result #2 is not available because Google results could not be inspected" in res2
        assert "DO NOT guess a URL" in res2
