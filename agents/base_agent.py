import json
import os
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI, RateLimitError

# Free providers that speak the OpenAI API. The app tries them in this order and
# uses every one that has a key in Streamlit Secrets. If one hits its limit,
# it automatically moves on to the next.
PROVIDERS = [
    {
        "name": "gemini",
        "secret": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "preferred": [
            "gemini-3.8-flash",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-flash-latest",
        ],
        "prefer_word": "flash",
    },
    {
        "name": "groq",
        "secret": "GROQ_API_KEY",
        "base_url": "https://api.groq.com/openai/v1",
        "preferred": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-20b",
            "openai/gpt-oss-120b",
        ],
        "prefer_word": None,
    },
]

# Models that can't do normal text chat
SKIP_WORDS = ("whisper", "tts", "guard", "orpheus", "playai", "embed", "image",
              "imagen", "veo", "aqa", "live", "audio", "vision-only")

_model_cache: Dict[str, str] = {}  # provider name -> model id (found once)


def _get_secret(name: str) -> Optional[str]:
    value = None
    try:
        import streamlit as st

        value = st.secrets.get(name)
    except Exception:
        pass  # no secrets file (e.g. running locally), fall back to env
    return value or os.getenv(name)


def _pick_model(provider: dict, client: OpenAI) -> str:
    """Choose a model that really exists for this key (model lists change often)."""
    name = provider["name"]
    if name in _model_cache:
        return _model_cache[name]

    override = _get_secret(f"{name.upper()}_MODEL")  # e.g. GEMINI_MODEL in Secrets
    if override:
        _model_cache[name] = override
        return override

    available = [m.id.replace("models/", "") for m in client.models.list().data]
    for candidate in provider["preferred"]:
        if candidate in available:
            _model_cache[name] = candidate
            return candidate

    chat = [m for m in available if not any(w in m.lower() for w in SKIP_WORDS)]
    word = provider["prefer_word"]
    if word:
        flash = [m for m in chat if word in m.lower()]
        chat = flash or chat
    if not chat:
        raise RuntimeError(f"{name}: no usable chat model found. Got: {available}")
    _model_cache[name] = chat[0]
    return chat[0]


class BaseAgent:
    def __init__(self, name: str, instructions: str):
        self.name = name
        self.instructions = instructions

        self.clients: List[tuple] = []  # (provider, client)
        for p in PROVIDERS:
            key = _get_secret(p["secret"])
            if key:
                self.clients.append((p, OpenAI(base_url=p["base_url"], api_key=key)))
        if not self.clients:
            raise RuntimeError(
                "No API key found. In Streamlit Cloud go to Manage app -> Settings -> "
                "Secrets and add GEMINI_API_KEY and/or GROQ_API_KEY."
            )

    async def run(self, messages: list) -> Dict[str, Any]:
        """Default run method to be overridden by child classes"""
        raise NotImplementedError("Subclasses must implement run()")

    def _query_ollama(self, prompt: str) -> str:
        """Kept under the old name so the other agent files don't need changes.
        It now calls free cloud models instead of a local Ollama server."""
        errors = []
        for provider, client in self.clients:
            try:
                model = _pick_model(provider, client)
            except Exception as e:
                errors.append(f"{provider['name']}: {e}")
                continue

            for attempt in range(2):
                try:
                    response = client.chat.completions.create(
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
                    errors.append(f"{provider['name']} ({model}) rate limit: {e}")
                    if attempt == 0:
                        time.sleep(8)  # short wait, then retry once
                except Exception as e:
                    errors.append(f"{provider['name']} ({model}): {e}")
                    break  # not a rate limit, go to the next provider

        raise RuntimeError("All providers failed. " + " | ".join(errors))

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
