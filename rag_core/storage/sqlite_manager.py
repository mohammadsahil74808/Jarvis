import sqlite3
import json
from threading import RLock
from typing import Optional

from rag_core.config import get_db_path

class SQLiteManager:
    def __init__(self):
        self.db_path = get_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            cursor = self._conn.cursor()
            
            # Namespaces
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS namespaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Documents
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    namespace_id INTEGER NOT NULL,
                    source_uri TEXT NOT NULL,
                    file_hash TEXT,
                    metadata TEXT,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(namespace_id) REFERENCES namespaces(id),
                    UNIQUE(namespace_id, source_uri)
                )
            """)

            # Chunks
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    token_count INTEGER,
                    faiss_id INTEGER UNIQUE,
                    FOREIGN KEY(doc_id) REFERENCES documents(id)
                )
            """)

            # Missing Indexes for Performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_faiss ON chunks(faiss_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_ns ON documents(namespace_id)")
            
            self._conn.commit()

    def ensure_namespace(self, name: str, description: str = "") -> int:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT id FROM namespaces WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return row[0]
            cursor.execute("INSERT INTO namespaces (name, description) VALUES (?, ?)", (name, description))
            self._conn.commit()
            return cursor.lastrowid

    def upsert_document(self, namespace: str, source_uri: str, file_hash: str = "", metadata: dict = None) -> int:
        ns_id = self.ensure_namespace(namespace)
        meta_str = json.dumps(metadata or {})
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute(
                "SELECT id FROM documents WHERE namespace_id = ? AND source_uri = ?", 
                (ns_id, source_uri)
            )
            row = cursor.fetchone()
            if row:
                doc_id = row[0]
                cursor.execute("""
                    UPDATE documents SET file_hash = ?, metadata = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (file_hash, meta_str, doc_id))
            else:
                cursor.execute("""
                    INSERT INTO documents (namespace_id, source_uri, file_hash, metadata)
                    VALUES (?, ?, ?, ?)
                """, (ns_id, source_uri, file_hash, meta_str))
                doc_id = cursor.lastrowid
            self._conn.commit()
            return doc_id

    def get_document_by_uri(self, namespace: str, source_uri: str) -> Optional[dict]:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT d.id, d.file_hash, d.metadata, d.last_updated
                FROM documents d
                JOIN namespaces n ON d.namespace_id = n.id
                WHERE n.name = ? AND d.source_uri = ?
            """, (namespace, source_uri))
            row = cursor.fetchone()
            if row:
                return {
                    "id": row[0],
                    "file_hash": row[1],
                    "metadata": json.loads(row[2]) if row[2] else {},
                    "last_updated": row[3]
                }
            return None

    def delete_document_chunks(self, doc_id: int):
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT faiss_id FROM chunks WHERE doc_id = ?", (doc_id,))
            faiss_ids = [r[0] for r in cursor.fetchall() if r[0] is not None]
            
            cursor.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
            self._conn.commit()
            return faiss_ids

    def insert_chunk(self, doc_id: int, text: str, chunk_index: int, token_count: int = 0) -> int:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("SELECT IFNULL(MAX(faiss_id), -1) FROM chunks")
            faiss_id = cursor.fetchone()[0] + 1
            
            cursor.execute("""
                INSERT INTO chunks (doc_id, text, chunk_index, token_count, faiss_id)
                VALUES (?, ?, ?, ?, ?)
            """, (doc_id, text, chunk_index, token_count, faiss_id))
            self._conn.commit()
            return faiss_id

    def get_chunk_by_faiss_id(self, faiss_id: int) -> Optional[dict]:
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT c.text, c.chunk_index, d.source_uri, d.metadata, n.name
                FROM chunks c
                JOIN documents d ON c.doc_id = d.id
                JOIN namespaces n ON d.namespace_id = n.id
                WHERE c.faiss_id = ?
            """, (faiss_id,))
            row = cursor.fetchone()
            if row:
                return {
                    "text": row[0],
                    "chunk_index": row[1],
                    "source_uri": row[2],
                    "metadata": json.loads(row[3]) if row[3] else {},
                    "namespace": row[4]
                }
            return None
            
    def get_all_chunks_for_namespace(self, namespace: str):
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT c.faiss_id, c.text, d.source_uri, d.metadata
                FROM chunks c
                JOIN documents d ON c.doc_id = d.id
                JOIN namespaces n ON d.namespace_id = n.id
                WHERE n.name = ?
            """, (namespace,))
            return [{"faiss_id": r[0], "text": r[1], "source_uri": r[2], "metadata": json.loads(r[3])} for r in cursor.fetchall()]

    def delete_old_web_documents(self, ttl_hours: int):
        # Implementation for TTL expiry
        with self._lock:
            cursor = self._conn.cursor()
            cursor.execute("""
                SELECT d.id FROM documents d
                JOIN namespaces n ON d.namespace_id = n.id
                WHERE n.name = 'web' AND d.last_updated <= datetime('now', ?)
            """, (f'-{ttl_hours} hours',))
            doc_ids = [r[0] for r in cursor.fetchall()]
            
            faiss_ids_to_remove = []
            for doc_id in doc_ids:
                faiss_ids_to_remove.extend(self.delete_document_chunks(doc_id))
                cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            self._conn.commit()
            return faiss_ids_to_remove
