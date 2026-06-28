import json
from rag_core import get_rag_engine

class SemanticMemory:
    def __init__(self):
        self.engine = get_rag_engine()

    def add_memory(self, text: str, metadata: dict = None):
        if not text.strip():
            return
        self.engine.add_memory(text, metadata)

    def search(self, query: str, k: int = 5):
        if not query.strip():
            return []
        # Return format expected by rest of Jarvis:
        # [{"text": ..., "metadata": ..., "distance": ...}]
        results = self.engine.search_vectors("memory", query, k=k)
        # Format mapping
        formatted = []
        for r in results:
            formatted.append({
                "text": r.get("text", ""),
                "metadata": r.get("metadata", {}),
                "timestamp": r.get("last_updated", ""),
                "distance": r.get("distance", 0.0)
            })
        return formatted

# Singleton
_instance = None

def get_semantic_memory():
    global _instance
    if _instance is None:
        _instance = SemanticMemory()
    return _instance

def add_semantic_memory(text, metadata=None):
    try:
        get_semantic_memory().add_memory(text, metadata)
    except Exception as e:
        print(f"[SemanticMemoryProxy] Add error: {e}")

def search_semantic_memory(query, k=5):
    try:
        return get_semantic_memory().search(query, k)
    except Exception as e:
        print(f"[SemanticMemoryProxy] Search error: {e}")
        return []

