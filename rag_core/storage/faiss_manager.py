import faiss
import numpy as np
from pathlib import Path
from threading import RLock
from rag_core.config import get_faiss_dir, get_embedding_dim

class FAISSManager:
    def __init__(self):
        self.faiss_dir = get_faiss_dir()
        self.faiss_dir.mkdir(parents=True, exist_ok=True)
        self.dim = get_embedding_dim()
        self._indexes = {}
        self._lock = RLock()

    def _get_index_path(self, namespace: str) -> Path:
        return self.faiss_dir / f"{namespace}.faiss"

    def get_index(self, namespace: str) -> faiss.IndexIDMap:
        with self._lock:
            if namespace in self._indexes:
                return self._indexes[namespace]
            
            idx_path = self._get_index_path(namespace)
            if idx_path.exists():
                try:
                    index = faiss.read_index(str(idx_path))
                    self._indexes[namespace] = index
                    return index
                except Exception as e:
                    print(f"[FAISSManager] Failed to load index {namespace}: {e}. Creating new.")
            
            # Create new index
            # FlatL2 is robust for most small/medium usages
            base_index = faiss.IndexFlatL2(self.dim)
            index = faiss.IndexIDMap(base_index)
            self._indexes[namespace] = index
            return index

    def add_vectors(self, namespace: str, vectors: np.ndarray, ids: np.ndarray):
        if len(vectors) == 0:
            return
        with self._lock:
            index = self.get_index(namespace)
            vectors = np.array(vectors).astype('float32')
            ids = np.array(ids).astype('int64')
            index.add_with_ids(vectors, ids)
            self.save_index(namespace)

    def remove_vectors(self, namespace: str, ids: list):
        if not ids:
            return
        with self._lock:
            index = self.get_index(namespace)
            id_selector = faiss.IDSelectorBatch(ids)
            index.remove_ids(id_selector)
            self.save_index(namespace)

    def search(self, namespace: str, query_vector: np.ndarray, k: int = 5):
        with self._lock:
            index = self.get_index(namespace)
            if index.ntotal == 0:
                return [], []
            query_vector = np.array([query_vector]).astype('float32')
            distances, indices = index.search(query_vector, k)
            return distances[0], indices[0]

    def save_index(self, namespace: str):
        with self._lock:
            if namespace in self._indexes:
                idx_path = self._get_index_path(namespace)
                faiss.write_index(self._indexes[namespace], str(idx_path))

    def get_ntotal(self, namespace: str) -> int:
        with self._lock:
            return self.get_index(namespace).ntotal
