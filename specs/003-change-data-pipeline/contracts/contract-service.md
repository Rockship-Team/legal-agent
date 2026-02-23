# Contract: Contract Creation Service

**Module**: `legal_chatbot/services/contract.py`

## Interface

```python
class ContractService:
    """DB-only contract creation with pre-configured templates."""

    def __init__(self, db: DatabaseInterface, embedding_service: EmbeddingService):
        """Initialize with database and embedding service."""

    async def check_availability(
        self, contract_type: str
    ) -> DataAvailability:
        """Check if enough data exists to create a contract.

        Args:
            contract_type: User input like 'mua bán đất', 'thuê nhà'

        Returns:
            DataAvailability with:
            - has_data: bool
            - article_count: int
            - available_categories: List[CategoryInfo]
            - available_contract_types: List[str]

        Flow:
        1. Map user input → contract_type slug (mua_ban_dat)
        2. Find matching template in contract_templates table
        3. Check category article_count > 0
        4. Return availability info
        """

    async def load_template(
        self, contract_type: str
    ) -> ContractTemplate:
        """Load contract template config from DB.

        Args:
            contract_type: Slug like 'mua_ban_dat'

        Returns:
            ContractTemplate with search_queries, required_laws, etc.

        Raises:
            ValueError if template not found
        """

    async def search_legal_articles(
        self, template: ContractTemplate
    ) -> List[Article]:
        """Multi-query vector search using template's pre-mapped queries.

        Args:
            template: ContractTemplate with search_queries list

        Returns:
            Merged + deduplicated list of articles from DB

        Flow:
        1. For each query in template.search_queries:
           - Generate embedding
           - Vector search Supabase (top_k=10, threshold=0.3)
        2. Merge all results
        3. Dedup by article ID (keep highest similarity score)
        4. Filter: status = 'active'
        5. Sort by relevance
        """

    async def validate_articles(
        self, articles: List[Article], template: ContractTemplate
    ) -> Tuple[bool, str]:
        """Validate if enough articles found for reliable contract.

        Returns:
            (is_sufficient, message)
            - (True, "OK") if len(articles) >= template.min_articles
            - (False, warning_message) otherwise
        """

    async def list_available_contracts(self) -> List[CategoryInfo]:
        """List all categories with their available contract types.

        Returns:
            List of CategoryInfo with contract_types populated
        """

    def map_user_input_to_type(self, user_input: str) -> Optional[str]:
        """Map natural language input to contract_type slug.

        Examples:
            'mua bán đất' → 'mua_ban_dat'
            'thuê nhà' → 'cho_thue_nha'
            'hợp đồng lao động' → 'hop_dong_lao_dong'
            'vay tiền' → 'vay_tien'

        Returns:
            contract_type slug or None if no match
        """
```

## Dependencies

- `db/supabase.py` (contract_templates CRUD, vector search)
- `services/embedding.py` (generate query embeddings)
- `models/contract.py` (ContractTemplate, DataAvailability, CategoryInfo)

## Error Handling

| Scenario | Behavior |
|----------|----------|
| Category not crawled | Return `DataAvailability(has_data=False)` with list of available |
| Template not found | Return `DataAvailability(has_data=False)` |
| Articles < min_articles | Return warning, allow user to proceed or cancel |
| DB connection error | Raise, let caller handle |
