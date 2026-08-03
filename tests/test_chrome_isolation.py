import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure jarvis/browser is in sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "jarvis" / "browser"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from jarvis.browser.browser_context import (
    find_real_chrome_user_data,
    get_chrome_automation_config,
    get_jarvis_dedicated_profile_dir,
    ensure_chrome_running_with_cdp
)


def test_dedicated_profile_isolation():
    """Verify JARVIS dedicated profile path is inside project memory and distinct from personal profile."""
    dedicated = get_jarvis_dedicated_profile_dir()
    personal = find_real_chrome_user_data()

    assert "browser_profile" in str(dedicated).lower()
    if personal:
        assert str(dedicated).lower() != str(personal).lower()
        assert "user_data_devtools" not in str(dedicated).lower()


def test_config_never_exposes_personal_user_data_for_launch():
    """Verify get_chrome_automation_config uses dedicated profile dir."""
    with patch("jarvis.browser.browser_context.ensure_chrome_running_with_cdp", return_value="http://127.0.0.1:9222"):
        cfg = get_chrome_automation_config()
        personal = find_real_chrome_user_data()
        assert "user_data_dir" in cfg
        if personal:
            assert str(cfg["user_data_dir"]).lower() != str(personal).lower()


def test_mode_a_existing_chrome_attachment():
    """Verify MODE A attaches to existing Chrome without starting a new subprocess."""
    with patch("jarvis.browser.browser_context.check_chrome_cdp_endpoint", return_value="http://127.0.0.1:9222"):
        with patch("subprocess.Popen") as mock_popen:
            res = ensure_chrome_running_with_cdp(9222)
            assert res == "http://127.0.0.1:9222"
            mock_popen.assert_not_called()


def test_mode_b_dedicated_profile_launch():
    """Verify MODE B launches Chrome using ONLY dedicated JARVIS profile and never personal profile."""
    call_count = 0
    def mock_check(port=9222):
        nonlocal call_count
        call_count += 1
        if call_count > 1:
            return f"http://127.0.0.1:{port}"
        return None

    with patch("jarvis.browser.browser_context.check_chrome_cdp_endpoint", side_effect=mock_check):
        with patch("subprocess.Popen") as mock_popen:
            res = ensure_chrome_running_with_cdp(9222)
            assert res is not None
            mock_popen.assert_called_once()
            cmd = mock_popen.call_args[0][0]
            
            # Verify user-data-dir flag points to dedicated JARVIS profile
            user_data_arg = [arg for arg in cmd if arg.startswith("--user-data-dir=")][0]
            personal = find_real_chrome_user_data()
            dedicated = get_jarvis_dedicated_profile_dir()

            assert str(dedicated).lower() in user_data_arg.lower()
            if personal:
                assert str(personal).lower() not in user_data_arg.lower()
            assert "user_data_devtools" not in user_data_arg.lower()
