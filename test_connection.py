"""
Smoke-test: verifies the custom LLM endpoint is reachable and the API key is valid.
Run:  python test_connection.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import httpx

BASE_URL = os.getenv("OPENAI_BASE_URL", "https://103.42.50.41:1034/v1")
API_KEY  = os.getenv("OPENAI_API_KEY", "")
MODEL    = os.getenv("OPENAI_MODEL", "qwen3-8b")
VERIFY   = os.getenv("SSL_VERIFY", "false").lower() != "false"

print(f"Endpoint : {BASE_URL}")
print(f"Model    : {MODEL}")
print(f"SSL verify: {VERIFY}")
print(f"Key      : {API_KEY[:12]}...")
print()


def test_models():
    print("--- GET /models ---")
    r = httpx.get(
        f"{BASE_URL}/models",
        headers={"Authorization": f"Bearer {API_KEY}"},
        verify=VERIFY,
        timeout=10,
    )
    print(f"Status: {r.status_code}")
    print(r.text[:500])


def test_chat():
    print("\n--- POST /chat/completions ---")
    r = httpx.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [{"role": "user", "content": "Reply with one word: hello"}],
            "max_tokens": 20,
        },
        verify=VERIFY,
        timeout=30,
    )
    print(f"Status: {r.status_code}")
    print(r.text[:500])


if __name__ == "__main__":
    try:
        test_models()
        test_chat()
    except Exception as e:
        print(f"Error: {e}")
