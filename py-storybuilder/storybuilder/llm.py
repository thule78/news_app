import json
import re

from anthropic import Anthropic

from . import config

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def _extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1)
    return json.loads(text)


def call_json(system: str, user: str, max_retries: int = 2, max_tokens: int = 2000) -> dict:
    client = _get_client()
    messages = [{"role": "user", "content": user}]
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        response = client.messages.create(
            model=config.MODEL_ID,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        try:
            return _extract_json(text)
        except json.JSONDecodeError as exc:
            last_error = exc
            messages.append({"role": "assistant", "content": text})
            messages.append({
                "role": "user",
                "content": f"That was not valid JSON ({exc}). Reply again with ONLY the valid JSON object.",
            })

    raise RuntimeError(f"LLM did not return valid JSON after {max_retries + 1} attempts") from last_error
