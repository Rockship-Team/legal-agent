# Code Review Guidelines

## Always check
- New API endpoints have input validation and proper error handling
- Database queries use parameterized inputs (no SQL injection)
- Supabase RPC calls use service role key for writes, anon key for reads
- Vietnamese text is handled with UTF-8 encoding
- LLM prompts don't leak system instructions or sensitive data
- Async functions properly await all calls
- New crawl/pipeline changes maintain incremental crawl (SHA-256 hash check)

## Style
- Type hints on all function signatures
- Pydantic models for request/response schemas
- Use `call_llm()` / `call_llm_json()` from `utils/llm.py` — never instantiate LLM clients directly
- Prefer early returns over nested conditionals

## Skip
- Formatting-only changes
- Changes in `data/` directory (crawled content)
- Migration SQL files (reviewed separately)
