import yaml
from pathlib import Path
from core.config import BASE_DIR

CONFIG_PATH = BASE_DIR / "rag_config.yaml"

def load_rag_config():
    if not CONFIG_PATH.exists():
        return {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"[RAG Config] Load error: {e}")
        return {}

def get_rag_setting(key_path, default=None):
    config = load_rag_config()
    keys = key_path.split('.')
    val = config
    try:
        for k in keys:
            val = val[k]
        return val
    except (KeyError, TypeError):
        return default

# Shortcuts
def get_db_path():
    path = get_rag_setting("storage.db_path", "memory/rag_metadata.db")
    return BASE_DIR / path

def get_faiss_dir():
    path = get_rag_setting("storage.faiss_dir", "memory/faiss_indexes")
    return BASE_DIR / path

def get_embedding_model_name():
    return get_rag_setting("embedding.model_name", "BAAI/bge-small-en-v1.5")

def get_embedding_dim():
    return get_rag_setting("embedding.dimension", 384)

def get_namespace_config(namespace: str):
    return get_rag_setting(f"namespaces.{namespace}", {"chunk_size": 1000, "chunk_overlap": 100})
