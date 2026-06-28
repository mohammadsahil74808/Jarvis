import torch
from sentence_transformers import SentenceTransformer
from typing import List
import numpy as np

from rag_core.config import get_embedding_model_name, get_rag_setting

class Embedder:
    _instance = None

    def __init__(self):
        self.model_name = get_embedding_model_name()
        self.batch_size = get_rag_setting("embedding.batch_size", 32)
        
        # Auto-detect device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[Embedder] Loading {self.model_name} on {self.device}...")
        
        # Load model. We normalize embeddings for cosine similarity with L2 distance.
        self.model = SentenceTransformer(self.model_name, device=self.device)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def encode(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.array([])
            
        embeddings = self.model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True # Normalizes so L2 == Cosine
        )
        return embeddings
