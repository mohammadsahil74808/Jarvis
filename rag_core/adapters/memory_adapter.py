from typing import List, Dict, Any
from rag_core.adapters.base import BaseAdapter
from rag_core.config import get_namespace_config

class MemoryAdapter(BaseAdapter):
    @property
    def namespace(self) -> str:
        return "memory"
        
    def __init__(self):
        self.config = get_namespace_config(self.namespace)

    def ingest(self, source_uri: str, **kwargs) -> List[Dict[str, Any]]:
        """
        For memory, source_uri is just a string identifier or literal text.
        We expect kwargs to provide 'text' and 'metadata'.
        """
        text = kwargs.get("text", source_uri)
        metadata = kwargs.get("metadata", {})
        
        # Memory is usually already concise, but just in case:
        raw_chunks = self.chunk_text(text, self.config["chunk_size"], self.config["chunk_overlap"])
        
        return [
            {"text": rc, "chunk_index": i, "metadata": metadata}
            for i, rc in enumerate(raw_chunks)
        ]
