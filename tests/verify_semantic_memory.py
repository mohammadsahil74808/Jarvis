import sys
import os
from pathlib import Path
import time

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from memory.semantic_memory import add_semantic_memory, search_semantic_memory

def test_semantic_memory():
    print("--- Testing Semantic Memory ---")
    
    # 1. Add some memories
    print("1. Adding test memories...")
    memories = [
        "User: I love playing acoustic guitar in the evenings.",
        "Jarvis: That sounds wonderful, Sahil! Musical hobbies are very relaxing.",
        "User: My project is called JARVIS-XXV and it uses vector memory.",
        "Jarvis: I'm honored to be part of the Mark XXV project, sir."
    ]
    
    for m in memories:
        add_semantic_memory(m)
    
    # Wait a bit for indexing (though it's synchronous in our basic impl)
    time.sleep(1)
    
    # 2. Search by meaning
    print("\n2. Searching for 'musical instruments'...")
    results = search_semantic_memory("musical instruments", k=2)
    for r in results:
        print(f"Match: {r['text']} (Dist: {r['distance']:.4f})")
    
    print("\n3. Searching for 'coding projects'...")
    results = search_semantic_memory("coding projects", k=2)
    for r in results:
        print(f"Match: {r['text']} (Dist: {r['distance']:.4f})")
        
    print("\n--- Semantic Memory Test Complete ---")

if __name__ == "__main__":
    test_semantic_memory()
