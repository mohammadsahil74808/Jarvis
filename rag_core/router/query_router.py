from typing import List, Dict
from rag_core.retrieval.hybrid import reciprocal_rank_fusion
from rag_core.config import get_rag_setting

class QueryRouter:
    def __init__(self, engine):
        self.engine = engine
        self.top_k = get_rag_setting("retrieval.top_k", 5)

    def classify_intent(self, query: str) -> List[str]:
        """
        A simple heuristic classifier to pick namespaces.
        In a full version, this could call an LLM.
        """
        query_lower = query.lower()
        namespaces = set()
        
        if any(w in query_lower for w in ["code", "function", "bug", "architecture", "debug"]):
            namespaces.add("code")
            namespaces.add("project")
            
        if any(w in query_lower for w in ["remember", "i said", "we discussed", "last time", "memory"]):
            namespaces.add("memory")
            
        if any(w in query_lower for w in ["notes", "pdf", "document", "exam"]):
            namespaces.add("docs")
            
        if any(w in query_lower for w in ["screenshot", "image", "screen"]):
            namespaces.add("ocr")
            
        if any(w in query_lower for w in ["search", "web", "online"]):
            namespaces.add("web")
            
        # Default to memory and docs if nothing specific
        if not namespaces:
            namespaces.update(["memory", "docs", "code"])
            
        return list(namespaces)

    def query(self, text: str, namespaces: List[str] = None, top_k: int = None) -> List[Dict]:
        if not namespaces:
            namespaces = self.classify_intent(text)
            
        if top_k is None:
            top_k = self.top_k
            
        all_results = []
        
        for ns in namespaces:
            try:
                # 1. Vector Search
                vector_hits = self.engine.search_vectors(ns, text, k=top_k * 2)
                
                # 2. BM25 Search
                bm25_scores = self.engine.retriever.get_bm25_scores(ns, text)
                
                # 3. RRF Fusion
                if vector_hits:
                    fused = reciprocal_rank_fusion(vector_hits, bm25_scores)
                    # Take top_k
                    all_results.extend(fused[:top_k])
            except Exception as e:
                print(f"[QueryRouter] Error searching {ns}: {e}")
                
        # Sort combined results across namespaces by rrf_score
        all_results.sort(key=lambda x: x.get("rrf_score", 0), reverse=True)
        return all_results[:top_k]
