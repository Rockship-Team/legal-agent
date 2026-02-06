# Crawler Module Contract

## Overview
The Crawler module is responsible for fetching legal documents from thuvienphapluat.vn.

## Interface

### CrawlerService

```python
from abc import ABC, abstractmethod
from typing import List, Optional, AsyncIterator
from pydantic import BaseModel

class CrawlConfig(BaseModel):
    source: str = "thuvienphapluat"
    limit: Optional[int] = None
    categories: List[str] = []
    rate_limit_seconds: float = 2.0

class CrawledDocument(BaseModel):
    url: str
    document_number: str
    title: str
    document_type: str
    effective_date: Optional[str]
    issuing_authority: Optional[str]
    html_content: str
    pdf_url: Optional[str]

class CrawlerService(ABC):
    @abstractmethod
    async def crawl(self, config: CrawlConfig) -> AsyncIterator[CrawledDocument]:
        """
        Crawl legal documents based on configuration.

        Yields CrawledDocument objects as they are fetched.
        Respects rate limiting and handles pagination.
        """
        pass

    @abstractmethod
    async def fetch_document(self, url: str) -> CrawledDocument:
        """
        Fetch a single document by URL.
        """
        pass
```

## CLI Contract

```bash
# Crawl legal documents
legal-chatbot crawl --source thuvienphapluat --limit 10 --category "luat"

# Output: JSON lines to stdout
{"status": "started", "source": "thuvienphapluat", "limit": 10}
{"type": "document", "url": "...", "title": "..."}
{"type": "document", "url": "...", "title": "..."}
{"status": "completed", "count": 10}

# Errors: stderr
{"error": "rate_limited", "message": "...", "retry_after": 60}
```

## Error Handling

| Error | Code | Handling |
|-------|------|----------|
| Network timeout | NETWORK_TIMEOUT | Retry with exponential backoff |
| Rate limited | RATE_LIMITED | Wait and retry |
| Parse error | PARSE_ERROR | Log and skip document |
| Authentication required | AUTH_REQUIRED | Fail with clear message |

## Dependencies
- playwright: Browser automation
- beautifulsoup4: HTML parsing
- aiohttp: Async HTTP requests

## Testing Contract

```python
async def test_crawler_yields_documents():
    """Crawler should yield valid documents"""
    crawler = CrawlerService()
    config = CrawlConfig(limit=1)

    async for doc in crawler.crawl(config):
        assert doc.url
        assert doc.title
        assert doc.html_content

async def test_crawler_respects_rate_limit():
    """Crawler should not exceed rate limit"""
    # Verify time between requests >= rate_limit_seconds
```
