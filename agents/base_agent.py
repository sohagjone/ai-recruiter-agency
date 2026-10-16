import json
import os
import time
from typing import Any, Dict, Optional

from openai import OpenAI, RateLimitError

# ---- Provider settings (Groq: free tier, OpenAI-compatible API) ----
BASE_URL = "https://api.groq.com/openai/v1"
SECRET_NAME = "GROQ_API_KEY"

# Groq changes its model list often, so the app asks Groq which models your key can
# use and picks the first one from this list. Put your favourite first.
PREFERRED_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "groq/compound-mini",
    "groq/compound",
]
# Words that mark models that can't do normal chat (audio, safety filters, etc.)
SKIP_WORDS = ("whisper", "tts", "guard", "orpheus", "playai", "embed", "prompt-guard")

_model_cache: Optional[str] = None  # found once, reused on every Streamlit rerun


def _get_secret(name: str) -> Optional[str]:
    value = None
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:
        pass  # no secrets file (e.g. running locally), fall back to env
    return value or os.getenv(name)


def _get_api_key() -> str:
    key = _get_secret(SECRET_NAME)
    if not key:
        raise RuntimeError(
            f"{SECRET_NAME} is not set. Add it in Streamlit Cloud: "
            "Manage app -> Settings -> Secrets."
        )
    return key


def _pick_model(client: OpenAI) -> str:
    """Choose a model that really exists for this key."""
    global _model_cache
    if _model_cache:
        return _model_cache

    # Optional manual override: add GROQ_MODEL = "model-id" in Secrets
    override = _get_secret("GROQ_MODEL")
    if override:
        _model_cache = override
        return _model_cache

    available = [m.id for m in client.models.list().data]
    for name in PREFERRED_MODELS:
        if name in available:
            _model_cache = name
            return _model_cache

    chat_models = [m for m in available if not any(w in m.lower() for w in SKIP_WORDS)]
    if not chat_models:
        raise RuntimeError(f"No usable chat model found. Groq returned: {available}")
    _model_cache = chat_models[0]
    return _model_cache


class BaseAgent:
    def __init__(self, name: str, instructions: str):
        self.name = name
        self.instructions = instructions
        self.client = OpenAI(base_url=BASE_URL, api_key=_get_api_key())

    async def run(self, messages: list) -> Dict[str, Any]:
        """Default run method to be overridden by child classes"""
        raise NotImplementedError("Subclasses must implement run()")

    def _query_ollama(self, prompt: str) -> str:
        """Kept under the old name so the other agent files don't need changes.
        It now calls Groq instead of a local Ollama server."""
        model = _pick_model(self.client)
        last_error = None
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": self.instructions},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=4000,
                )
                return response.choices[0].message.content or ""
            except RateLimitError as e:
                # Free tiers have per-minute limits: wait and retry
                last_error = e
                time.sleep(10 * (attempt + 1))
            except Exception as e:
                print(f"Error querying model '{model}': {str(e)}")
                raise
        raise last_error

    def _parse_json_safely(self, text: str) -> Dict[str, Any]:
        """Safely parse JSON from text, handling potential errors"""
        try:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(text[start : end + 1])
            return {"error": "No JSON content found"}
        except json.JSONDecodeError:
            return {"error": "Invalid JSON content"}
