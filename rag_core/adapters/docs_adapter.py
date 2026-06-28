import os
from typing import List, Dict, Any
from rag_core.adapters.base import BaseAdapter
from rag_core.config import get_namespace_config
import fitz  # PyMuPDF
from docx import Document

class DocsAdapter(BaseAdapter):
    @property
    def namespace(self) -> str:
        return "docs"
        
    def __init__(self):
        self.config = get_namespace_config(self.namespace)

    def ingest(self, source_uri: str, **kwargs) -> List[Dict[str, Any]]:
        if not os.path.exists(source_uri):
            return []
            
        ext = os.path.splitext(source_uri)[1].lower()
        chunks = []
        
        try:
            if ext == ".pdf":
                doc = fitz.open(source_uri)
                for page_num, page in enumerate(doc):
                    try:
                        text = page.get_text("text").strip()
                        if text:
                            # Page level chunking, or split further if huge
                            raw_chunks = self.chunk_text(text, self.config["chunk_size"], self.config["chunk_overlap"])
                            for i, rc in enumerate(raw_chunks):
                                chunks.append({
                                    "text": rc,
                                    "chunk_index": len(chunks),
                                    "metadata": {"page": page_num + 1}
                                })
                    except Exception as pe:
                        print(f"[DocsAdapter] Error on page {page_num} of {source_uri}: {pe}")
            elif ext in [".docx", ".doc"]:
                doc = Document(source_uri)
                full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
                raw_chunks = self.chunk_text(full_text, self.config["chunk_size"], self.config["chunk_overlap"])
                for i, rc in enumerate(raw_chunks):
                    chunks.append({
                        "text": rc,
                        "chunk_index": i,
                        "metadata": {}
                    })
        except Exception as e:
            print(f"[DocsAdapter] Error reading {source_uri}: {e}")

        return chunks
