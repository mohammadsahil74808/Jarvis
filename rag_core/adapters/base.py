from typing import List, Dict, Any
from abc import ABC, abstractmethod

class BaseAdapter(ABC):
    @property
    @abstractmethod
    def namespace(self) -> str:
        pass
        
    @abstractmethod
    def ingest(self, source_uri: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Reads the source_uri and returns a list of chunk dictionaries.
        Each chunk should be like:
        {
            "text": "chunk text",
            "chunk_index": 0,
            "metadata": {"line_range": "1-50", "type": "function", ...}
        }
        """
        pass

    def chunk_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """A simple sliding window chunker."""
        chunks = []
        start = 0
        text_len = len(text)
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(text[start:end])
            if end == text_len:
                break
            start += (chunk_size - chunk_overlap)
        return chunks
