import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import Callable

from rag_core.config import get_rag_setting

class DebouncedIndexer:
    def __init__(self, callback: Callable[[str], None], debounce_seconds: int = 5):
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self._timers = {}
        self._lock = threading.Lock()

    def trigger(self, filepath: str):
        with self._lock:
            if filepath in self._timers:
                self._timers[filepath].cancel()
            timer = threading.Timer(self.debounce_seconds, self._execute, args=[filepath])
            self._timers[filepath] = timer
            timer.start()

    def _execute(self, filepath: str):
        with self._lock:
            if filepath in self._timers:
                del self._timers[filepath]
        try:
            self.callback(filepath, "modified")
        except Exception as e:
            print(f"[DebouncedIndexer] Error indexing {filepath}: {e}")

class RAGFileHandler(FileSystemEventHandler):
    def __init__(self, indexer: DebouncedIndexer, engine):
        self.indexer = indexer
        self.engine = engine

    def on_modified(self, event):
        if not event.is_directory:
            self.indexer.trigger(event.src_path)
            
    def on_created(self, event):
        if not event.is_directory:
            self.indexer.trigger(event.src_path)
            
    def on_deleted(self, event):
        if not event.is_directory:
            # We can skip debouncing for deletion as it's immediate and final
            self.engine.auto_remove_file(event.src_path)

class WatchdogMonitor:
    def __init__(self, engine):
        self.engine = engine
        self.debounce_seconds = get_rag_setting("watchdog.debounce_seconds", 5)
        self.paths = get_rag_setting("watchdog.monitored_paths", [])
        self.observer = Observer()
        
        self.indexer = DebouncedIndexer(self._on_file_changed, self.debounce_seconds)
        self.handler = RAGFileHandler(self.indexer, self.engine)

    def _on_file_changed(self, filepath: str, action: str):
        # Delegate to engine
        print(f"[WatchdogMonitor] Queueing auto-ingest for: {filepath}")
        self.engine.auto_ingest_file(filepath)

    def start(self):
        if not self.paths:
            return
        for path in self.paths:
            try:
                self.observer.schedule(self.handler, path, recursive=True)
                print(f"[WatchdogMonitor] Watching {path}")
            except Exception as e:
                print(f"[WatchdogMonitor] Failed to watch {path}: {e}")
        
        self.observer.start()

    def stop(self):
        self.observer.stop()
        self.observer.join()
