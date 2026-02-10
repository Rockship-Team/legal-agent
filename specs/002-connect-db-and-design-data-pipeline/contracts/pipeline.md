# Pipeline Module Contract

## Overview
The Pipeline module orchestrates the data pipeline: discovery, crawling, parsing, indexing, and validation of legal documents by category.

## Interface

### PipelineService

```python
# services/pipeline.py
from typing import Optional
from models.pipeline import PipelineRun, CategoryConfig, CrawlResult

class PipelineService:
    """Orchestrates the data pipeline for legal document ingestion."""

    def __init__(self, db: DatabaseInterface, crawler: CrawlerService,
                 indexer: IndexerService, embedding: EmbeddingService):
        self.db = db
        self.crawler = crawler
        self.indexer = indexer
        self.embedding = embedding

    async def run(self, category: str, limit: int = 20) -> PipelineRun:
        """Execute full pipeline for a category.

        Phases:
        1. DISCOVERY: Find new/updated documents in category
        2. CRAWL: Fetch and parse document content
        3. INDEX: Store in DB + generate embeddings
        4. VALIDATE: Verify data integrity
        """
        pass

    async def discover(self, category: str) -> list[CrawlResult]:
        """Phase 1: Find documents to crawl.

        - Crawl category listing page
        - Extract document metadata
        - Compare content_hash with DB → identify new/changed docs
        """
        pass

    async def crawl_document(self, url: str) -> CrawlResult:
        """Phase 2: Crawl single document.

        - Fetch via Playwright + stealth
        - Save raw HTML to Supabase Storage
        - Parse articles (Điều) from content
        - Generate content hash
        """
        pass

    def index_document(self, result: CrawlResult) -> int:
        """Phase 3: Index document into DB.

        - Insert/update legal_documents
        - Insert articles
        - Generate + store embeddings via EmbeddingService
        - Returns articles indexed count
        """
        pass

    def validate(self, pipeline_run: PipelineRun) -> bool:
        """Phase 4: Validate pipeline results.

        - Check article count matches expected
        - Verify embeddings generated for all articles
        - Log results to pipeline_runs table
        """
        pass

    def get_category_config(self, name: str) -> CategoryConfig:
        """Get crawl configuration for a category."""
        pass
```

### CrawlerService Extensions

```python
# services/crawler.py — EXTENSIONS

class CrawlerService:
    # Existing methods preserved...

    async def crawl_category_listing(self, category_url: str,
                                      limit: int = 20) -> list[dict]:
        """Crawl category listing page to discover documents.

        Returns list of {url, title, document_number, status} dicts.
        Uses Playwright + stealth for Cloudflare bypass.
        """
        pass

    async def crawl_with_stealth(self, url: str) -> str:
        """Crawl a single page using Playwright + stealth.

        - Firefox browser (less fingerprinted)
        - playwright-stealth plugin
        - Realistic viewport (1920x1080), locale (vi-VN)
        - Wait for Cloudflare challenge (5-10s)
        - Rate limiting: 3-5s + random jitter
        """
        pass

    def compute_content_hash(self, html_content: str) -> str:
        """Compute SHA-256 hash of content for change detection."""
        pass
```

## CLI Contract

```bash
# Crawl a category
python -m legal_chatbot pipeline crawl --category dat-dai --limit 5
# Output:
# ┌─ Pipeline: đất đai ──────────────────────────────────────┐
# │ Phase 1: Discovery... found 6 documents                  │
# │ Phase 2: Crawling... 3 new, 0 updated, 3 skipped         │
# │ Phase 3: Indexing... 523 articles, 523 embeddings         │
# │ Phase 4: Validation... ✓ passed                           │
# │                                                            │
# │ ✓ Pipeline completed in 4m 32s                            │
# └────────────────────────────────────────────────────────────┘

# Check pipeline status
python -m legal_chatbot pipeline status
# Output:
# Last 5 runs:
# 2026-02-10 14:30  dat_dai    completed  3 docs  523 articles  4m 32s
# 2026-02-09 10:00  nha_o      completed  2 docs  180 articles  2m 15s

# List available categories
python -m legal_chatbot pipeline categories
# Output:
# dat_dai    Đất đai             Last crawl: 2026-02-10
# nha_o      Nhà ở               Last crawl: 2026-02-09
# dan_su     Dân sự              Never crawled
```

## Error Handling

| Error | Handling |
|-------|----------|
| Cloudflare challenge failed | Retry with fresh browser session (max 3) |
| Document parse failed | Log error, skip document, continue pipeline |
| Embedding generation failed | Log error, store article without embedding |
| Supabase insert failed | Retry 3x with backoff, then fail pipeline |
| Rate limited by website | Increase delay to 10s, retry after cooldown |

## Category Configuration

```python
LAND_LAW_CATEGORY = CategoryConfig(
    name="dat_dai",
    display_name="Đất đai",
    crawl_url="https://thuvienphapluat.vn/van-ban/Bat-dong-san/",
    document_urls=[
        "https://thuvienphapluat.vn/van-ban/Bat-dong-san/Luat-Dat-dai-2024-31-2024-QH15-523642.aspx",
        "https://thuvienphapluat.vn/van-ban/Bat-dong-san/Nghi-dinh-102-2024-ND-CP-huong-dan-Luat-Dat-dai-603982.aspx",
        "https://thuvienphapluat.vn/van-ban/Bat-dong-san/Nghi-dinh-101-2024-ND-CP-dang-ky-cap-giay-chung-nhan-quyen-su-dung-dat-tai-san-gan-lien-dat-613131.aspx",
    ],
    max_pages=20,
    rate_limit_seconds=4.0,
)
```

## Testing Contract

```python
async def test_pipeline_discovers_documents():
    """Pipeline should find documents in category listing"""
    results = await pipeline.discover("dat_dai")
    assert len(results) > 0
    assert all(r.document_number for r in results)

async def test_pipeline_crawls_with_hash():
    """Crawler should compute content hash"""
    result = await pipeline.crawl_document(url)
    assert result.content_hash
    assert len(result.content_hash) == 64  # SHA-256

def test_pipeline_skips_unchanged():
    """Pipeline should skip documents with same hash"""
    # Insert document with hash X
    # Re-crawl → same hash → skip
    assert result.is_new is False

async def test_pipeline_full_run():
    """Full pipeline should discover, crawl, index, validate"""
    run = await pipeline.run("dat_dai", limit=1)
    assert run.status == PipelineStatus.COMPLETED
    assert run.articles_indexed > 0
```
