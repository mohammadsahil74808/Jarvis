import unittest
import os
from rag_core.adapters.code_adapter import CodeAdapter
from rag_core.adapters.project_adapter import ProjectAdapter
from rag_core.adapters.memory_adapter import MemoryAdapter

class TestAdapters(unittest.TestCase):
    def setUp(self):
        self.code_adapter = CodeAdapter()
        self.project_adapter = ProjectAdapter()
        self.memory_adapter = MemoryAdapter()
        
        # Create dummy file
        self.dummy_py = "test_dummy.py"
        with open(self.dummy_py, "w", encoding="utf-8") as f:
            f.write("def hello():\n    print('world')\n")
            
        self.dummy_non_utf8 = "test_non_utf8.py"
        with open(self.dummy_non_utf8, "wb") as f:
            f.write(b"def hello():\n    print('\xff')\n")

    def tearDown(self):
        if os.path.exists(self.dummy_py): os.remove(self.dummy_py)
        if os.path.exists(self.dummy_non_utf8): os.remove(self.dummy_non_utf8)

    def test_code_adapter_valid(self):
        chunks = self.code_adapter.ingest(self.dummy_py)
        self.assertGreater(len(chunks), 0)
        self.assertIn("hello", chunks[0]["text"])

    def test_code_adapter_non_utf8(self):
        # Should not crash, should replace characters
        chunks = self.code_adapter.ingest(self.dummy_non_utf8)
        self.assertGreater(len(chunks), 0)

    def test_memory_adapter(self):
        chunks = self.memory_adapter.ingest("dummy", text="Hello world", metadata={"source": "voice"})
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["metadata"]["source"], "voice")

if __name__ == '__main__':
    unittest.main()
