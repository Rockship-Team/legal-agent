# Contract: Pipeline Service (Incremental)

**Module**: `legal_chatbot/services/pipeline.py` (modified)

## Interface Changes

```python
class PipelineService:
    """Modified: Incremental crawl with document registry."""

    async def run(
        self,
        category: str,
        limit: int = 50,
        trigger_type: str = 'manual',
        force: bool = False
    ) -> PipelineResult:
        """Run pipeline for a category.

        Changes from 002:
        - ADDED: Read URLs from document_registry (not hardcoded)
        - ADDED: Content hash comparison (skip unchanged)
        - ADDED: trigger_type tracking ('manual', 'scheduled', 'forced')
        - ADDED: documents_skipped count
        - ADDED: duration_seconds tracking

        Args:
            category: Category name (e.g. 'dat_dai')
            limit: Max documents per run
            trigger_type: 'manual' | 'scheduled' | 'forced'
            force: Skip hash comparison, re-crawl everything

        Flow:
        1. Create pipeline_run entry (with trigger_type)
        2. Load document_registry entries for category
        3. For each entry:
           a. If not force: compute content hash, compare with stored
           b. If unchanged: skip, increment documents_skipped
           c. If changed: crawl → parse → embed → upsert
        4. Update category counts (document_count, article_count)
        5. Finalize pipeline_run (status, duration, stats)
        """

    async def _check_document_changed(
        self, registry_entry: DocumentRegistryEntry
    ) -> bool:
        """Check if document content has changed since last crawl.

        Strategy:
        1. Full crawl with Playwright (no HEAD request optimization)
        2. Normalize HTML → extract main content → SHA-256
        3. Compare with registry_entry.last_content_hash
        4. Return True if different or if never checked

        Note: thuvienphapluat.vn does not support ETag/Last-Modified
        """

    async def _get_document_registry(
        self, category: str
    ) -> List[DocumentRegistryEntry]:
        """Load active registry entries for a category.

        Returns entries sorted by priority (1=highest).
        Only returns is_active=True entries.
        """

    async def _update_category_counts(self, category: str) -> None:
        """Call update_category_counts() RPC after pipeline completes."""

    def _compute_normalized_hash(self, html_content: str) -> str:
        """Compute SHA-256 of normalized content.

        Steps:
        1. Parse with BeautifulSoup
        2. Remove: script, style, noscript, iframe
        3. Remove: ad/tracking class elements
        4. Extract: div.content1 or div.toanvancontent
        5. Get text, collapse whitespace
        6. SHA-256 hash
        """
```

## Dependencies

- `db/supabase.py` (document_registry CRUD, update_category_counts RPC)
- `services/crawler.py` (crawl_with_stealth — unchanged)
- `services/embedding.py` (embed_and_store — unchanged)
- `services/indexer.py` (parse_html_articles — unchanged)
