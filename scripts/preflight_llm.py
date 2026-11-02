from __future__ import annotations
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[1]
src_path = repo_root / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

"""One cheap call to verify the configured model/endpoint works with the
Anthropic-shaped client before spending a pipeline run on it."""
from configurations.config import get_settings
from configurations.provider import generate_text

s = get_settings()
is_openai = s.llm_provider == "openai"
key_set = bool(s.openai_api_key if is_openai else s.agentrouter_api_key)
print("provider:", s.llm_provider, "| model:", s.llm_model_name,
      "| base_url:", s.openai_base_url if is_openai else s.llm_base_url,
      "| key set:", key_set)
if not key_set:
    raise SystemExit("key not set: stopping before any API call")

text, stop = generate_text("Reply with the single word: OK", model=s.llm_model_name,
                           max_tokens=256, timeout=30.0)
print("stop_reason:", stop)
print("text:", repr(text))
    