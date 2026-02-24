"""Shared Anthropic LLM client — single source of truth for all LLM calls."""

import json
import logging
from typing import Optional

from anthropic import Anthropic

from legal_chatbot.utils.config import get_settings

logger = logging.getLogger(__name__)

# Module-level singleton
_client: Optional[Anthropic] = None


def get_client() -> Anthropic:
    """Get or create Anthropic client singleton."""
    global _client
    if _client is None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Add it to your .env file."
            )
        _client = Anthropic(api_key=settings.anthropic_api_key)
    return _client


def get_model() -> str:
    """Get configured model name."""
    return get_settings().llm_model


def call_llm(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1000,
    system: str = "",
) -> str:
    """Call Anthropic Messages API.

    Args:
        messages: List of {role, content} dicts. System messages are
                  extracted automatically if no `system` param given.
        temperature: Sampling temperature.
        max_tokens: Max response tokens.
        system: Explicit system prompt. If empty, extracted from messages.

    Returns:
        Response text string.
    """
    client = get_client()
    model = get_model()

    # Separate system message from user/assistant messages
    if not system:
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)
    else:
        user_messages = [m for m in messages if m["role"] != "system"]

    # Ensure at least one user message
    if not user_messages:
        user_messages = [{"role": "user", "content": ""}]

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": user_messages,
    }
    if system:
        kwargs["system"] = system
    if temperature > 0:
        kwargs["temperature"] = temperature

    response = client.messages.create(**kwargs)
    return response.content[0].text


def call_llm_json(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 4000,
    system: str = "",
) -> dict | list | None:
    """Call LLM and parse JSON from response.

    Handles markdown code blocks (```json ... ```) automatically.
    Returns parsed JSON or None on failure.
    """
    text = call_llm(
        messages, temperature=temperature, max_tokens=max_tokens, system=system
    )

    # Strip markdown code fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    else:
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM JSON: {e}\nRaw: {text[:500]}")
        return None


def search_web(
    query: str,
    max_tokens: int = 4000,
    allowed_domains: list[str] | None = None,
    max_searches: int = 5,
) -> str:
    """Call Claude with web_search tool.

    Uses Anthropic's server-side web_search_20250305 tool. Claude will
    autonomously search the web and synthesize results.

    Args:
        query: User question / search instruction.
        max_tokens: Max response tokens.
        allowed_domains: Restrict search to these domains only.
        max_searches: Max number of web searches per request.

    Returns:
        Claude's synthesized response text.
    """
    client = get_client()
    model = get_model()

    tool_def: dict = {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": max_searches,
    }
    if allowed_domains:
        tool_def["allowed_domains"] = allowed_domains

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        tools=[tool_def],
        messages=[{"role": "user", "content": query}],
    )

    # Extract text blocks from response (skip tool_use/tool_result blocks)
    texts = []
    for block in response.content:
        if hasattr(block, "text"):
            texts.append(block.text)

    return "\n".join(texts) if texts else ""


def search_web_urls(
    topic: str,
    domain: str = "thuvienphapluat.vn",
    limit: int = 20,
) -> list[dict]:
    """Search the web and extract URLs for a topic.

    Uses Claude web_search to find document URLs from a specific domain.

    Args:
        topic: Search topic (e.g. "đất đai", "lao động")
        domain: Domain to restrict search to.
        limit: Max number of URLs to return.

    Returns:
        List of {url, title} dicts.
    """
    client = get_client()
    model = get_model()

    tool_def = {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 5,
        "allowed_domains": [domain],
    }

    prompt = f"""Tìm các văn bản pháp luật Việt Nam về "{topic}" trên {domain}.

Yêu cầu:
1. Tìm kiếm luật, bộ luật, nghị định, thông tư liên quan đến {topic}
2. Ưu tiên văn bản MỚI NHẤT (2024, 2023, 2022)
3. Trả về tối đa {limit} kết quả

Trả về JSON array (CHỈ JSON, không text khác):
[
  {{"url": "https://{domain}/van-ban/...", "title": "Tên văn bản"}},
  ...
]"""

    response = client.messages.create(
        model=model,
        max_tokens=4000,
        tools=[tool_def],
        messages=[{"role": "user", "content": prompt}],
    )

    # Extract text and parse JSON
    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

    if not raw_text:
        logger.warning(f"Web search returned no text for topic: {topic}")
        return []

    # Parse JSON from response
    result = _parse_json_from_text(raw_text)
    if isinstance(result, list):
        # Filter: only keep valid URLs
        valid = []
        seen = set()
        for item in result:
            url = item.get("url", "")
            if url and url not in seen and domain in url:
                seen.add(url)
                valid.append({"url": url, "title": item.get("title", "")})
                if len(valid) >= limit:
                    break
        return valid

    logger.warning(f"Could not parse URLs from web search for '{topic}'")
    return []


def _parse_json_from_text(text: str) -> dict | list | None:
    """Extract and parse JSON from text that may contain markdown fences."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        parts = text.split("```")
        if len(parts) >= 3:
            text = parts[1].strip()
    else:
        text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON array or object in the text
        import re
        match = re.search(r'(\[[\s\S]*\]|\{[\s\S]*\})', text)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        return None
