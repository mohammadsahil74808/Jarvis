import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.config import get_api_key, get_gemini_client, LIVE_MODEL

def verify_gemini():
    print("===== GEMINI VERIFICATION =====\n")

    # 1. API key loaded
    api_key = get_api_key()
    assert api_key and len(api_key) > 20, "API key missing or invalid"
    print("[OK] API key loaded")

    # 2. SDK initialized
    client = get_gemini_client()
    assert client is not None, "SDK initialization failed"
    print("[OK] SDK initialized")

    # 3. Model exists
    models = list(client.models.list())
    model_names = [m.name for m in models]
    assert any(LIVE_MODEL in name for name in model_names), f"Model {LIVE_MODEL} not found in model list"
    print("[OK] Model exists")

    # 4. Request sent & Response received
    res = client.models.generate_content(
        model="models/gemini-2.5-flash",
        contents="Confirm Gemini operational status in 5 words."
    )
    assert res and res.text, "No response text received from Gemini"
    print("[OK] Request sent")
    print("[OK] Response received")

    # 5. Response parsed
    output_text = res.text.strip()
    assert len(output_text) > 0, "Parsed text is empty"
    print("[OK] Response parsed")

    # 6. Jarvis received output
    print(f"[OK] Jarvis received output: \"{output_text}\"")
    print("\n===== ALL VERIFICATION CHECKS PASSED =====")

if __name__ == "__main__":
    verify_gemini()
