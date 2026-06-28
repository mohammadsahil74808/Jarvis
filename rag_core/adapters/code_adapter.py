import os
from typing import List, Dict, Any
from rag_core.adapters.base import BaseAdapter
from rag_core.config import get_namespace_config
import tree_sitter_python as tspython
from tree_sitter import Language, Parser

class CodeAdapter(BaseAdapter):
    @property
    def namespace(self) -> str:
        return "code"
        
    def __init__(self):
        self.config = get_namespace_config(self.namespace)
        try:
            self.PY_LANGUAGE = Language(tspython.language())
            self.parser = Parser(self.PY_LANGUAGE)
        except Exception as e:
            print(f"[CodeAdapter] Tree-sitter init failed: {e}")
            self.parser = None

    def ingest(self, source_uri: str, **kwargs) -> List[Dict[str, Any]]:
        if not os.path.exists(source_uri):
            return []
            
        try:
            with open(source_uri, "r", encoding="utf-8", errors="replace") as f:
                code = f.read()
        except Exception as e:
            print(f"[CodeAdapter] Failed to read {source_uri}: {e}")
            return []

        chunks = []
        if self.parser and source_uri.endswith(".py"):
            # Tree-sitter parsing for Python
            tree = self.parser.parse(bytes(code, "utf8"))
            root_node = tree.root_node
            
            chunk_idx = 0
            for child in root_node.children:
                if child.type in ["function_definition", "class_definition"]:
                    start_line = child.start_point[0] + 1
                    end_line = child.end_point[0] + 1
                    func_text = code[child.start_byte:child.end_byte]
                    
                    # Extract name
                    name_node = next((n for n in child.children if n.type == "identifier"), None)
                    symbol_name = code[name_node.start_byte:name_node.end_byte] if name_node else "unknown"

                    chunks.append({
                        "text": func_text,
                        "chunk_index": chunk_idx,
                        "metadata": {
                            "type": child.type,
                            "symbol": symbol_name,
                            "line_range": f"{start_line}-{end_line}"
                        }
                    })
                    chunk_idx += 1
            
            # If nothing extracted via TS, fallback
            if not chunks:
                chunks = self._fallback_chunk(code)
        else:
            chunks = self._fallback_chunk(code)
            
        return chunks

    def _fallback_chunk(self, text: str) -> List[Dict[str, Any]]:
        raw_chunks = self.chunk_text(text, self.config["chunk_size"], self.config["chunk_overlap"])
        return [
            {"text": rc, "chunk_index": i, "metadata": {"type": "raw_text"}}
            for i, rc in enumerate(raw_chunks)
        ]
