"""Pipeline service — orchestrates crawl, parse, index, validate"""

import asyncio
import hashlib
import logging
import time
import uuid
from datetime import datetime
from typing import List, Optional

from legal_chatbot.db.base import DatabaseInterface
from legal_chatbot.models.pipeline import (
    CategoryConfig,
    CrawlResult,
    DocumentRegistryEntry,
    PipelineRun,
    PipelineStatus,
)
from legal_chatbot.services.crawler import CrawlerService
from legal_chatbot.services.embedding import EmbeddingService
from legal_chatbot.services.indexer import IndexerService
from legal_chatbot.utils.vietnamese import (
    edit_distance,
    normalize_category_name,
    remove_diacritics,
)

logger = logging.getLogger(__name__)

class InvalidCategoryError(ValueError):
    """Raised when a category name is not a valid legal domain."""
    pass

# Default crawl settings (used when not stored in DB)
_DEFAULT_RATE_LIMIT = 4.0
_DEFAULT_MAX_PAGES = 20


class PipelineService:
    """Orchestrates the data pipeline for legal document ingestion."""

    def __init__(
        self,
        db: DatabaseInterface,
        crawler: Optional[CrawlerService] = None,
        embedding: Optional[EmbeddingService] = None,
    ):
        self.db = db
        self.crawler = crawler or CrawlerService()
        self.embedding = embedding or EmbeddingService()
        self.indexer = IndexerService()
        self._category_id_cache: dict[str, str] = {}

    def sync_categories(self) -> int:
        """Load categories from DB into cache. Returns count loaded."""
        if not hasattr(self.db, "_read"):
            return 0

        client = self.db._read()
        result = (
            client.table("legal_categories")
            .select("id, name")
            .eq("is_active", True)
            .execute()
        )
        count = 0
        for cat in result.data:
            self._category_id_cache[cat["name"]] = cat["id"]
            count += 1
        logger.info(f"Loaded {count} categories from DB")
        return count

    def get_category_id(self, category_name: str) -> Optional[str]:
        """Get category UUID from cache or DB."""
        if not category_name:
            return None

        if category_name in self._category_id_cache:
            return self._category_id_cache[category_name]

        if not hasattr(self.db, "_read"):
            return None

        client = self.db._read()
        result = (
            client.table("legal_categories")
            .select("id")
            .eq("name", category_name)
            .limit(1)
            .execute()
        )
        if result.data:
            self._category_id_cache[category_name] = result.data[0]["id"]
            return result.data[0]["id"]
        return None

    def _fuzzy_match_category(self, name: str, max_distance: int = 2) -> Optional[str]:
        """Find an existing category whose name is close to `name`.

        Returns category_id if a match within max_distance is found, else None.
        """
        if not hasattr(self.db, "_read"):
            return None

        client = self.db._read()
        cats = client.table("legal_categories").select("id, name").execute()
        if not cats.data:
            return None

        best_id = None
        best_dist = max_distance + 1
        for cat in cats.data:
            dist = edit_distance(name, cat["name"])
            if dist < best_dist:
                best_dist = dist
                best_id = cat["id"]
                best_name = cat["name"]

        if best_id and best_dist <= max_distance:
            self._category_id_cache[best_name] = best_id
            # Also cache the typo variant so repeat lookups are instant
            self._category_id_cache[name] = best_id
            logger.info(
                f"Fuzzy matched category: '{name}' → '{best_name}' (distance={best_dist})"
            )
            return best_id
        return None

    @staticmethod
    def _llm_validate_category(raw_name: str) -> Optional[str]:
        """Ask LLM whether this is a valid Vietnamese legal category.

        Returns a suggested category name if valid, None if not.
        """
        try:
            from legal_chatbot.utils.llm import call_llm

            answer = call_llm(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Bạn là chuyên gia pháp luật Việt Nam. "
                            "Kiểm tra xem input có phải lĩnh vực pháp luật hợp lệ không. "
                            "Trả lời ĐÚNG 1 dòng:\n"
                            "- Nếu hợp lệ: YES|tên_lĩnh_vực_snake_case (ví dụ: YES|vay_tien)\n"
                            "- Nếu không hợp lệ: NO|lý do ngắn"
                        ),
                    },
                    {"role": "user", "content": f"Lĩnh vực: {raw_name}"},
                ],
                temperature=0,
                max_tokens=50,
            ).strip()

            if answer.upper().startswith("YES|"):
                suggested = answer.split("|", 1)[1].strip()
                return normalize_category_name(suggested) if suggested else None
            return None

        except Exception as e:
            logger.warning(f"LLM category validation failed: {e}")
            return None

    @staticmethod
    def _extract_domain_from_title(title: str) -> Optional[str]:
        """Extract the legal domain name from a Vietnamese law document title.

        Works with both diacritics and non-diacritics titles by normalizing
        to ASCII first, then pattern-matching common Vietnamese law title formats.

        Examples (after internal normalization):
            "bo luat dan su 2015"              → "dan su"
            "luat duong bo 2024"               → "duong bo"
            "nghi dinh ... huong dan luat dat dai" → "dat dai"
            "nghi dinh ... ve dang ky kinh doanh"  → "dang ky kinh doanh"
        """
        import re

        norm = remove_diacritics(title).lower().strip()

        patterns = [
            # "bo luat dan su 2015" → "dan su"
            r'bo luat\s+(.+?)(?:\s+\d{4}|\s*$)',
            # "luat dat dai 2024" → "dat dai"
            r'(?:^|\s)luat\s+(.+?)(?:\s+\d{4}|\s*$)',
            # "nghi dinh ... ve <domain>"
            r'(?:nghi dinh|thong tu).*?\bve\s+(.+?)(?:\s+\d{4}|\s*$)',
        ]

        for pattern in patterns:
            m = re.search(pattern, norm)
            if m:
                domain = m.group(1).strip()
                # Remove trailing document numbers or "so ..." noise
                domain = re.sub(r'\s+so\s+.*$', '', domain)
                domain = re.sub(r'\s*\d+/\d+.*$', '', domain)
                if domain:
                    return domain
        return None

    def category_from_document_title(self, title: str) -> Optional[str]:
        """Determine category_id from a law document's title.

        Extracts the legal domain (e.g. "Dân sự", "Đường bộ") from the title,
        normalizes it, and uses ensure_category() to find or create the category.

        Returns category_id or None if extraction/validation fails.

        Examples:
            "Bộ luật Dân sự 2015"          → category "dan_su"
            "Luật Đường bộ 2024"           → category "duong_bo"
            "Nghị định 102/2024/NĐ-CP ..."  → extracted from title context
        """
        if not title:
            return None

        domain = self._extract_domain_from_title(title)

        if not domain:
            logger.warning(f"Could not extract domain from title: '{title}'")
            return None

        try:
            return self.ensure_category(domain)
        except InvalidCategoryError:
            logger.warning(
                f"Invalid category from title: '{title}' (domain: '{domain}')"
            )
            return None

    def ensure_category(self, raw_name: str, display_name: str = "") -> str:
        """Get or create a category. Returns category_id.

        Validation layers:
        1. Normalize → exact match in DB
        2. Fuzzy match (edit distance ≤ 2)
        3. LLM validation (ask Claude if it's a real legal domain)
        4. Auto-create if validated

        Raises InvalidCategoryError if category is not a valid legal domain.
        """
        name = normalize_category_name(raw_name)

        # 1. Exact match (cache / DB)
        existing = self.get_category_id(name)
        if existing:
            return existing

        # 2. Fuzzy match against existing categories
        fuzzy = self._fuzzy_match_category(name)
        if fuzzy:
            return fuzzy

        # 3. LLM validation — ask if it's a valid legal domain
        suggested = self._llm_validate_category(raw_name)
        if suggested:
            name = suggested
            existing = self.get_category_id(name)
            if existing:
                return existing
            fuzzy = self._fuzzy_match_category(name)
            if fuzzy:
                return fuzzy
        else:
            available = ", ".join(sorted(self._category_id_cache.keys())) or "(chưa có)"
            raise InvalidCategoryError(
                f"'{raw_name}' không phải lĩnh vực pháp luật hợp lệ. "
                f"Các lĩnh vực có sẵn: {available}"
            )

        if not hasattr(self.db, "_write"):
            return ""

        # 5. Auto-create new category
        if not display_name:
            display_name = name.replace("_", " ").title()

        client = self.db._write()
        result = client.table("legal_categories").upsert(
            {
                "name": name,
                "display_name": display_name,
                "description": f"Auto-created from contract type: {raw_name}",
                "is_active": True,
            },
            on_conflict="name",
        ).execute()

        if result.data:
            cat_id = result.data[0]["id"]
            self._category_id_cache[name] = cat_id
            logger.info(f"Auto-created category: {name} ({cat_id})")
            return cat_id
        return ""

    async def run(
        self,
        topic: str = "",
        limit: int = 20,
        trigger_type: str = "manual",
        force: bool = False,
    ) -> PipelineRun:
        """Execute full pipeline.

        Accepts a topic (e.g. "đất đai", "lao động"). The system will:
        1. Search thuvienphapluat.vn for the topic
        2. Crawl discovered documents
        3. Auto-detect category per document from its title
        4. Index articles + generate embeddings
        5. Auto-discover contract templates

        Args:
            topic: Search keyword (e.g. "đất đai", "hôn nhân gia đình")
            limit: Max documents per run
            trigger_type: 'manual' | 'scheduled' | 'forced'
            force: Skip hash comparison, re-crawl everything
        """
        config = CategoryConfig(
            name="auto",
            display_name=topic or "Auto",
            crawl_url="",
            rate_limit_seconds=_DEFAULT_RATE_LIMIT,
            max_pages=_DEFAULT_MAX_PAGES,
        )

        start_time = time.time()
        run = PipelineRun(
            id=str(uuid.uuid4()),
            started_at=datetime.now(),
            trigger_type=trigger_type,
        )

        try:
            logger.info(f"Pipeline: '{topic}' (trigger={trigger_type}, force={force})")

            # Phase 1: Discovery — search thuvienphapluat.vn
            logger.info(f"Phase 1: Searching thuvienphapluat.vn for '{topic}'...")
            discovered = await self.crawler.search_documents(topic, limit=limit)
            crawl_urls = [d["url"] for d in discovered]
            registry_entries = []

            if crawl_urls:
                logger.info(f"  Found {len(crawl_urls)} documents")
            else:
                logger.warning(f"  No documents found for '{topic}'")

            run.documents_found = len(crawl_urls)

            # Phase 2: Crawl (incremental)
            logger.info("Phase 2: Crawling...")
            crawl_results = []
            registry_map = {e["url"]: e for e in registry_entries} if registry_entries else {}

            for url in crawl_urls:
                try:
                    result = await self.crawl_document(url, config)
                    if not result:
                        continue

                    # Incremental: compare content hash
                    registry_entry = registry_map.get(url)
                    if not force and registry_entry:
                        old_hash = registry_entry.get("last_content_hash", "")
                        if old_hash and old_hash == result.content_hash:
                            run.documents_skipped += 1
                            logger.info(f"  Skipped (unchanged): {result.title[:50]}")
                            # Update checked_at
                            if registry_entry.get("id"):
                                self.db.update_registry_hash(
                                    registry_entry["id"], result.content_hash
                                )
                            continue

                    # Update registry with new hash
                    if registry_entry and registry_entry.get("id"):
                        self.db.update_registry_hash(
                            registry_entry["id"], result.content_hash
                        )

                    # Also check DB-level hash
                    existing = self.db.get_document_by_hash(result.content_hash)
                    if existing and not force:
                        result.is_new = False
                        run.documents_skipped += 1
                        logger.info(f"  Skipped (DB hash match): {result.title[:50]}")
                    else:
                        crawl_results.append(result)
                        run.documents_new += 1
                        logger.info(f"  Crawled: {result.title[:50]}")

                except Exception as e:
                    logger.error(f"  Error crawling {url}: {e}")

                # Rate limiting
                await asyncio.sleep(
                    config.rate_limit_seconds + __import__("random").uniform(0, 2)
                )

            # Phase 3: Index
            logger.info("Phase 3: Indexing...")
            total_articles = 0
            for result in crawl_results:
                try:
                    count = self.index_document(result, config)
                    total_articles += count
                    logger.info(
                        f"  Indexed: {result.title[:50]} ({count} articles)"
                    )
                except Exception as e:
                    logger.error(f"  Error indexing {result.title[:50]}: {e}")

            run.articles_indexed = total_articles
            run.embeddings_generated = total_articles

            # Phase 4: Validate + update category counts
            logger.info("Phase 4: Validation...")
            valid = self.validate(run)
            if valid:
                run.status = PipelineStatus.COMPLETED
                logger.info(
                    f"Pipeline completed: {run.documents_new} new, "
                    f"{run.documents_skipped} skipped, {run.articles_indexed} articles"
                )
            else:
                run.status = PipelineStatus.FAILED
                logger.warning("Pipeline validation failed")

            # Collect all categories that were touched during indexing
            touched_categories = set(self._category_id_cache.keys())

            # Update category counts for all touched categories
            if hasattr(self.db, "update_category_counts"):
                for cat_name in touched_categories:
                    cat_id = self.get_category_id(cat_name)
                    if cat_id:
                        try:
                            self.db.update_category_counts(cat_id)
                        except Exception as e:
                            logger.warning(f"Failed to update counts for {cat_name}: {e}")

            # Phase 5: Auto-discover contract templates for all touched categories
            logger.info("Phase 5: Auto-discover contract templates...")
            total_templates = 0
            for cat_name in touched_categories:
                try:
                    n = self.seed_templates_for_category(cat_name, cache_articles=True)
                    if n:
                        logger.info(f"  {cat_name}: {n} templates discovered")
                        total_templates += n
                except Exception as e:
                    logger.warning(f"Template discovery failed for {cat_name}: {e}")
            logger.info(f"  Total: {total_templates} templates")

        except Exception as e:
            run.status = PipelineStatus.FAILED
            run.error_message = str(e)
            logger.error(f"Pipeline failed: {e}")

        run.completed_at = datetime.now()
        run.duration_seconds = time.time() - start_time
        return run

    def _get_document_registry(self, category: str) -> List[dict]:
        """Load active registry entries for a category from DB."""
        if not hasattr(self.db, "get_document_registry"):
            return []
        try:
            return self.db.get_document_registry(category)
        except Exception as e:
            logger.warning(f"Failed to load document registry: {e}")
            return []

    @staticmethod
    def _compute_normalized_hash(html_content: str) -> str:
        """Compute SHA-256 of normalized content.

        Steps:
        1. Parse with BeautifulSoup
        2. Remove: script, style, noscript, iframe
        3. Extract: div.content1 or div.toanvancontent
        4. Get text, collapse whitespace
        5. SHA-256 hash
        """
        try:
            from bs4 import BeautifulSoup
            import re

            soup = BeautifulSoup(html_content, "html.parser")

            # Remove noise elements
            for tag in soup.find_all(["script", "style", "noscript", "iframe"]):
                tag.decompose()

            # Extract main content
            content_elem = (
                soup.find("div", class_="content1")
                or soup.find("div", class_="toanvancontent")
                or soup.find("article")
                or soup
            )

            text = content_elem.get_text()
            # Collapse whitespace
            text = re.sub(r"\s+", " ", text).strip()

            return hashlib.sha256(text.encode("utf-8")).hexdigest()
        except Exception:
            # Fallback to raw hash
            return hashlib.sha256(html_content.encode("utf-8")).hexdigest()

    async def crawl_document(
        self, url: str, config: CategoryConfig
    ) -> Optional[CrawlResult]:
        """Phase 2: Crawl a single document."""
        html = await self.crawler.crawl_with_stealth(url)
        if not html:
            return None

        content_hash = CrawlerService.compute_content_hash(html)
        parsed = self.crawler._parse_document(url, html)
        if not parsed:
            return None

        # Parse articles from HTML
        articles = self.indexer.parse_html_articles(html, "temp")

        return CrawlResult(
            url=url,
            document_number=parsed.document_number,
            title=parsed.title,
            document_type=parsed.document_type,
            effective_date=parsed.effective_date,
            issuing_authority=parsed.issuing_authority,
            html_content=html,
            content_hash=content_hash,
            articles_count=len(articles),
        )

    def index_document(self, result: CrawlResult, config: CategoryConfig) -> int:
        """Phase 3: Index document into DB + generate embeddings."""
        # Auto-detect category from document title (not from user input)
        category_id = self.category_from_document_title(result.title)
        if category_id:
            logger.info(f"  Category auto-detected from title: '{result.title[:60]}'")
        else:
            logger.warning(f"  Could not auto-detect category from title: '{result.title[:60]}'")

        # Insert document
        doc_data = {
            "document_type": result.document_type,
            "document_number": result.document_number,
            "title": result.title,
            "effective_date": result.effective_date,
            "issuing_authority": result.issuing_authority,
            "source_url": result.url,
            "content_hash": result.content_hash,
            "status": result.status,
        }
        if category_id:
            doc_data["category_id"] = category_id
        doc_id = self.db.upsert_document(doc_data)

        # Parse articles
        articles = self.indexer.parse_html_articles(result.html_content, doc_id)

        # Deduplicate by article_number — keep the longest content
        seen = {}
        for a in articles:
            key = a.article_number
            if key not in seen or len(a.content) > len(seen[key].content):
                seen[key] = a
        articles = list(seen.values())

        # Convert to dicts for embedding
        article_dicts = []
        for a in articles:
            article_dicts.append(
                {
                    "id": a.id,
                    "document_id": doc_id,
                    "article_number": a.article_number,
                    "title": a.title,
                    "content": a.content,
                    "chapter": a.chapter,
                    "chunk_index": 0,
                }
            )

        # Embed and store
        if article_dicts:
            count = self.embedding.embed_and_store(self.db, article_dicts)
            return count

        return 0

    def validate(self, pipeline_run: PipelineRun) -> bool:
        """Phase 4: Validate pipeline results."""
        if pipeline_run.documents_new == 0:
            logger.info("No new documents to validate")
            return True

        if pipeline_run.articles_indexed == 0:
            logger.warning("No articles indexed")
            return False

        return True

    def get_category_config(self, name: str) -> Optional[CategoryConfig]:
        """Get crawl configuration for a category from DB."""
        if not hasattr(self.db, "_read"):
            return None

        client = self.db._read()
        result = (
            client.table("legal_categories")
            .select("name, display_name, description, crawl_url")
            .eq("name", name)
            .eq("is_active", True)
            .limit(1)
            .execute()
        )
        if not result.data:
            return None

        cat = result.data[0]

        # Load document URLs from registry
        registry = self._get_document_registry(name)
        doc_urls = [e["url"] for e in registry] if registry else []

        return CategoryConfig(
            name=cat["name"],
            display_name=cat.get("display_name", name),
            description=cat.get("description", ""),
            crawl_url=cat.get("crawl_url", ""),
            document_urls=doc_urls,
            rate_limit_seconds=_DEFAULT_RATE_LIMIT,
            max_pages=_DEFAULT_MAX_PAGES,
        )

    def seed_templates_for_category(self, category: str, cache_articles: bool = False) -> int:
        """Auto-discover and seed contract templates for a category.

        Uses LLM to analyze crawled articles and determine what contract types
        can be created. No hardcoded template definitions — everything is
        discovered from the actual legal content.

        Steps:
          1. Load articles for the category from DB
          2. LLM Step 1: Discover contract types from articles
          3. For each type, run search queries → cache articles
          4. LLM Step 2: Generate required_fields from cached articles
          5. Upsert each template to Supabase

        Returns count of templates seeded.
        """
        if not hasattr(self.db, "upsert_contract_template"):
            return 0

        category_id = self.get_category_id(category)
        if not category_id:
            return 0

        # Load articles for LLM context
        if not hasattr(self.db, "get_articles_by_category"):
            return 0

        articles = self.db.get_articles_by_category(category, limit=80)
        if not articles:
            logger.warning(f"No articles found for category {category}, skipping template discovery")
            return 0

        # LLM Step 1: Discover contract types
        discovered = self._discover_contract_types(category, articles)
        if not discovered:
            logger.warning(f"LLM could not discover contract types for {category}")
            return 0

        logger.info(f"Discovered {len(discovered)} contract types for {category}")

        count = 0
        for tmpl in discovered:
            tmpl_data = {
                "contract_type": tmpl["contract_type"],
                "display_name": tmpl["display_name"],
                "search_queries": tmpl.get("search_queries", []),
                "category_id": category_id,
            }

            # Cache articles via search queries
            cached = []
            if cache_articles and hasattr(self.db, "search_articles") and tmpl_data["search_queries"]:
                try:
                    cached = self._run_template_queries(tmpl_data["search_queries"])
                    tmpl_data["cached_articles"] = cached
                    tmpl_data["cached_at"] = datetime.now().isoformat()
                    logger.info(
                        f"  Cached {len(cached)} articles for {tmpl['contract_type']}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to cache articles for {tmpl['contract_type']}: {e}")

            # LLM Step 2: Generate required_fields from cached articles
            if cached:
                try:
                    required_fields = self._generate_required_fields(tmpl, cached)
                    if required_fields:
                        tmpl_data["required_fields"] = required_fields
                        logger.info(
                            f"  Generated {len(required_fields.get('fields', []))} fields for {tmpl['contract_type']}"
                        )
                except Exception as e:
                    logger.warning(f"Failed to generate fields for {tmpl['contract_type']}: {e}")

            try:
                self.db.upsert_contract_template(tmpl_data)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to seed template {tmpl['contract_type']}: {e}")

        logger.info(f"Seeded {count} templates for {category}")
        return count

    def _discover_contract_types(self, category: str, articles: list) -> list[dict] | None:
        """Use LLM to discover what contract types can be created from articles.

        Args:
            category: Category slug (e.g. "dat_dai")
            articles: List of articles with article_number, title, content, document_title

        Returns:
            List of dicts: [{contract_type, display_name, search_queries}, ...]
        """
        from legal_chatbot.utils.llm import call_llm_json

        # Build article summaries — titles + first 200 chars of content
        article_summaries = []
        seen = set()
        for a in articles:
            key = (a.get("article_number"), a.get("document_title"))
            if key in seen:
                continue
            seen.add(key)
            summary = f"- Điều {a.get('article_number', '?')} ({a.get('document_title', '')}): {a.get('title', '')} — {a.get('content', '')[:200]}"
            article_summaries.append(summary)
            if len(article_summaries) >= 40:
                break

        articles_text = "\n".join(article_summaries)

        # Collect unique document titles
        doc_titles = list({a.get("document_title", "") for a in articles if a.get("document_title")})
        docs_text = "\n".join(f"- {t}" for t in doc_titles)

        prompt = f"""Bạn là chuyên gia pháp luật Việt Nam. Dựa trên các điều luật đã crawl bên dưới, hãy xác định các LOẠI HỢP ĐỒNG có thể tạo được.

VĂN BẢN PHÁP LUẬT:
{docs_text}

MỘT SỐ ĐIỀU LUẬT TIÊU BIỂU:
{articles_text}

YÊU CẦU: Xác định các loại hợp đồng phổ biến có thể tạo dựa trên các điều luật trên.
Trả về JSON array (KHÔNG có text nào khác ngoài JSON):
[
  {{
    "contract_type": "slug_tieng_viet_khong_dau",
    "display_name": "Tên hợp đồng đầy đủ tiếng Việt có dấu",
    "search_queries": ["truy vấn tìm kiếm 1", "truy vấn tìm kiếm 2", "truy vấn 3"]
  }}
]

QUY TẮC:
1. contract_type phải là slug tiếng Việt không dấu, snake_case (vd: mua_ban_dat, cho_thue_nha, hop_dong_lao_dong)
2. display_name phải có dấu tiếng Việt đầy đủ (vd: "Hợp đồng mua bán đất")
3. search_queries là 3-5 câu truy vấn tìm kiếm để tìm điều luật liên quan cho loại hợp đồng đó
4. Chỉ liệt kê các loại hợp đồng mà điều luật đã crawl CÓ ĐỦ cơ sở pháp lý để tạo
5. Không bịa ra loại hợp đồng nếu không có điều luật liên quan
6. Thường mỗi lĩnh vực pháp luật có 1-4 loại hợp đồng phổ biến
7. Chỉ trả về JSON array, không giải thích"""

        try:
            discovered = call_llm_json(
                messages=[
                    {"role": "system", "content": "Bạn là API trả về JSON. Chỉ trả về JSON hợp lệ, không có text khác."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=2000,
            )

            if not isinstance(discovered, list) or not discovered:
                logger.warning(f"LLM returned invalid discovery result for {category}")
                return None

            # Validate each entry has required keys
            valid = []
            for entry in discovered:
                if entry.get("contract_type") and entry.get("display_name"):
                    valid.append({
                        "contract_type": entry["contract_type"],
                        "display_name": entry["display_name"],
                        "search_queries": entry.get("search_queries", []),
                    })

            return valid if valid else None

        except Exception as e:
            logger.warning(f"LLM discovery failed for {category}: {e}")
            return None

    def _generate_required_fields(self, template: dict, cached_articles: list) -> dict | None:
        """Use LLM to generate required_fields JSONB from cached articles.

        Analyzes the legal articles and generates:
        - fields: list of {name, label, required} for the contract form
        - field_groups: prefix-based grouping for HTML preview sections
        - common_groups: shared financial/timeline groups
        - legal_refs: specific article references
        - key_terms: important legal terms from articles
        """
        from legal_chatbot.utils.llm import call_llm_json

        # Build article summaries for LLM context
        article_texts = []
        for a in cached_articles[:15]:  # Limit to top 15 most relevant
            text = f"Điều {a.get('article_number', '?')} ({a.get('document_title', '')}): {a.get('content', '')[:500]}"
            article_texts.append(text)

        articles_context = "\n\n".join(article_texts)

        prompt = f"""Bạn là chuyên gia pháp luật Việt Nam. Dựa trên các điều luật bên dưới, hãy tạo danh sách các trường thông tin cần thiết cho "{template['display_name']}".

ĐIỀU LUẬT THAM KHẢO:
{articles_context}

YÊU CẦU: Trả về JSON với cấu trúc sau (KHÔNG có text nào khác ngoài JSON):
{{
  "fields": [
    {{"name": "field_name_snake_case", "label": "Nhãn tiếng Việt có dấu", "required": true/false}}
  ],
  "field_groups": [
    {{"prefix": "party_a_prefix_", "key": "section_key", "label": "TÊN NHÓM TIẾNG VIỆT (BÊN A)"}}
  ],
  "common_groups": [
    {{"prefix": "payment_", "key": "tai_chinh", "label": "TÀI CHÍNH"}}
  ],
  "legal_refs": ["Điều X Luật Y"],
  "key_terms": ["Điều kiện quan trọng từ luật"]
}}

QUY TẮC:
1. Mỗi bên (A, B) cần: họ tên, ngày sinh, CCCD, ngày cấp, nơi cấp, địa chỉ, SĐT
2. Prefix field name theo bên: vd landlord_, tenant_, seller_, buyer_, transferor_, transferee_, employer_, employee_
3. Thông tin tài sản/đối tượng: địa chỉ, diện tích, giấy chứng nhận, mô tả
4. Tài chính: giá, đặt cọc, phương thức thanh toán
5. Thời hạn: ngày bắt đầu, ngày kết thúc, thời hạn
6. field_groups gom các fields theo prefix của từng bên và đối tượng
7. common_groups gom fields tài chính, thời hạn
8. Label phải có dấu tiếng Việt đầy đủ
9. Chỉ trả về JSON, không giải thích"""

        try:
            required_fields = call_llm_json(
                messages=[
                    {"role": "system", "content": "Bạn là API trả về JSON. Chỉ trả về JSON hợp lệ, không có text khác."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=4000,
            )

            if not isinstance(required_fields, dict):
                logger.warning(f"LLM returned non-dict for {template['contract_type']}")
                return None

            # Validate structure
            if "fields" not in required_fields or not required_fields["fields"]:
                logger.warning(f"LLM returned empty fields for {template['contract_type']}")
                return None

            return required_fields

        except Exception as e:
            logger.warning(f"LLM generation failed for {template['contract_type']}: {e}")
            return None

    def _run_template_queries(self, queries: list, top_k: int = 10) -> list:
        """Run search queries and return deduplicated results."""
        seen_keys = set()
        results = []

        for query in queries:
            embedding = self.embedding.embed_single(query)
            articles = self.db.search_articles(query_embedding=embedding, top_k=top_k)

            for a in articles:
                key = (a.get("article_number"), a.get("document_title", ""))
                if key not in seen_keys:
                    seen_keys.add(key)
                    results.append({
                        "article_number": a.get("article_number"),
                        "title": a.get("title", ""),
                        "document_title": a.get("document_title", ""),
                        "content": a.get("content", ""),
                        "similarity": round(a.get("similarity", 0), 4),
                    })

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results

    def list_categories(self) -> List[dict]:
        """List all categories from DB."""
        if not hasattr(self.db, "_read"):
            return []
        client = self.db._read()
        result = (
            client.table("legal_categories")
            .select("name, display_name, description, crawl_url, is_active")
            .eq("is_active", True)
            .order("name")
            .execute()
        )
        return result.data
