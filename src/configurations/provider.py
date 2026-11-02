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
from anthropic.types import TextBlock
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
def get_openai_client():
    from openai import OpenAI
    s = get_settings()
    if not s.openai_api_key:
        raise RuntimeError("llm_provider=openai but OPENAI_API_KEY is empty")
    return OpenAI(api_key=s.openai_api_key, base_url=s.openai_base_url)


def generate_text(prompt: str, model: str, max_tokens: int, timeout: float) -> tuple[str | None, str]:
    """(text or None, stop_reason). None + a length/max_tokens reason means a
    reasoning model spent its whole budget thinking — never treat it as success."""
    if get_settings().llm_provider == "openai":
        r = get_openai_client().chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=max_tokens,  # unverified for Luna; see preflight
            timeout=timeout,
        )
        choice = r.choices[0]
        return ((choice.message.content or "").strip() or None), str(choice.finish_reason)

    r = get_llm_client().messages.create(
        model=model, max_tokens=max_tokens, timeout=timeout,
        messages=[{"role": "user", "content": prompt}],
    )
    for block in r.content:
        if isinstance(block, TextBlock):
            return (block.text.strip() or None), r.stop_reason or ""
    return None, r.stop_reason or ""


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