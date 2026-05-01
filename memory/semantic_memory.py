import os
import sqlite3
import json
import numpy as np
import faiss
from datetime import datetime
from pathlib import Path
from threading import RLock
from sentence_transformers import SentenceTransformer

from core.config import BASE_DIR

DB_PATH = BASE_DIR / "memory" / "semantic_memory.db"
INDEX_PATH = BASE_DIR / "memory" / "semantic_index.faiss"
MODEL_NAME = "all-MiniLM-L6-v2"

class SemanticMemory:
    def __init__(self):
        self._lock = RLock()
        self._model = None
        self._index = None
        self._db_conn = None
        self._dimension = 384 # Dimension for all-MiniLM-L6-v2
        self._unflushed_writes = 0
        
        # Ensure directory exists
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._init_faiss()

    def _get_model(self):
        if self._model is None:
            print(f"[SemanticMemory] Loading {MODEL_NAME}...")
            self._model = SentenceTransformer(MODEL_NAME)
        return self._model

    def _init_db(self):
        self._db_conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        cursor = self._db_conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                metadata TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                faiss_id INTEGER UNIQUE
            )
        """)
        
        # Migration check for faiss_id column
        cursor.execute("PRAGMA table_info(memories)")
        cols = [c[1] for c in cursor.fetchall()]
        if "faiss_id" not in cols:
            print("[SemanticMemory] Migrating database: adding faiss_id column")
            cursor.execute("ALTER TABLE memories ADD COLUMN faiss_id INTEGER")
            # For existing rows, assign sequential IDs matching current index order
            cursor.execute("SELECT id FROM memories ORDER BY id ASC")
            for i, (rid,) in enumerate(cursor.fetchall()):
                cursor.execute("UPDATE memories SET faiss_id = ? WHERE id = ?", (i, rid))
        
        self._db_conn.commit()

    def _init_faiss(self):
        if INDEX_PATH.exists():
            try:
                self._index = faiss.read_index(str(INDEX_PATH))
                print(f"[SemanticMemory] FAISS index loaded ({self._index.ntotal} entries)")
                return
            except Exception as e:
                print(f"[SemanticMemory] FAISS load error: {e}, recreating...")
        
        self._index = faiss.IndexIDMap(faiss.IndexFlatL2(self._dimension))
        # Rebuild index from DB if index was missing/corrupt but DB has data
        self._rebuild_from_db()

    def _rebuild_from_db(self):
        cursor = self._db_conn.cursor()
        cursor.execute("SELECT id, text FROM memories ORDER BY id ASC")
        rows = cursor.fetchall()
        if not rows:
            return
        
        print(f"[SemanticMemory] Rebuilding index from {len(rows)} database entries...")
        
        # Use existing faiss_id if available, otherwise generate new ones
        texts = []
        ids = []
        for rid, text in rows:
            cursor.execute("SELECT faiss_id FROM memories WHERE id = ?", (rid,))
            fid = cursor.fetchone()[0]
            if fid is None:
                cursor.execute("SELECT IFNULL(MAX(faiss_id), -1) FROM memories")
                fid = cursor.fetchone()[0] + 1
                cursor.execute("UPDATE memories SET faiss_id = ? WHERE id = ?", (fid, rid))
            
            texts.append(text)
            ids.append(fid)
            
        embeddings = self._get_model().encode(texts)
        self._index.add_with_ids(
            np.array(embeddings).astype('float32'),
            np.array(ids).astype('int64')
        )
        self._db_conn.commit()
        
        self._save_index()

    def _save_index(self):
        faiss.write_index(self._index, str(INDEX_PATH))

    def add_memory(self, text: str, metadata: dict = None):
        if not text.strip():
            return
        
        with self._lock:
            # 1. Calculate new persistent faiss_id
            cursor = self._db_conn.cursor()
            cursor.execute("SELECT IFNULL(MAX(faiss_id), -1) FROM memories")
            new_faiss_id = cursor.fetchone()[0] + 1
            
            # 2. Store in SQLite
            cursor.execute(
                "INSERT INTO memories (text, metadata, faiss_id) VALUES (?, ?, ?)",
                (text, json.dumps(metadata or {}), new_faiss_id)
            )
            self._db_conn.commit()
            
            # 3. Add to FAISS with ID
            embedding = self._get_model().encode([text])[0]
            self._index.add_with_ids(
                np.array([embedding]).astype('float32'),
                np.array([new_faiss_id]).astype('int64')
            )
            
            self._unflushed_writes += 1
            if self._unflushed_writes >= 10:
                self._save_index()
                self._unflushed_writes = 0
            print(f"[SemanticMemory] Added memory (ID {new_faiss_id}): {text[:50]}...")

    def search(self, query: str, k: int = 5):
        if not query.strip() or self._index.ntotal == 0:
            return []
        
        with self._lock:
            query_vector = self._get_model().encode([query])[0]
            distances, indices = self._index.search(np.array([query_vector]).astype('float32'), k)
            
            # FAISS indices match SQLite row IDs (if only additions, no deletions)
            # Actually, id in SQLite starts at 1, indices start at 0.
            # And indices follow the order of addition.
            results = []
            for idx, dist in zip(indices[0], distances[0]):
                if idx == -1: continue
                
                # Fetch from DB by faiss_id instead of OFFSET
                cursor = self._db_conn.cursor()
                cursor.execute("SELECT text, metadata, timestamp FROM memories WHERE faiss_id = ?", (int(idx),))
                row = cursor.fetchone()
                if row:
                    results.append({
                        "text": row[0],
                        "metadata": json.loads(row[1]),
                        "timestamp": row[2],
                        "distance": float(dist)
                    })
            return results

# Singleton
_instance = None

def get_semantic_memory():
    global _instance
    if _instance is None:
        _instance = SemanticMemory()
    return _instance

def add_semantic_memory(text, metadata=None):
    get_semantic_memory().add_memory(text, metadata)

def search_semantic_memory(query, k=5):
    return get_semantic_memory().search(query, k)
