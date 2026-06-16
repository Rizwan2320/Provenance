
"""
LLM and embedding model access — single initialisation point.

Rules:
  - Import get_llm_client() or get_embedding_model() — never
    initialise Anthropic() or SentenceTransformer() directly elsewhere.
  - Switching providers = change config.py only, nothing here changes.
  - Complexity added here only when a second provider is needed.
"""

from __future__ import annotations

from functools import lru_cache

import anthropic
from sentence_transformers import SentenceTransformer

from configurations.config import get_settings


@lru_cache(maxsize=1)
def get_llm_client() -> anthropic.Anthropic:
    """
    Returns a singleton Anthropic client pointed at AgentRouter.

    To switch to direct Anthropic:
      - Remove LLM_BASE_URL from .env
      - Change AGENTROUTER_API_KEY to ANTHROPIC_API_KEY
      Nothing else changes.
    """
    settings = get_settings()

    return anthropic.Anthropic(
        api_key=settings.agentrouter_api_key,
        base_url=settings.llm_base_url,
        # auth_token mirrors api_key — covers both auth
        # header patterns used by gateway proxies
        auth_token=settings.agentrouter_api_key,
    )


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    Returns a singleton sentence-transformers model.

    First call: downloads ~90MB weights to HuggingFace cache.
    Subsequent calls: returns cached in-memory model instantly.

    Windows note: if you hit OSError on first call, set
    TRANSFORMERS_CACHE=C:\\hf_cache in .env — see LEARNINGS.md.
    """
    settings = get_settings()
    return SentenceTransformer(settings.embedding_model_name)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Convenience wrapper — embeds a batch of texts.
    Returns a list of float vectors, one per input text.

    Batching here matters: SentenceTransformer is significantly
    faster encoding 100 texts at once than 100 individual calls.
    """
    model = get_embedding_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.tolist()