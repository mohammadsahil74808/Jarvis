import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from memory.semantic_memory import get_semantic_memory, DB_PATH, INDEX_PATH
import sqlite3
import faiss

def test_fix():
    print("Starting Semantic Memory Mapping Test...")
    
    # 1. Clean start
    if DB_PATH.exists(): DB_PATH.unlink()
    if INDEX_PATH.exists(): INDEX_PATH.unlink()
    
    sm = get_semantic_memory()
    
    # 2. Add some memories
    memories = [
        "The capital of France is Paris.",
        "The sky is blue today.",
        "Artificial intelligence is transforming the world."
    ]
    
    for m in memories:
        sm.add_memory(m)
    
    print("Added 3 memories.")
    
    # 3. Simulate deletion in DB
    # We'll delete the middle one: "The sky is blue today."
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("DELETE FROM memories WHERE text LIKE '%sky is blue%'")
    conn.commit()
    conn.close()
    
    print("Deleted 'The sky is blue today' from SQLite.")
    
    # 4. Search for the 3rd one: "Artificial intelligence"
    # Even though row 2 is gone, faiss_id for "Artificial intelligence" should still be 2.
    # The OFFSET approach would have fetched row 2 (which is now gone or shifted).
    
    results = sm.search("What is transforming the world?", k=1)
    
    if results:
        print(f"Search Result: {results[0]['text']}")
        if "Artificial intelligence" in results[0]['text']:
            print("SUCCESS: Correct memory found despite deletion!")
        else:
            print("FAILURE: Wrong memory found!")
    else:
        print("FAILURE: No results found!")

if __name__ == "__main__":
    test_fix()
