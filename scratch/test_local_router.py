import sys
import os
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from core.local_router import LocalRouter
import subprocess
from unittest.mock import MagicMock, patch

def test_injection_fix():
    print("Starting Local Router Injection Test...")
    router = LocalRouter()
    
    # 1. Test search sanitization
    # We'll mock webbrowser.open to see what URL is being called
    with patch('webbrowser.open') as mock_open:
        # Malicious query
        query = '"; calc #'
        router.search_google(query)
        
        called_url = mock_open.call_args[0][0]
        print(f"Called URL: {called_url}")
        
        # Check if ';' or 'calc' made it into the shell (it shouldn't in a dangerous way)
        # webbrowser.open handles the URL, and our _sanitize should remove ';'
        if ';' in called_url:
            print("FAILURE: Semicolon found in URL (though webbrowser might handle it, it's safer removed)")
        else:
            print("SUCCESS: Semicolon sanitized.")
            
        if 'calc' in called_url:
            print("INFO: 'calc' preserved as part of the query string (expected).")
        
    # 2. Test app launching fix
    # We'll mock subprocess.Popen
    with patch('subprocess.Popen') as mock_popen:
        router.open_notepad()
        # Should be called with list of args
        args = mock_popen.call_args[0][0]
        print(f"Popen args: {args}")
        if isinstance(args, list) and args[0] == "cmd":
            print("SUCCESS: subprocess.Popen used with list of arguments.")
        else:
            print("FAILURE: subprocess.Popen not used as expected.")

if __name__ == "__main__":
    test_injection_fix()
