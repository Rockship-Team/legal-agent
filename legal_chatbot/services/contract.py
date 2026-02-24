"""Contract creation service — DB-only, template-based."""

import logging
from typing import List, Optional, Tuple

from legal_chatbot.models.contract import (
    CategoryInfo,
    ContractTemplate,
    DataAvailability,
)
from legal_chatbot.utils.config import get_settings

logger = logging.getLogger(__name__)

# Map natural language input to contract_type slug
INPUT_TO_TYPE = {
    "mua bán đất": "mua_ban_dat",
    "mua đất": "mua_ban_dat",
    "bán đất": "mua_ban_dat",
    "cho thuê đất": "cho_thue_dat",
    "thuê đất": "cho_thue_dat",
    "chuyển nhượng đất": "chuyen_nhuong_dat",
    "chuyển nhượng quyền sử dụng đất": "chuyen_nhuong_dat",
    "thuê nhà": "cho_thue_nha",
    "cho thuê nhà": "cho_thue_nha",
    "mua bán nhà": "mua_ban_nha",
    "mua nhà": "mua_ban_nha",
    "bán nhà": "mua_ban_nha",
    "hợp đồng lao động": "hop_dong_lao_dong",
    "lao động": "hop_dong_lao_dong",
    "thử việc": "thu_viec",
    "vay tiền": "vay_tien",
    "vay": "vay_tien",
    "ủy quyền": "uy_quyen",
    "dịch vụ": "dich_vu",
    "hợp đồng dịch vụ": "dich_vu",
}

# Map English template slugs (legacy) to Vietnamese DB contract_type
SLUG_ALIAS = {
    "rental": "cho_thue_nha",
    "sale_house": "mua_ban_nha",
    "sale_land": "chuyen_nhuong_dat",
    "sale": "mua_ban_tai_san",
    "service": "dich_vu",
    "employment": "hop_dong_lao_dong",
}


class ContractService:
    """DB-only contract creation with pre-configured templates."""

    def __init__(self):
        self._db = None
        self._embedding = None

    @property
    def db(self):
        """Lazy-load database client."""
        if self._db is None:
            from legal_chatbot.db.supabase import get_database
            self._db = get_database()
        return self._db

    @property
    def embedding(self):
        """Lazy-load embedding service."""
        if self._embedding is None:
            from legal_chatbot.services.embedding import EmbeddingService
            self._embedding = EmbeddingService()
        return self._embedding

    def map_user_input_to_type(self, user_input: str) -> Optional[str]:
        """Map natural language input to contract_type slug.

        Examples:
            'mua bán đất' → 'mua_ban_dat'
            'thuê nhà' → 'cho_thue_nha'
            'rental' → 'cho_thue_nha' (via SLUG_ALIAS)
        """
        input_lower = user_input.lower().strip()

        # Check English slug alias first
        if input_lower in SLUG_ALIAS:
            return SLUG_ALIAS[input_lower]

        # Direct match
        if input_lower in INPUT_TO_TYPE:
            return INPUT_TO_TYPE[input_lower]

        # Partial match
        for phrase, slug in INPUT_TO_TYPE.items():
            if phrase in input_lower or input_lower in phrase:
                return slug

        # Try slug format directly
        slug_input = input_lower.replace(" ", "_")

        # Check slug alias for slug format
        if slug_input in SLUG_ALIAS:
            return SLUG_ALIAS[slug_input]

        template = self.db.get_contract_template(slug_input)
        if template:
            return slug_input

        return None

    async def check_availability(self, contract_type: str) -> DataAvailability:
        """Check if enough data exists to create a contract.

        Args:
            contract_type: User input like 'mua bán đất', 'thuê nhà'

        Returns:
            DataAvailability with has_data, available info
        """
        # Map input to slug
        type_slug = self.map_user_input_to_type(contract_type)

        # Get all available info
        all_cats = self.db.get_all_categories_with_stats()
        available_categories = [
            CategoryInfo(
                name=c["name"],
                display_name=c["display_name"],
                article_count=c.get("article_count", 0),
                document_count=c.get("document_count", 0),
            )
            for c in all_cats
            if c.get("article_count", 0) > 0
        ]

        # Get available contract types
        contracts_list = self.db.list_available_contracts()
        available_types = []
        for cat_info in contracts_list:
            for ct in cat_info.get("contract_types", []):
                available_types.append(ct["name"])

        if not type_slug:
            return DataAvailability(
                category=None,
                has_data=False,
                available_categories=available_categories,
                available_contract_types=available_types,
            )

        # Find template
        template = self.db.get_contract_template(type_slug)
        if not template:
            return DataAvailability(
                category=None,
                has_data=False,
                available_categories=available_categories,
                available_contract_types=available_types,
            )

        # Check category has data
        category_id = template.get("category_id")
        cat_data = next(
            (c for c in all_cats if c["id"] == category_id), None
        )

        if not cat_data or cat_data.get("article_count", 0) == 0:
            return DataAvailability(
                category=cat_data["name"] if cat_data else None,
                has_data=False,
                available_categories=available_categories,
                available_contract_types=available_types,
            )

        return DataAvailability(
            category=cat_data["name"],
            has_data=True,
            article_count=cat_data.get("article_count", 0),
            document_count=cat_data.get("document_count", 0),
            available_categories=available_categories,
            available_contract_types=available_types,
        )

    async def load_template(self, contract_type: str) -> ContractTemplate:
        """Load contract template config from DB.

        Args:
            contract_type: Slug like 'mua_ban_dat'

        Raises:
            ValueError if template not found
        """
        template = self.db.get_contract_template(contract_type)
        if not template:
            raise ValueError(f"Template not found: {contract_type}")

        return ContractTemplate(
            id=template.get("id"),
            category_id=template["category_id"],
            contract_type=template["contract_type"],
            display_name=template["display_name"],
            description=template.get("description"),
            search_queries=template.get("search_queries", []),
            required_laws=template.get("required_laws", []),
            min_articles=template.get("min_articles", 5),
            required_fields=template.get("required_fields"),
            article_outline=template.get("article_outline"),
            is_active=template.get("is_active", True),
        )

    async def search_legal_articles(
        self, template: ContractTemplate
    ) -> List[dict]:
        """Multi-query vector search using template's pre-mapped queries.

        For each query in template.search_queries:
        - Generate embedding
        - Vector search Supabase (top_k=10, threshold=0.3)
        Merge + dedup by article ID (keep highest similarity score).
        """
        all_results = {}

        for query_text in template.search_queries:
            try:
                query_embedding = self.embedding.embed_single(query_text)
                articles = self.db.search_articles(
                    query_embedding=query_embedding,
                    top_k=10,
                )
                for article in articles:
                    article_id = article.get("id", "")
                    existing = all_results.get(article_id)
                    if not existing or article.get("similarity", 0) > existing.get("similarity", 0):
                        all_results[article_id] = article
            except Exception as e:
                logger.warning(f"Search failed for query '{query_text}': {e}")

        # Sort by relevance and return
        results = sorted(
            all_results.values(),
            key=lambda x: x.get("similarity", 0),
            reverse=True,
        )
        return results

    async def validate_articles(
        self, articles: List[dict], template: ContractTemplate
    ) -> Tuple[bool, str]:
        """Validate if enough articles found for reliable contract.

        Returns:
            (is_sufficient, message)
        """
        if len(articles) >= template.min_articles:
            return True, "OK"

        return (
            False,
            f"Tìm thấy {len(articles)}/{template.min_articles} điều luật cần thiết. "
            f"Kết quả có thể chưa đầy đủ. Bạn muốn tiếp tục hay dừng lại?",
        )

    async def list_available_contracts(self) -> List[dict]:
        """List all categories with their available contract types."""
        return self.db.list_available_contracts()
