import sys
import os
import sqlite3
import numpy as np
import faiss
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from memory.semantic_memory import get_semantic_memory, add_semantic_memory, search_semantic_memory

def test_faiss_sync_issue():
    print("Testing FAISS Sync Issue...")
    memory = get_semantic_memory()
    
    # 1. Clear existing for clean test
    if os.path.exists("memory/semantic_index.faiss"):
        os.remove("memory/semantic_index.faiss")
    if os.path.exists("memory/semantic_memory.db"):
        os.remove("memory/semantic_memory.db")
    
    # Re-init
    memory._db_conn = None
    memory._index = None
    memory._init_db()
    memory._init_faiss()
    
    # 2. Add 5 memories (not enough to trigger auto-save which is at 10)
    for i in range(5):
        add_semantic_memory(f"This is test memory number {i}")
    
    print(f"Memories in DB: {memory._db_conn.execute('SELECT COUNT(*) FROM memories').fetchone()[0]}")
    print(f"Memories in Index: {memory._index.ntotal}")
    
    # 3. Simulate crash by NOT calling _save_index and restarting
    # The index on disk doesn't exist yet (ntotal=0 if we read it)
    # But wait, _init_faiss rebuilds from DB if index is MISSING.
    
    # Let's force a save after 11 to have an index on disk
    for i in range(6):
        add_semantic_memory(f"Batch 2 memory {i}")
    
    print(f"Memories in Index after 11 adds: {memory._index.ntotal}")
    # Now index is saved to disk (ntotal=11)
    
    # 4. Add 5 more (ntotal in memory = 16, ntotal on disk = 11)
    for i in range(5):
        add_semantic_memory(f"Batch 3 memory {i}")
    
    print(f"Final Memories in DB: {memory._db_conn.execute('SELECT COUNT(*) FROM memories').fetchone()[0]}")
    print(f"Final Memories in Index (RAM): {memory._index.ntotal}")
    
    # 5. Simulate restart (re-read from disk)
    memory._init_faiss()
    print(f"Memories in Index (After Reload): {memory._index.ntotal}")
    
    if memory._index.ntotal < 16:
        print("FAIL: FAISS index is out of sync with Database after reload!")
    else:
        print("PASS: FAISS index synced correctly.")

if __name__ == "__main__":
    test_faiss_sync_issue()
