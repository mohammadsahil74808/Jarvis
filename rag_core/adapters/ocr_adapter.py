import os
from typing import List, Dict, Any
from rag_core.adapters.base import BaseAdapter
from rag_core.config import get_namespace_config
import pytesseract
from PIL import Image

class OCRAdapter(BaseAdapter):
    @property
    def namespace(self) -> str:
        return "ocr"
        
    def __init__(self):
        self.config = get_namespace_config(self.namespace)

    def ingest(self, source_uri: str, **kwargs) -> List[Dict[str, Any]]:
        """source_uri is the path to an image."""
        if not os.path.exists(source_uri):
            return []
            
        try:
            image = Image.open(source_uri)
            text = pytesseract.image_to_string(image).strip()
            
            if not text:
                return []
                
            raw_chunks = self.chunk_text(text, self.config["chunk_size"], self.config["chunk_overlap"])
            
            # Simple heuristic for error screenshot
            is_error = "error" in text.lower() or "exception" in text.lower()
            
            return [
                {
                    "text": rc,
                    "chunk_index": i,
                    "metadata": {"is_error": is_error}
                }
                for i, rc in enumerate(raw_chunks)
            ]
        except Exception as e:
            print(f"[OCRAdapter] Error reading {source_uri}: {e}")
            return []
