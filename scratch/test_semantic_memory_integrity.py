import sys
import os
import sqlite3
import json
from pathlib import Path

# Add the project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from memory.semantic_memory import get_semantic_memory, add_semantic_memory, search_semantic_memory
    print("[OK] SemanticMemory modules imported successfully.")
except ImportError as e:
    print(f"[ERROR] ImportError: {e}")
    sys.exit(1)

def test_semantic_integrity():
    print("[START] Starting MEMORY VALIDATION TEST")
    
    memory = get_semantic_memory()
    conn = memory._db_conn
    cursor = conn.cursor()
    
    # Debug: List existing memories
    cursor.execute("SELECT faiss_id, text FROM memories")
    print("\n--- EXISTING MEMORIES BEFORE TEST ---")
    for row in cursor.fetchall():
        safe_row_text = str(row[1]).encode('ascii', 'ignore').decode('ascii')
        print(f"ID: {row[0]} | Text: {safe_row_text[:50]}...")
    
    # 1. Store: "User likes Python and AI"
    print("\n[STEP 1] Storing: 'User likes Python and AI'")
    add_semantic_memory("User likes Python and AI", {"category": "likes"})
    
    # 2. Store: "User prefers dark mode"
    print("[STEP 2] Storing: 'User prefers dark mode'")
    add_semantic_memory("User prefers dark mode", {"category": "preferences"})
    
    # 3. Simulate deletion
    print("[STEP 3] Deleting 'User prefers dark mode' from SQLite")
    cursor.execute("SELECT faiss_id FROM memories WHERE text = ?", ("User prefers dark mode",))
    row = cursor.fetchone()
    if row:
        deleted_faiss_id = row[0]
        cursor.execute("DELETE FROM memories WHERE faiss_id = ?", (deleted_faiss_id,))
        conn.commit()
        print(f"Deleted faiss_id: {deleted_faiss_id}")

    # 4. Perform search
    print("[STEP 4] Searching: 'What does the user like?'")
    results = search_semantic_memory("What does the user like?", k=10)
    
    # 5. Verify
    print("\n--- TEST RESULTS ---")
    print(f"Results Count: {len(results)}")
    
    found_correct = False
    found_wrong = False
    
    for r in results:
        # Safe print
        safe_text = r['text'].encode('ascii', 'ignore').decode('ascii')
        print(f"- Found: {safe_text}")
        if "Python and AI" in r['text']:
            found_correct = True
        if "dark mode" in r['text']:
            found_wrong = True
            
    if found_correct and not found_wrong:
        print("[SUCCESS] Semantic integrity verified.")
    elif found_wrong:
        print("[FAILURE] Deleted memory still present in search results.")
    elif not found_correct:
        print("[FAILURE] Correct memory NOT found in results.")
    
    # Final check: FAISS vs SQLite count
    cursor.execute("SELECT COUNT(*) FROM memories")
    db_count = cursor.fetchone()[0]
    faiss_count = memory._index.ntotal
    print(f"\nFinal State: SQLite={db_count} entries, FAISS={faiss_count} vectors.")

if __name__ == "__main__":
    test_semantic_integrity()
