import numpy as np
from rank_bm25 import BM25Okapi
from typing import List, Dict

import os
import pickle

class HybridRetriever:
    def __init__(self, data_dir=".jarvis/bm25"):
        self._bm25_models = {}
        self._corpus_map = {} # namespace -> dict mapping chunk id -> tokenized document
        self.data_dir = data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.dirty_namespaces = set()

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
            
        self.dirty_namespaces.add(namespace)

    def save_bm25(self, namespace: str = None):
        """Saves BM25 index to disk. If namespace is None, saves all dirty namespaces."""
        namespaces_to_save = [namespace] if namespace else list(self.dirty_namespaces)
        for ns in namespaces_to_save:
            model = self._bm25_models.get(ns)
            corpus_map = self._corpus_map.get(ns)
            path = os.path.join(self.data_dir, f"{ns}.pkl")
            if model and corpus_map:
                try:
                    with open(path, "wb") as f:
                        pickle.dump({"model": model, "corpus_map": corpus_map}, f)
                    if ns in self.dirty_namespaces:
                        self.dirty_namespaces.remove(ns)
                except Exception as e:
                    print(f"[HybridRetriever] Error saving {ns} BM25: {e}")
            else:
                if os.path.exists(path):
                    os.remove(path)

    def load_bm25(self, namespace: str) -> bool:
        """Loads BM25 index from disk. Returns True if successful."""
        path = os.path.join(self.data_dir, f"{namespace}.pkl")
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    data = pickle.load(f)
                    self._bm25_models[namespace] = data.get("model")
                    self._corpus_map[namespace] = data.get("corpus_map")
                    return True
            except Exception as e:
                print(f"[HybridRetriever] Error loading {namespace} BM25: {e}")
        return False

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
