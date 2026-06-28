from typing import List, Dict, Any
from rag_core.adapters.base import BaseAdapter
from rag_core.config import get_namespace_config

class WebAdapter(BaseAdapter):
    @property
    def namespace(self) -> str:
        return "web"
        
    def __init__(self):
        self.config = get_namespace_config(self.namespace)

    def ingest(self, source_uri: str, **kwargs) -> List[Dict[str, Any]]:
        """
        source_uri is the URL. We expect kwargs['text'] to hold the fetched content.
        This allows reuse of existing newspaper3k logic in JARVIS.
        """
        text = kwargs.get("text", "")
        if not text:
            return []
            
        raw_chunks = self.chunk_text(text, self.config["chunk_size"], self.config["chunk_overlap"])
        
        return [
            {"text": rc, "chunk_index": i, "metadata": {"url": source_uri}}
            for i, rc in enumerate(raw_chunks)
        ]
