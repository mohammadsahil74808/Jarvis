import unittest
from rag_core.retrieval.hybrid import HybridRetriever
from rag_core.storage.faiss_manager import FAISSManager
from rag_core.embeddings import Embedder
import os

class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.embedder = Embedder("BAAI/bge-small-en-v1.5")
        self.faiss = FAISSManager(self.embedder)
        self.retriever = HybridRetriever(self.faiss, self.embedder)
        
        # Setup dummy index
        self.ns = "test_ns"
        self.faiss.get_or_create_index(self.ns)
        
        self.chunks = [
            {"text": "The quick brown fox jumps over the lazy dog", "id": 1, "faiss_id": 1, "metadata": {}},
            {"text": "A fast brown fox leaps over a sleepy dog", "id": 2, "faiss_id": 2, "metadata": {}},
            {"text": "Python is a programming language", "id": 3, "faiss_id": 3, "metadata": {}}
        ]
        
        # Add to FAISS
        self.faiss.add_vectors(self.ns, [c["text"] for c in self.chunks], [c["faiss_id"] for c in self.chunks])
        
        # Build BM25
        self.retriever.rebuild_bm25(self.ns, self.chunks)

    def tearDown(self):
        if os.path.exists("rag_core/storage/faiss_indexes"):
            idx_file = os.path.join("rag_core/storage/faiss_indexes", f"{self.ns}.faiss")
            if os.path.exists(idx_file): os.remove(idx_file)

    def test_hybrid_search(self):
        # Searching for "fox" should highly rank the first two chunks
        results = self.retriever.search(self.ns, "brown fox", self.chunks, top_k=2)
        
        self.assertEqual(len(results), 2)
        texts = [r["text"] for r in results]
        self.assertTrue(any("quick brown fox" in t for t in texts))
        self.assertTrue(any("fast brown fox" in t for t in texts))
        self.assertFalse(any("Python" in t for t in texts))

if __name__ == '__main__':
    unittest.main()
