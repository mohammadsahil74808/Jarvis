import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from actions.browser_agent import browser_agent

def test_browser_agent():
    print("--- Testing BrowserAgent ---")
    
    # 1. Test Navigation (Headless)
    print("1. Testing go_to (headless)...")
    result = browser_agent({
        "action": "go_to",
        "url": "https://www.google.com",
        "headless": True
    })
    print(f"Result: {result}")
    
    # 2. Test Extraction
    print("\n2. Testing extraction (headless)...")
    result = browser_agent({
        "action": "extract",
        "selector": "body",
        "headless": True
    })
    print(f"Extraction result (first 100 chars): {result[:100]}...")
    
    # 3. Test Search
    print("\n3. Testing search (headless)...")
    result = browser_agent({
        "action": "search",
        "query": "Playwright Python",
        "headless": True
    })
    print(f"Search result: {result}")
    
    # 4. Test Close
    print("\n4. Testing close...")
    result = browser_agent({"action": "close"})
    print(f"Close result: {result}")
    
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    test_browser_agent()
