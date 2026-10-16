import json
import os
from typing import Any, Dict

from openai import OpenAI


def _get_api_key() -> str:
    """Read the OpenAI key from Streamlit secrets first, then environment variables."""
    key = None
    try:
        import streamlit as st

        key = st.secrets.get("OPENAI_API_KEY")
    except Exception:
        pass  # no secrets file (e.g. running locally), fall back to env
    key = key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it in Streamlit Cloud: "
            "Manage app -> Settings -> Secrets."
        )
    return key


MODEL_NAME = "gpt-4o-mini"


class BaseAgent:
    def __init__(self, name: str, instructions: str):
        self.name = name
        self.instructions = instructions
        # Real OpenAI API (no base_url, no localhost)
        self.client = OpenAI(api_key=_get_api_key())

    async def run(self, messages: list) -> Dict[str, Any]:
        """Default run method to be overridden by child classes"""
        raise NotImplementedError("Subclasses must implement run()")

    def _query_ollama(self, prompt: str) -> str:
        """Kept under the old name so the other agent files don't need changes.
        It now calls OpenAI instead of a local Ollama server."""
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
        except Exception as e:
            print(f"Error querying OpenAI: {str(e)}")
            raise

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
