import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

import actions.dev_agent as dev_agent

def test_web_project_detection():
    print("Testing web project detection and auto-preview logic...")
    
    # Create a temp project dir
    temp_dir = Path("temp_test_project")
    temp_dir.mkdir(exist_ok=True)
    (temp_dir / "index.html").write_text("<html></html>")
    
    try:
        with patch("webbrowser.open") as mock_open:
            # 1. Test _run_project with specific 'preview' command
            res = dev_agent._run_project("preview site", temp_dir)
            print(f"Preview Result: {res}")
            assert "Web project previewed" in res
            mock_open.assert_called()
            
            # Reset mock
            mock_open.reset_mock()
            
            # 2. Test _has_error for web projects
            # Web projects don't have stdout to check usually, so it should return False (no error)
            err = dev_agent._has_error("Ran with no output.", "open index.html")
            assert err is False
            print("[PASS] Web project detection passed.")

    finally:
        # Cleanup
        if (temp_dir / "index.html").exists(): (temp_dir / "index.html").unlink()
        if temp_dir.exists(): temp_dir.rmdir()

@patch("actions.dev_agent._plan_project")
@patch("actions.dev_agent._write_file")
@patch("actions.dev_agent._run_project")
@patch("webbrowser.open")
def test_build_web_project(mock_open, mock_run, mock_write, mock_plan):
    print("Testing _build_project for web projects...")
    
    mock_plan.return_value = {
        "project_name": "test_web",
        "entry_point": "index.html",
        "files": [{"path": "index.html", "description": "home"}],
        "run_command": "",
        "dependencies": []
    }
    mock_write.return_value = "<html></html>"
    mock_run.return_value = "Web project previewed"
    
    # We need to make sure the file actually exists for the auto-preview check in _build_project
    proj_dir = dev_agent.PROJECTS_DIR / "test_web"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "index.html").write_text("test")
    
    try:
        res = dev_agent._build_project("Test web site", "HTML", "test_web", 30)
        print(f"Build Result: {res}")
        assert "working" in res.lower()
        # In _build_project, it calls webbrowser.open if index.html exists
        assert mock_open.called
        print("[PASS] _build_project web support passed.")
    finally:
        if (proj_dir / "index.html").exists(): (proj_dir / "index.html").unlink()
        if proj_dir.exists(): proj_dir.rmdir()

if __name__ == "__main__":
    test_web_project_detection()
    test_build_web_project()
    print("\nAll coding mode tests passed!")
