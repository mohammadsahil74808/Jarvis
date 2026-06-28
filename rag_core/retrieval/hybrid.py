import numpy as np
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any

class HybridRetriever:
    def __init__(self):
        self._bm25_models = {}
        self._corpus_map = {} # namespace -> dict mapping chunk id -> tokenized document

    def rebuild_bm25(self, namespace: str, chunks: List[dict]):
        """Rebuilds the BM25 index from scratch for a given namespace."""
        if not chunks:
            self._bm25_models[namespace] = None
            self._corpus_map[namespace] = {}
            return

        tokenized_corpus = []
        doc_ids = []
        for chunk in chunks:
            text = chunk.get("text", "")
            fid = chunk.get("faiss_id")
            if fid is not None:
                tokenized = text.lower().split()
                tokenized_corpus.append(tokenized)
                doc_ids.append(fid)

        if tokenized_corpus:
            self._bm25_models[namespace] = BM25Okapi(tokenized_corpus)
            self._corpus_map[namespace] = {fid: idx for idx, fid in enumerate(doc_ids)}
        else:
            self._bm25_models[namespace] = None
            self._corpus_map[namespace] = {}

    def get_bm25_scores(self, namespace: str, query: str) -> Dict[int, float]:
        model = self._bm25_models.get(namespace)
        corpus_map = self._corpus_map.get(namespace, {})
        
        if not model or not corpus_map:
            return {}

        tokenized_query = query.lower().split()
        scores = model.get_scores(tokenized_query)
        
        result = {}
        for fid, idx in corpus_map.items():
            result[fid] = float(scores[idx])
        return result

def reciprocal_rank_fusion(vector_results: List[Dict], bm25_scores: Dict[int, float], k: int = 60) -> List[Dict]:
    """
    vector_results: list of dicts with {"faiss_id": id, "distance": dist, ...}
        (lower distance is better for L2)
    bm25_scores: dict of faiss_id -> score
        (higher score is better)
    """
    # Rank vectors (sort by distance asc)
    vector_results.sort(key=lambda x: x["distance"])
    
    # Rank BM25 (sort by score desc)
    bm25_ranked = sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)
    
    rrf_scores = {}
    
    for rank, item in enumerate(vector_results, 1):
        fid = item["faiss_id"]
        rrf_scores[fid] = rrf_scores.get(fid, 0.0) + 1.0 / (k + rank)
        
    for rank, (fid, _) in enumerate(bm25_ranked, 1):
        rrf_scores[fid] = rrf_scores.get(fid, 0.0) + 1.0 / (k + rank)
        
    # Apply RRF score back to vector results and sort
    for item in vector_results:
        fid = item["faiss_id"]
        item["rrf_score"] = rrf_scores.get(fid, 0.0)
        
    # Items that were only found by BM25? For simplicity, we only rerank items 
    # retrieved by the vector search (which we assume is broad enough).
    # A true hybrid might fetch top N from both and merge.
    
    vector_results.sort(key=lambda x: x["rrf_score"], reverse=True)
    return vector_results
