import sqlite3
from pathlib import Path
import os

db_path = "memory/semantic_memory.db"
if not os.path.exists(db_path):
    print("DB not found.")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT faiss_id, COUNT(*) FROM memories GROUP BY faiss_id HAVING COUNT(*) > 1")
    dupes = cursor.fetchall()
    if dupes:
        print(f"CRITICAL: Found {len(dupes)} duplicate FAISS IDs!")
        for fid, count in dupes:
            print(f"  ID {fid}: {count} occurrences")
    else:
        print("PASS: No duplicate FAISS IDs found in database.")
    
    cursor.execute("SELECT COUNT(*) FROM memories")
    db_count = cursor.fetchone()[0]
    print(f"Total memories in DB: {db_count}")
    conn.close()
