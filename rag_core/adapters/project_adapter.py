import os
import re
from typing import List, Dict, Any
from rag_core.adapters.base import BaseAdapter
from rag_core.config import get_namespace_config

class ProjectAdapter(BaseAdapter):
    @property
    def namespace(self) -> str:
        return "project"
        
    def __init__(self):
        self.config = get_namespace_config(self.namespace)

    def ingest(self, source_uri: str, **kwargs) -> List[Dict[str, Any]]:
        if not os.path.exists(source_uri):
            return []
            
        ext = os.path.splitext(source_uri)[1].lower()
        chunks = []
        
        try:
            with open(source_uri, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
                
            if ext == ".dart":
                # Basic regex chunking for Dart (classes and functions)
                pattern = r"((?:class|Widget)\s+\w+.*?\{.*?\n\})|((?:[\w<>]+\s+)?\w+\(.*?\{.*?\n\})"
                matches = re.finditer(pattern, code, re.DOTALL)
                
                chunk_idx = 0
                for match in matches:
                    text = match.group(0)
                    if len(text.strip()) > 10:
                        chunks.append({
                            "text": text,
                            "chunk_index": chunk_idx,
                            "metadata": {"type": "dart_element"}
                        })
                        chunk_idx += 1
                        
                if not chunks:
                    raw = self.chunk_text(code, self.config["chunk_size"], self.config["chunk_overlap"])
                    chunks = [{"text": c, "chunk_index": i, "metadata": {}} for i, c in enumerate(raw)]
            else:
                # Generic fallback
                raw = self.chunk_text(code, self.config["chunk_size"], self.config["chunk_overlap"])
                chunks = [{"text": c, "chunk_index": i, "metadata": {}} for i, c in enumerate(raw)]
                
        except Exception as e:
            print(f"[ProjectAdapter] Error reading {source_uri}: {e}")

        return chunks
