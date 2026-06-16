# scripts/smoke_test_providers.py
"""
Run this before Phase 1 to verify both providers work.
Usage: uv run python scripts/smoke_test_providers.py
"""

from configurations.provider import embed_texts, get_llm_client
from configurations.config import get_settings

def test_llm():
    settings = get_settings()
    client = get_llm_client()
    response = client.messages.create(
        model=settings.llm_model_name,
        max_tokens=32,
        messages=[{"role": "user", "content": "Reply with: OK"}],
    )
    print(f"LLM OK → {response.content[0].text.strip()}")

def test_embeddings():
    vectors = embed_texts(["hello world", "test sentence"])
    print(f"Embedding OK → dim={len(vectors[0])}, count={len(vectors)}")

if __name__ == "__main__":
    test_llm()
    test_embeddings()