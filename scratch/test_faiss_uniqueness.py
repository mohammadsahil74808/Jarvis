import sys
from pathlib import Path
import sqlite3
import json

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from memory.semantic_memory import get_semantic_memory, add_semantic_memory, search_semantic_memory, DB_PATH, INDEX_PATH

def test_faiss_uniqueness():
    print("[START] Starting FAISS ID UNIQUENESS TEST")
    
    # Reset for clean test
    if DB_PATH.exists(): DB_PATH.unlink()
    if INDEX_PATH.exists(): INDEX_PATH.unlink()
    
    mem = get_semantic_memory()
    
    # 1. Store memories
    add_semantic_memory("User likes Python")
    add_semantic_memory("User likes AI")
    add_semantic_memory("User likes coding")
    
    # 2. Check Uniqueness in DB
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT faiss_id, text FROM memories")
    rows = cursor.fetchall()
    
    ids = [r[0] for r in rows]
    print(f"Assigned IDs: {ids}")
    
    if len(ids) == len(set(ids)):
        print("[SUCCESS] All FAISS IDs are unique.")
    else:
        print("[FAILURE] Duplicate FAISS IDs detected!")
        sys.exit(1)
        
    # 3. Simulate deletion
    delete_id = ids[1] # Delete 'User likes AI'
    print(f"[STEP] Deleting entry with faiss_id: {delete_id}")
    cursor.execute("DELETE FROM memories WHERE faiss_id = ?", (delete_id,))
    conn.commit()
    
    # 4. Add a new one to verify no collision
    add_semantic_memory("User likes space")
    
    cursor.execute("SELECT faiss_id, text FROM memories")
    new_rows = cursor.fetchall()
    new_ids = [r[0] for r in new_rows]
    print(f"IDs after deletion and new add: {new_ids}")
    
    if len(new_ids) == len(set(new_ids)):
        print("[SUCCESS] IDs remain unique after modification.")
    else:
        print("[FAILURE] ID collision detected after addition!")
        sys.exit(1)
        
    # 5. Retrieval test
    print("[STEP] Searching: 'What does the user like?'")
    results = search_semantic_memory("What does the user like?", k=5)
    print(f"Results Count: {len(results)}")
    for r in results:
        print(f" - Found: {r['text']}")
        
    texts = [r['text'] for r in results]
    if "User likes AI" not in texts:
        print("[SUCCESS] Deleted memory is NOT present.")
    else:
        print("[FAILURE] Deleted memory still returned!")
        
    if "User likes Python" in texts and "User likes coding" in texts:
        print("[SUCCESS] Remaining memories correctly retrieved.")
        
    conn.close()

if __name__ == "__main__":
    test_faiss_uniqueness()
