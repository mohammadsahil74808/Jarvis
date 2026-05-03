from memory.semantic_memory import get_semantic_memory
import os

print("Initializing SemanticMemory...")
memory = get_semantic_memory()
print(f"Index total: {memory._index.ntotal}")
print(f"Index path: {os.path.abspath('memory/semantic_index.faiss')}")
print(f"Exists: {os.path.exists('memory/semantic_index.faiss')}")
