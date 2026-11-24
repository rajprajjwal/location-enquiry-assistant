# Source history: Raj Kumar (a3ef3a6); migrated to the shared gateway.
"""Smoke-test the configured shared client without printing credentials."""
from dotenv import load_dotenv
from app.llm import get_llm


if __name__ == '__main__':
    load_dotenv()
    print(get_llm().invoke([{'role':'user','content':'Reply with one word: hello'}]).content)
