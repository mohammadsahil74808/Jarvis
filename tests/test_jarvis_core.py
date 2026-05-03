import pytest
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from actions.file_manager import delete_file
from agent.planner import create_plan
from memory.semantic_memory import get_semantic_memory

def test_file_manager_delete_no_confirm():
    """Verify that deleting a file without confirm=True fails."""
    result = delete_file("dummy.txt", confirm=False)
    assert "Deletion blocked" in result

def test_planner_multi_step():
    """Verify that multi-step goals produce multiple steps."""
    plan = create_plan("Research AI and save to ai.txt")
    assert len(plan["steps"]) >= 2

def test_semantic_memory_init():
    """Verify that semantic memory initializes and handles missing index."""
    memory = get_semantic_memory()
    assert memory._index is not None
    # If DB has data but index is missing, it should have been rebuilt
    import sqlite3
    db_path = "memory/semantic_memory.db"
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
        conn.close()
        assert memory._index.ntotal == count

@pytest.mark.skipif(not os.path.exists("models/vosk-model"), reason="Vosk model not found")
def test_wake_detector_load():
    """Verify wake detector loads correctly."""
    from core.wake_detector import WakeWordDetector
    detector = WakeWordDetector("models/vosk-model")
    assert detector is not None

def test_config_loading():
    """Verify config loads correctly."""
    from core.config import get_config
    config = get_config()
    assert isinstance(config, dict)
