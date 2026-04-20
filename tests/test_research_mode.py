import sys
import os

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_root)

from actions.research_mode import research_mode

def test_research():
    print("--- Testing Research Mode ---")
    
    # 1. Tech Research Test
    print("\n1. Testing Tech Research Mode...")
    params = {
        "action": "research",
        "query": "Gemini 1.5 Pro features",
        "research_mode": "tech",
        "max_sites": 2
    }
    result = research_mode(params)
    print(f"Tech Research Results:\n{result[:500]}...")
    
    # 2. News/General Test
    print("\n2. Testing News Summarization Data...")
    params = {
        "action": "summarize",
        "query": "latest space news",
        "research_mode": "news",
        "max_sites": 1
    }
    result = research_mode(params)
    print(f"Summarization Data Results:\n{result[:500]}...")

    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    test_research()
