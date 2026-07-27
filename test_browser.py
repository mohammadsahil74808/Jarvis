# test_browser.py
"""Direct action test script for Browser Use in JARVIS."""

from actions.browser_use_action import browser_use_action

print("🚀 Starting Direct JARVIS Browser Action Test...")

# 1. Open Website Test
url = "https://google.com"
print(f"\n1️⃣ Opening website: {url}")
result1 = browser_use_action({"action": "open_website", "url": url})
print(f"Result: {result1}")

# 2. Search Web Test
query = "JARVIS AI Assistant"
print(f"\n2️⃣ Searching Web for: '{query}'")
result2 = browser_use_action({"action": "search_web", "query": query})
print(f"Result: {result2}")

# 3. Extract Webpage Content Test
print(f"\n3️⃣ Extracting text content from page...")
result3 = browser_use_action({"action": "extract_data", "query": "main content"})
print(f"Result summary:\n{result3[:300]}...")

print("\n✅ Direct Browser Use Action Test Completed Successfully!")
