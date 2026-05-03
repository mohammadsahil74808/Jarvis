import faiss
import sqlite3
import os

index_path = "memory/semantic_index.faiss"
db_path = "memory/semantic_memory.db"

if os.path.exists(index_path):
    index = faiss.read_index(index_path)
    print(f"FAISS Index Total: {index.ntotal}")
else:
    print("Index not found.")

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    print(f"Database Total: {count}")
    conn.close()
