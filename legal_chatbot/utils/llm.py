"""Shared LLM client — single source of truth for all LLM calls.

Supports Anthropic (default) and DeepSeek (OpenAI-compatible) for chat.
"""

import json
import logging
from typing import Optional

from anthropic import Anthropic, AsyncAnthropic

from legal_chatbot.utils.config import get_settings

logger = logging.getLogger(__name__)

# Hardcoded Sonnet model for legal Q&A — accuracy-critical, never use cheap model
SONNET_MODEL = "claude-sonnet-4-20250514"

# Module-level singletons
_client: Optional[Anthropic] = None
_async_client: Optional[AsyncAnthropic] = None
_deepseek_client = None
_deepseek_async_client = None


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


def get_async_client() -> AsyncAnthropic:
    """Get or create async Anthropic client singleton."""
    global _async_client
    if _async_client is None:
        settings = get_settings()
        if not settings.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not set. Add it to your .env file."
            )
        _async_client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    return _async_client


def _use_deepseek() -> bool:
    """Check if DeepSeek is configured for chat."""
    settings = get_settings()
    return bool(settings.deepseek_api_key)


def _get_deepseek_client():
    """Get or create DeepSeek (OpenAI-compatible) client singleton."""
    global _deepseek_client
    if _deepseek_client is None:
        from openai import OpenAI
        settings = get_settings()
        _deepseek_client = OpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
    return _deepseek_client


def _get_deepseek_async_client():
    """Get or create async DeepSeek client singleton."""
    global _deepseek_async_client
    if _deepseek_async_client is None:
        from openai import AsyncOpenAI
        settings = get_settings()
        _deepseek_async_client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url="https://api.deepseek.com",
        )
    return _deepseek_async_client


def _build_oai_messages(messages: list[dict], system: str) -> list[dict]:
    """Convert Anthropic-style messages to OpenAI format (system as first message)."""
    oai_msgs = []
    if not system:
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                oai_msgs.append(msg)
    else:
        oai_msgs = [m for m in messages if m["role"] != "system"]

    if system:
        oai_msgs.insert(0, {"role": "system", "content": system})
    if not oai_msgs:
        oai_msgs = [{"role": "user", "content": ""}]
    return oai_msgs


def get_model() -> str:
    """Get configured model name."""
    return get_settings().llm_model


def _prepare_kwargs(
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int,
    system: str,
) -> dict:
    """Build kwargs dict for Anthropic Messages API (shared by all call_llm variants)."""
    if not system:
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            else:
                user_messages.append(msg)
    else:
        user_messages = [m for m in messages if m["role"] != "system"]

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
    return kwargs


def call_llm(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 1000,
    system: str = "",
) -> str:
    """Call Anthropic Messages API (uses default model from LLM_MODEL env var).

    For legal Q&A where accuracy is critical, use call_llm_sonnet() instead.
    """
    client = get_client()
    kwargs = _prepare_kwargs(messages, get_model(), temperature, max_tokens, system)
    response = client.messages.create(**kwargs)
    return response.content[0].text


def call_llm_sonnet(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
    system: str = "",
) -> str:
    """Call LLM for legal Q&A where accuracy is critical.

    Routes to DeepSeek if configured, otherwise uses Anthropic Sonnet.
    """
    if _use_deepseek():
        client = _get_deepseek_client()
        model = get_settings().deepseek_model
        oai_msgs = _build_oai_messages(messages, system)
        # Lower temperature for DeepSeek to reduce hallucination
        ds_temp = min(temperature, 0.1)
        response = client.chat.completions.create(
            model=model,
            messages=oai_msgs,
            temperature=ds_temp,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    client = get_client()
    kwargs = _prepare_kwargs(messages, SONNET_MODEL, temperature, max_tokens, system)
    response = client.messages.create(**kwargs)
    return response.content[0].text


def call_llm_stream(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
    system: str = "",
):
    """Stream Anthropic Messages API — yields text chunks (synchronous).

    Uses default model from LLM_MODEL env var.
    """
    client = get_client()
    kwargs = _prepare_kwargs(messages, get_model(), temperature, max_tokens, system)
    with client.messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            yield text


async def call_llm_stream_async(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
    system: str = "",
):
    """Stream Anthropic Messages API — async generator (default model)."""
    client = get_async_client()
    kwargs = _prepare_kwargs(messages, get_model(), temperature, max_tokens, system)
    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield text


async def call_llm_stream_sonnet_async(
    messages: list[dict],
    temperature: float = 0.3,
    max_tokens: int = 4096,
    system: str = "",
):
    """Stream LLM response for legal Q&A.

    Routes to DeepSeek if configured, otherwise uses Anthropic Sonnet.
    """
    if _use_deepseek():
        client = _get_deepseek_async_client()
        model = get_settings().deepseek_model
        oai_msgs = _build_oai_messages(messages, system)
        ds_temp = min(temperature, 0.1)
        stream = await client.chat.completions.create(
            model=model,
            messages=oai_msgs,
            temperature=ds_temp,
            max_tokens=max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
        return

    client = get_async_client()
    kwargs = _prepare_kwargs(messages, SONNET_MODEL, temperature, max_tokens, system)
    async with client.messages.stream(**kwargs) as stream:
        async for text in stream.text_stream:
            yield text


def call_llm_json(
    messages: list[dict],
    temperature: float = 0.1,
    max_tokens: int = 4000,
    system: str = "",
    use_sonnet: bool = False,
) -> dict | list | None:
    """Call LLM and parse JSON from response.

    Handles markdown code blocks (```json ... ```) automatically.
    Args:
        use_sonnet: If True, uses SONNET_MODEL for higher accuracy.
    Returns parsed JSON or None on failure.
    """
    llm_fn = call_llm_sonnet if use_sonnet else call_llm
    text = llm_fn(
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
        logger.debug(f"LLM returned non-JSON (expected for non-legal queries): {text[:200]}")
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

    tool_def: dict = {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": max_searches,
    }
    if allowed_domains:
        tool_def["allowed_domains"] = allowed_domains

    response = client.messages.create(
        model=SONNET_MODEL,
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
    Always uses SONNET_MODEL — Haiku is unreliable with web search + JSON.

    Args:
        topic: Search topic (e.g. "đất đai", "lao động")
        domain: Domain to restrict search to.
        limit: Max number of URLs to return.

    Returns:
        List of {url, title} dicts.
    """
    client = get_client()

    tool_def = {
        "type": "web_search_20250305",
        "name": "web_search",
        "max_uses": 5,
        "allowed_domains": [domain],
    }

    prompt = f"""Tìm NỘI DUNG TOÀN VĂN các văn bản pháp luật Việt Nam về "{topic}" trên {domain}.

Yêu cầu:
1. CHỈ tìm trang TOÀN VĂN văn bản luật (URL dạng {domain}/van-ban/.../*.aspx)
2. KHÔNG lấy bài viết tổng hợp, hỏi đáp, tin tức (URL chứa /phap-luat/, /hoi-dap/, /chinh-sach/)
3. Tìm: luật, bộ luật, nghị định, thông tư liên quan đến {topic}
4. Ưu tiên văn bản MỚI NHẤT (2024, 2023, 2022)
5. Trả về tối đa {limit} kết quả

Trả về JSON array (CHỈ JSON, không text khác):
[
  {{"url": "https://{domain}/van-ban/.../<ten-van-ban>.aspx", "title": "Tên văn bản"}},
  ...
]"""

    response = client.messages.create(
        model=SONNET_MODEL,
        max_tokens=4000,
        tools=[tool_def],
        messages=[{"role": "user", "content": prompt}],
    )

    # Strategy 1: Extract URLs directly from WebSearchToolResultBlock
    # (most reliable — doesn't depend on LLM outputting valid JSON)
    direct_urls: list[dict] = []
    seen = set()
    for block in response.content:
        # WebSearchToolResultBlock has .content list of WebSearchResultBlock items
        if getattr(block, "type", None) == "web_search_tool_result":
            for item in getattr(block, "content", []):
                url = getattr(item, "url", "")
                title = getattr(item, "title", "")
                if url and url not in seen and domain in url:
                    seen.add(url)
                    direct_urls.append({"url": url, "title": title})

    # Filter: prefer full-text law pages (/van-ban/), deprioritize blog/news articles
    blog_patterns = ['/phap-luat/', '/hoi-dap/', '/chinh-sach/', '/thoi-su-', '/tu-van-']
    law_urls = [u for u in direct_urls if '/van-ban/' in u["url"]]
    other_urls = [u for u in direct_urls if '/van-ban/' not in u["url"]
                  and not any(p in u["url"] for p in blog_patterns)]
    filtered = law_urls + other_urls

    if filtered:
        logger.info(f"Web search found {len(filtered)} URLs ({len(law_urls)} law pages) for '{topic}'")
        return filtered[:limit]
    if direct_urls:
        logger.info(f"Web search found {len(direct_urls)} URLs (no law pages) for '{topic}'")
        return direct_urls[:limit]

    # Strategy 2: Parse JSON from LLM text response (fallback)
    raw_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            raw_text += block.text

    if raw_text:
        result = _parse_json_from_text(raw_text)
        if isinstance(result, list):
            valid = []
            for item in result:
                url = item.get("url", "")
                if url and url not in seen and domain in url:
                    seen.add(url)
                    valid.append({"url": url, "title": item.get("title", "")})
                    if len(valid) >= limit:
                        break
            if valid:
                return valid

    logger.warning(f"Could not extract URLs from web search for '{topic}'")
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
