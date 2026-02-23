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
from legal_chatbot.utils.config import get_settings
from legal_chatbot.utils.vietnamese import (
    edit_distance,
    normalize_category_name,
    remove_diacritics,
)

logger = logging.getLogger(__name__)

# Transaction verbs — stripped when comparing category *subjects*
_TRANSACTION_VERBS = {
    "mua", "ban", "thue", "cho", "vay", "muon", "chuyen", "nhuong", "gop",
}

# Known legal domain keywords (no diacritics) for fast validation
_LEGAL_KEYWORDS = (
    _TRANSACTION_VERBS
    | {
        # Assets / objects
        "dat", "nha", "xe", "may", "phong", "can", "ho", "oto",
        # Legal domains
        "lao", "dong", "dan", "su", "hinh", "thuong", "mai",
        "doanh", "nghiep", "dau", "tu", "tai", "chinh",
        # Contract-related
        "hop", "dong", "dich", "vu", "uy", "quyen", "bao", "hiem",
        # Property / finance
        "bat", "san", "tien", "von",
        # Family / inheritance
        "hon", "nhan", "gia", "dinh", "thua", "ke",
        # General legal
        "luat", "phap", "nghia", "kinh",
    }
)


class InvalidCategoryError(ValueError):
    """Raised when a category name is not a valid legal domain."""
    pass


# Contract template configurations (search queries per contract type)
CONTRACT_TEMPLATES = {
    "dat_dai": [
        {
            "contract_type": "mua_ban_dat",
            "display_name": "Hợp đồng mua bán đất",
            "search_queries": [
                "điều kiện chuyển nhượng quyền sử dụng đất",
                "hợp đồng chuyển nhượng quyền sử dụng đất",
                "quyền nghĩa vụ bên chuyển nhượng bên nhận",
                "giá đất thanh toán chuyển nhượng",
                "thủ tục đăng ký biến động đất đai",
            ],
            "required_laws": ["Luật Đất đai 2024", "Bộ luật Dân sự 2015"],
            "min_articles": 10,
        },
        {
            "contract_type": "cho_thue_dat",
            "display_name": "Hợp đồng cho thuê đất",
            "search_queries": [
                "cho thuê quyền sử dụng đất",
                "hợp đồng thuê đất điều kiện",
                "quyền nghĩa vụ bên cho thuê bên thuê đất",
            ],
            "required_laws": ["Luật Đất đai 2024", "Bộ luật Dân sự 2015"],
            "min_articles": 8,
        },
        {
            "contract_type": "chuyen_nhuong_dat",
            "display_name": "Hợp đồng chuyển nhượng QSDĐ",
            "search_queries": [
                "chuyển nhượng quyền sử dụng đất",
                "điều kiện chuyển nhượng đất",
                "thủ tục chuyển nhượng đất đai",
            ],
            "required_laws": ["Luật Đất đai 2024", "Bộ luật Dân sự 2015"],
            "min_articles": 10,
        },
    ],
    "nha_o": [
        {
            "contract_type": "cho_thue_nha",
            "display_name": "Hợp đồng thuê nhà ở",
            "search_queries": [
                "hợp đồng thuê nhà ở",
                "quyền nghĩa vụ bên cho thuê bên thuê nhà",
                "giá thuê phương thức thanh toán nhà",
                "chấm dứt hợp đồng thuê nhà",
            ],
            "required_laws": ["Luật Nhà ở 2023", "Bộ luật Dân sự 2015"],
            "min_articles": 8,
        },
        {
            "contract_type": "mua_ban_nha",
            "display_name": "Hợp đồng mua bán nhà ở",
            "search_queries": [
                "mua bán nhà ở điều kiện",
                "hợp đồng mua bán nhà",
                "quyền sở hữu nhà ở chuyển nhượng",
            ],
            "required_laws": ["Luật Nhà ở 2023", "Bộ luật Dân sự 2015"],
            "min_articles": 8,
        },
    ],
    "lao_dong": [
        {
            "contract_type": "hop_dong_lao_dong",
            "display_name": "Hợp đồng lao động",
            "search_queries": [
                "hợp đồng lao động nội dung hình thức",
                "quyền nghĩa vụ người lao động",
                "quyền nghĩa vụ người sử dụng lao động",
                "thời giờ làm việc nghỉ ngơi",
                "tiền lương chế độ",
            ],
            "required_laws": ["Bộ luật Lao động 2019"],
            "min_articles": 10,
        },
        {
            "contract_type": "thu_viec",
            "display_name": "Hợp đồng thử việc",
            "search_queries": [
                "thử việc thời gian điều kiện",
                "tiền lương thử việc",
                "kết thúc thử việc",
            ],
            "required_laws": ["Bộ luật Lao động 2019"],
            "min_articles": 5,
        },
    ],
    "dan_su": [
        {
            "contract_type": "vay_tien",
            "display_name": "Hợp đồng vay tiền",
            "search_queries": [
                "hợp đồng vay tài sản",
                "lãi suất vay quy định",
                "nghĩa vụ trả nợ bên vay",
                "thời hạn vay",
            ],
            "required_laws": ["Bộ luật Dân sự 2015"],
            "min_articles": 5,
        },
        {
            "contract_type": "uy_quyen",
            "display_name": "Hợp đồng ủy quyền",
            "search_queries": [
                "hợp đồng ủy quyền",
                "phạm vi ủy quyền",
                "nghĩa vụ bên ủy quyền bên được ủy quyền",
            ],
            "required_laws": ["Bộ luật Dân sự 2015"],
            "min_articles": 5,
        },
        {
            "contract_type": "dich_vu",
            "display_name": "Hợp đồng dịch vụ",
            "search_queries": [
                "hợp đồng dịch vụ",
                "quyền nghĩa vụ bên cung ứng bên sử dụng dịch vụ",
                "giá dịch vụ thanh toán",
            ],
            "required_laws": ["Bộ luật Dân sự 2015"],
            "min_articles": 5,
        },
    ],
}


# Category configurations
CATEGORIES = {
    "dat_dai": CategoryConfig(
        name="dat_dai",
        display_name="Đất đai",
        description="Luật Đất đai, nghị định hướng dẫn về quyền sử dụng đất, chuyển nhượng, thu hồi đất",
        crawl_url="https://thuvienphapluat.vn/van-ban/Bat-dong-san/",
        document_urls=[
            "https://thuvienphapluat.vn/van-ban/Bat-dong-san/Luat-Dat-dai-2024-31-2024-QH15-523642.aspx",
            "https://thuvienphapluat.vn/van-ban/Bat-dong-san/Nghi-dinh-102-2024-ND-CP-huong-dan-Luat-Dat-dai-603982.aspx",
            "https://thuvienphapluat.vn/van-ban/Bat-dong-san/Nghi-dinh-101-2024-ND-CP-dang-ky-cap-giay-chung-nhan-quyen-su-dung-dat-tai-san-gan-lien-dat-613131.aspx",
        ],
        max_pages=20,
        rate_limit_seconds=4.0,
    ),
    "nha_o": CategoryConfig(
        name="nha_o",
        display_name="Nhà ở",
        description="Luật Nhà ở, nghị định về mua bán, cho thuê, quản lý nhà ở",
        crawl_url="https://thuvienphapluat.vn/van-ban/Bat-dong-san/",
        document_urls=[],
        max_pages=10,
        rate_limit_seconds=4.0,
    ),
    "lao_dong": CategoryConfig(
        name="lao_dong",
        display_name="Lao động",
        description="Bộ luật Lao động, nghị định về hợp đồng lao động, tiền lương, bảo hiểm",
        crawl_url="https://thuvienphapluat.vn/van-ban/Lao-dong-Tien-luong/",
        document_urls=[],
        max_pages=10,
        rate_limit_seconds=4.0,
    ),
    "dan_su": CategoryConfig(
        name="dan_su",
        display_name="Dân sự",
        description="Bộ luật Dân sự, nghị định về hợp đồng, tài sản, thừa kế, bồi thường thiệt hại",
        crawl_url="https://thuvienphapluat.vn/van-ban/Quyen-dan-su/",
        document_urls=[],
        max_pages=10,
        rate_limit_seconds=4.0,
    ),
    "doanh_nghiep": CategoryConfig(
        name="doanh_nghiep",
        display_name="Doanh nghiệp",
        description="Luật Doanh nghiệp, luật Đầu tư, nghị định về đăng ký kinh doanh",
        crawl_url="https://thuvienphapluat.vn/van-ban/Doanh-nghiep/",
        document_urls=[],
        max_pages=10,
        rate_limit_seconds=4.0,
    ),
    "thuong_mai": CategoryConfig(
        name="thuong_mai",
        display_name="Thương mại",
        description="Luật Thương mại, nghị định về mua bán hàng hóa, dịch vụ thương mại",
        crawl_url="https://thuvienphapluat.vn/van-ban/Thuong-mai/",
        document_urls=[],
        max_pages=10,
        rate_limit_seconds=4.0,
    ),
}

# URL pattern → category name mapping (for fix-data migration)
URL_CATEGORY_MAP = {
    "Bat-dong-san": "dat_dai",
    "Lao-dong": "lao_dong",
    "Quyen-dan-su": "dan_su",
    "Doanh-nghiep": "doanh_nghiep",
    "Thuong-mai": "thuong_mai",
}


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
        """Sync CATEGORIES dict into legal_categories table. Returns count synced."""
        if not hasattr(self.db, "_write"):
            logger.warning("sync_categories requires Supabase backend")
            return 0

        client = self.db._write()
        count = 0
        for name, config in CATEGORIES.items():
            data = {
                "name": name,
                "display_name": config.display_name,
                "description": config.description,
                "crawl_url": config.crawl_url,
                "is_active": True,
            }
            result = client.table("legal_categories").upsert(
                data, on_conflict="name"
            ).execute()
            if result.data:
                self._category_id_cache[name] = result.data[0]["id"]
                count += 1

        logger.info(f"Synced {count} categories to legal_categories")
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

    def _subject_match_category(self, name: str) -> Optional[str]:
        """Match by domain subject after stripping transaction verbs.

        "thue_xe" and "mua_xe" both have subject {"xe"} → same category.
        "thue_nha" has subject {"nha"} which overlaps with "nha_o" → match.
        """
        if not hasattr(self.db, "_read"):
            return None

        parts = set(name.split("_"))
        subject = parts - _TRANSACTION_VERBS
        if not subject:
            return None

        client = self.db._read()
        cats = client.table("legal_categories").select("id, name").execute()
        if not cats.data:
            return None

        for cat in cats.data:
            cat_parts = set(cat["name"].split("_"))
            cat_subject = cat_parts - _TRANSACTION_VERBS
            # Match if subjects share at least one non-verb word
            if subject & cat_subject:
                self._category_id_cache[cat["name"]] = cat["id"]
                self._category_id_cache[name] = cat["id"]
                logger.info(
                    f"Subject matched category: '{name}' → '{cat['name']}' "
                    f"(shared: {subject & cat_subject})"
                )
                return cat["id"]
        return None

    @staticmethod
    def _has_legal_keywords(name: str) -> bool:
        """Fast check: does normalized name contain any known legal keywords?"""
        parts = name.split("_")
        return any(part in _LEGAL_KEYWORDS for part in parts)

    @staticmethod
    def _llm_validate_category(raw_name: str) -> Optional[str]:
        """Ask LLM whether this is a valid Vietnamese legal category.

        Returns a suggested category name if valid, None if not.
        """
        try:
            from groq import Groq

            settings = get_settings()
            if not settings.groq_api_key:
                return None

            client = Groq(api_key=settings.groq_api_key)
            response = client.chat.completions.create(
                model=settings.llm_model,
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
            )

            answer = (response.choices[0].message.content or "").strip()
            if answer.upper().startswith("YES|"):
                suggested = answer.split("|", 1)[1].strip()
                # Normalize the LLM suggestion too
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
        3. Subject match (strip transaction verbs, compare domain words)
        4. Keyword validation (known legal terms)
        5. LLM fallback (ask Groq if it's a real legal domain)
        6. Auto-create if validated

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

        # 3. Subject match — "thue_xe" matches "mua_xe" (same subject "xe")
        subject = self._subject_match_category(name)
        if subject:
            return subject

        # 4. Validate before auto-creating
        if not self._has_legal_keywords(name):
            # 5. LLM fallback — maybe it's a valid domain we don't have keywords for
            suggested = self._llm_validate_category(raw_name)
            if suggested:
                # LLM said it's valid, use its suggested name
                name = suggested
                # Check again if this suggested name already exists
                existing = self.get_category_id(name)
                if existing:
                    return existing
                fuzzy = self._fuzzy_match_category(name)
                if fuzzy:
                    return fuzzy
            else:
                raise InvalidCategoryError(
                    f"'{raw_name}' không phải lĩnh vực pháp luật hợp lệ. "
                    f"Các lĩnh vực có sẵn: {', '.join(sorted(CATEGORIES.keys()))}"
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
        category: str,
        limit: int = 50,
        trigger_type: str = "manual",
        force: bool = False,
    ) -> PipelineRun:
        """Execute full pipeline for a category.

        Supports incremental crawl via document_registry + content hash comparison.

        Args:
            category: Category name (e.g. 'dat_dai')
            limit: Max documents per run
            trigger_type: 'manual' | 'scheduled' | 'forced'
            force: Skip hash comparison, re-crawl everything

        Phases:
        1. DISCOVERY: Load URLs from document_registry (or fallback to hardcoded)
        2. CRAWL: Fetch, hash compare, skip unchanged
        3. INDEX: Store in DB + generate embeddings
        4. VALIDATE: Verify data integrity + update category counts
        """
        config = self.get_category_config(category)
        if not config:
            raise ValueError(f"Unknown category: {category}")

        start_time = time.time()
        run = PipelineRun(
            id=str(uuid.uuid4()),
            started_at=datetime.now(),
            trigger_type=trigger_type,
        )

        try:
            logger.info(f"Pipeline: {config.display_name} (trigger={trigger_type}, force={force})")

            # Phase 1: Discovery — load from document_registry or fallback
            logger.info("Phase 1: Discovery...")
            registry_entries = self._get_document_registry(category)
            if registry_entries:
                urls = [e["url"] for e in registry_entries[:limit]]
                logger.info(f"  Loaded {len(urls)} URLs from document_registry")
            else:
                urls = config.document_urls[:limit]
                logger.info(f"  Fallback to hardcoded URLs: {len(urls)}")

            run.documents_found = len(urls)

            # Phase 2: Crawl (incremental)
            logger.info("Phase 2: Crawling...")
            crawl_results = []
            registry_map = {e["url"]: e for e in registry_entries} if registry_entries else {}

            for url in urls:
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

            # Resolve category_id (auto-created during indexing from doc titles)
            category_id = self.get_category_id(category)
            run.category_id = category_id

            # Update category counts
            if category_id and hasattr(self.db, "update_category_counts"):
                try:
                    self.db.update_category_counts(category_id)
                except Exception as e:
                    logger.warning(f"Failed to update category counts: {e}")

            # Phase 5: Auto-seed registry + templates (with cached search results)
            logger.info("Phase 5: Auto-seed registry & templates...")
            try:
                reg_count = self.seed_registry_for_category(category)
                tmpl_count = self.seed_templates_for_category(
                    category, cache_articles=True
                )
                logger.info(
                    f"  Seeded: {reg_count} registry entries, {tmpl_count} templates (with cached articles)"
                )
            except Exception as e:
                logger.warning(f"Auto-seed failed (non-critical): {e}")

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
        """Get crawl configuration for a category."""
        return CATEGORIES.get(name)

    def seed_templates_for_category(self, category: str, cache_articles: bool = False) -> int:
        """Seed contract templates for a category. Returns count seeded.

        If cache_articles=True, also runs template search queries and caches
        the matching articles in the template's cached_articles JSONB column.
        This requires the embedding model to be loaded (self.embedding).
        """
        if not hasattr(self.db, "upsert_contract_template"):
            return 0

        templates = CONTRACT_TEMPLATES.get(category, [])
        if not templates:
            return 0

        category_id = self.get_category_id(category)
        if not category_id:
            return 0

        count = 0
        for tmpl in templates:
            tmpl_data = {**tmpl, "category_id": category_id}

            # Pre-compute search results if requested
            if cache_articles and hasattr(self.db, "search_articles"):
                try:
                    cached = self._run_template_queries(tmpl.get("search_queries", []))
                    tmpl_data["cached_articles"] = cached
                    tmpl_data["cached_at"] = datetime.now().isoformat()
                    logger.info(
                        f"  Cached {len(cached)} articles for {tmpl['contract_type']}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to cache articles for {tmpl['contract_type']}: {e}")

            try:
                self.db.upsert_contract_template(tmpl_data)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to seed template {tmpl['contract_type']}: {e}")

        logger.info(f"Seeded {count} templates for {category}")
        return count

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

    def seed_registry_for_category(self, category: str) -> int:
        """Seed document registry entries for a category. Returns count seeded."""
        if not hasattr(self.db, "upsert_registry_entry"):
            return 0

        config = CATEGORIES.get(category)
        if not config or not config.document_urls:
            return 0

        category_id = self.get_category_id(category)
        if not category_id:
            return 0

        count = 0
        for i, url in enumerate(config.document_urls):
            entry = {
                "category_id": category_id,
                "url": url,
                "title": f"{config.display_name} - Doc {i + 1}",
                "role": "primary" if i == 0 else "related",
                "priority": i + 1,
            }
            try:
                self.db.upsert_registry_entry(entry)
                count += 1
            except Exception as e:
                logger.warning(f"Failed to seed registry entry {url}: {e}")

        logger.info(f"Seeded {count} registry entries for {category}")
        return count

    @staticmethod
    def list_categories() -> List[CategoryConfig]:
        """List all available categories."""
        return list(CATEGORIES.values())
