import unittest
import os
import time
from rag_core.engine import RAGEngine

class TestEngine(unittest.TestCase):
    def setUp(self):
        self.engine = RAGEngine()
        # Create a dummy file
        self.test_file = "test_ingest.py"
        with open(self.test_file, "w") as f:
            f.write("print('test engine')")

    def tearDown(self):
        if os.path.exists(self.test_file): os.remove(self.test_file)
        self.engine.auto_remove_file(self.test_file)
        
    def test_auto_ingest_and_query(self):
        self.engine.auto_ingest_file(self.test_file)
        # Wait for queue to process
        self.engine.ingest_queue.join()
        
        results = self.engine.query("test engine", namespaces=["code"])
        self.assertTrue(any("test engine" in r["text"] for r in results))
        
    def test_document_deletion(self):
        self.engine.auto_ingest_file(self.test_file)
        self.engine.ingest_queue.join()
        
        # Now remove
        self.engine.auto_remove_file(self.test_file)
        self.engine.ingest_queue.join()
        
        results = self.engine.query("test engine", namespaces=["code"])
        self.assertEqual(len(results), 0)

if __name__ == '__main__':
    unittest.main()
