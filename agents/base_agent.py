import json
import os
import time
from typing import Any, Dict

from openai import OpenAI, RateLimitError

# ---- Provider settings (Groq: free tier, OpenAI-compatible API) ----
BASE_URL = "https://api.groq.com/openai/v1"
MODEL_NAME = "llama-3.3-70b-versatile"  # if you hit rate limits, try "llama-3.1-8b-instant"
SECRET_NAME = "GROQ_API_KEY"


def _get_api_key() -> str:
    """Read the key from Streamlit secrets first, then environment variables."""
    key = None
    try:
        import streamlit as st

        key = st.secrets.get(SECRET_NAME)
    except Exception:
        pass  # no secrets file (e.g. running locally), fall back to env
    key = key or os.getenv(SECRET_NAME)
    if not key:
        raise RuntimeError(
            f"{SECRET_NAME} is not set. Add it in Streamlit Cloud: "
            "Manage app -> Settings -> Secrets."
        )
    return key


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
        last_error = None
        for attempt in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": self.instructions},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.7,
                    max_tokens=2000,
                )
                return response.choices[0].message.content
            except RateLimitError as e:
                # Free tiers have per-minute limits: wait and retry
                last_error = e
                time.sleep(10 * (attempt + 1))
            except Exception as e:
                print(f"Error querying model: {str(e)}")
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
