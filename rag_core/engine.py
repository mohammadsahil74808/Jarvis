import hashlib
from typing import List, Dict, Optional
import numpy as np

from rag_core.storage.sqlite_manager import SQLiteManager
from rag_core.storage.faiss_manager import FAISSManager
from rag_core.embeddings import Embedder
from rag_core.retrieval.hybrid import HybridRetriever
from rag_core.watchers.indexer import WatchdogMonitor
from rag_core.router.query_router import QueryRouter

# Adapters
from rag_core.adapters.code_adapter import CodeAdapter
from rag_core.adapters.memory_adapter import MemoryAdapter
from rag_core.adapters.docs_adapter import DocsAdapter
from rag_core.adapters.ocr_adapter import OCRAdapter
from rag_core.adapters.web_adapter import WebAdapter
from rag_core.adapters.project_adapter import ProjectAdapter

class RAGEngine:
    _instance = None

    def __init__(self):
        print("[RAGEngine] Initializing Core...")
        self.sqlite = SQLiteManager()
        self.faiss = FAISSManager()
        self.embedder = Embedder.get_instance()
        self.retriever = HybridRetriever()
        
        self.adapters = {
            "code": CodeAdapter(),
            "memory": MemoryAdapter(),
            "docs": DocsAdapter(),
            "ocr": OCRAdapter(),
            "web": WebAdapter(),
            "project": ProjectAdapter()
        }
        
        from queue import Queue
        import threading
        self.ingest_queue = Queue()
        self.worker_thread = threading.Thread(target=self._ingest_worker, daemon=True)
        self.worker_thread.start()
        
        self.router = QueryRouter(self)
        self.watchdog = WatchdogMonitor(self)
        
        self._rebuild_all_bm25()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _rebuild_all_bm25(self):
        for ns in self.adapters.keys():
            if not self.retriever.load_bm25(ns):
                chunks = self.sqlite.get_all_chunks_for_namespace(ns)
                self.retriever.rebuild_bm25(ns, chunks)
                self.retriever.save_bm25(ns)

    def _ingest_worker(self):
        while True:
            task = self.ingest_queue.get()
            if task is None: break
            try:
                ns, uri, kwargs = task
                self._sync_ingest(ns, uri, **kwargs)
            except Exception as e:
                print(f"[RAGEngine] Ingest Worker Error: {e}")
            finally:
                self.ingest_queue.task_done()

    def _hash_file(self, filepath: str) -> str:
        import os
        try:
            if not os.path.exists(filepath):
                return ""
            mtime = os.path.getmtime(filepath)
            size = os.path.getsize(filepath)
            return f"mtime_{mtime}_size_{size}"
        except:
            return ""

    def ingest(self, namespace: str, source_uri: str, **kwargs):
        """Asynchronous ingest push to queue."""
        self.ingest_queue.put((namespace, source_uri, kwargs))
        
    def _sync_ingest(self, namespace: str, source_uri: str, **kwargs):
        """Synchronous ingest execution."""
        adapter = self.adapters.get(namespace)
        if not adapter:
            print(f"[RAGEngine] No adapter for {namespace}")
            return

        import os
        MAX_FILE_SIZE = 50 * 1024 * 1024 # 50 MB
        if os.path.exists(source_uri) and os.path.getsize(source_uri) > MAX_FILE_SIZE:
            print(f"[RAGEngine] File {source_uri} exceeds 50MB limit.")
            return

        file_hash = self._hash_file(source_uri) if namespace not in ["memory", "web"] else ""
        
        # Check if unchanged
        existing = self.sqlite.get_document_by_uri(namespace, source_uri)
        if existing and existing["file_hash"] == file_hash and file_hash:
            return # No change
            
        if source_uri == "_rebuild_bm25_only_":
            all_chunks = self.sqlite.get_all_chunks_for_namespace(namespace)
            self.retriever.rebuild_bm25(namespace, all_chunks)
            self.retriever.save_bm25(namespace)
            return

        print(f"[RAGEngine] Ingesting {source_uri} into {namespace}...")
        
        # 1. Parse & Chunk
        chunks = adapter.ingest(source_uri, **kwargs)
        if not chunks:
            return
            
        # 2. Cleanup old vectors if doc existed
        if existing:
            old_faiss_ids = self.sqlite.delete_document_chunks(existing["id"])
            self.faiss.remove_vectors(namespace, old_faiss_ids)

        # 3. Create document
        doc_id = self.sqlite.upsert_document(namespace, source_uri, file_hash, kwargs.get("metadata", {}))
        
        # 4. Embed & Store
        texts = [c["text"] for c in chunks]
        embeddings = self.embedder.encode(texts)
        
        faiss_ids = []
        for i, chunk in enumerate(chunks):
            fid = self.sqlite.insert_chunk(doc_id, chunk["text"], chunk["chunk_index"], 0)
            faiss_ids.append(fid)
            
        self.faiss.add_vectors(namespace, embeddings, np.array(faiss_ids))
        
        # 5. Rebuild BM25
        all_chunks = self.sqlite.get_all_chunks_for_namespace(namespace)
        self.retriever.rebuild_bm25(namespace, all_chunks)
        self.retriever.save_bm25(namespace)

    def search_vectors(self, namespace: str, query: str, k: int = 5) -> List[Dict]:
        query_vec = self.embedder.encode([query])[0]
        distances, indices = self.faiss.search(namespace, query_vec, k)
        
        results = []
        for dist, idx in zip(distances, indices):
            if idx == -1: continue
            chunk_data = self.sqlite.get_chunk_by_faiss_id(int(idx))
            if chunk_data:
                chunk_data["distance"] = float(dist)
                chunk_data["faiss_id"] = int(idx)
                results.append(chunk_data)
        return results

    def query(self, text: str, namespaces: Optional[List[str]] = None, top_k: Optional[int] = None) -> str:
        """High level query returning formatted markdown context."""
        hits = self.router.query(text, namespaces, top_k)
        if not hits:
            return "No relevant context found."
            
        res = []
        for h in hits:
            ns = h.get("namespace", "unknown")
            src = h.get("source_uri", "unknown")
            text_snip = h.get("text", "")
            dist = h.get("distance")
            updated = h.get("last_updated")
            meta = []
            if dist is not None: meta.append(f"Relevance: {dist:.3f}")
            if updated: meta.append(f"Date: {updated}")
            meta_str = f" ({', '.join(meta)})" if meta else ""
            res.append(f"[{ns}] Source: {src}{meta_str}\n{text_snip}\n")
        return "\n---\n".join(res)

    def auto_ingest_file(self, filepath: str):
        import os
        # Simple heuristic
        if filepath.endswith(".py"):
            self.ingest("code", filepath)
        elif filepath.endswith(".dart"):
            self.ingest("project", filepath)
        elif filepath.endswith((".pdf", ".docx")):
            try:
                if filepath.endswith(".pdf") and os.path.getsize(filepath) > 50 * 1024 * 1024:
                    print(f"[RAGEngine] Skipping large PDF: {filepath} (>50MB)")
                    return
            except OSError:
                pass
            self.ingest("docs", filepath)

    def auto_remove_file(self, filepath: str):
        print(f"[RAGEngine] Processing deletion of {filepath}")
        for ns in ["code", "project", "docs"]:
            doc = self.sqlite.get_document_by_uri(ns, filepath)
            if doc:
                old_faiss_ids = self.sqlite.delete_document_chunks(doc["id"])
                if old_faiss_ids:
                    self.faiss.remove_vectors(ns, old_faiss_ids)
                    
                    # Also remove from documents table
                    self.sqlite._conn.cursor().execute("DELETE FROM documents WHERE id = ?", (doc["id"],))
                    self.sqlite._conn.commit()
                    
                    self.ingest_queue.put((ns, "_rebuild_bm25_only_", {}))

    def add_memory(self, text: str, metadata: Optional[dict] = None):
        self.ingest("memory", text[:50], text=text, metadata=metadata)
        
    def start_background_jobs(self):
        self.watchdog.start()
        
    def cleanup_ephemeral(self, ttl_hours: int = 24):
        old_ids = self.sqlite.delete_old_web_documents(ttl_hours)
        if old_ids:
            self.faiss.remove_vectors("web", old_ids)
            self._rebuild_all_bm25()
