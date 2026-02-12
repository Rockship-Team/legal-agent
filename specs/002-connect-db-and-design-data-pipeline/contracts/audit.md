# Audit Trail Module Contract

## Overview
The Audit module records research results and generated contracts for verification, tracking which law versions were used.

## Interface

### AuditService

```python
# services/audit.py
from typing import List, Optional
from models.audit import ResearchAudit, ContractAudit, LawVersion, ArticleSource

class AuditService:
    """Records and retrieves audit trails for research and contracts."""

    def __init__(self, db: DatabaseInterface):
        self.db = db

    def save_research_audit(self, audit: ResearchAudit) -> str:
        """Save a research audit entry.

        Called after each chat/research response.
        Records: query, sources (articles used), response, law versions.
        Returns audit ID.
        """
        pass

    def save_contract_audit(self, audit: ContractAudit) -> str:
        """Save a contract audit entry.

        Called after each contract generation.
        Records: type, input data, content, legal refs, law versions, PDF path.
        Returns audit ID.
        """
        pass

    def get_research_audit(self, audit_id: str) -> Optional[ResearchAudit]:
        """Get a specific research audit by ID."""
        pass

    def get_contract_audit(self, audit_id: str) -> Optional[ContractAudit]:
        """Get a specific contract audit by ID."""
        pass

    def list_audits(self, limit: int = 20, audit_type: str = "all") -> list[dict]:
        """List recent audit entries.

        audit_type: 'research', 'contract', or 'all'
        Returns combined list sorted by created_at desc.
        """
        pass

    def verify_audit(self, audit_id: str) -> dict:
        """Verify if an audit entry's law versions are still current.

        Checks each law_version against current DB status.
        Returns: {
            "audit_id": str,
            "is_current": bool,
            "outdated_laws": [{doc_number, old_status, new_status}],
            "verified_at": datetime
        }
        """
        pass

    def build_law_versions(self, article_ids: List[str]) -> List[LawVersion]:
        """Build law version list from article IDs.

        Looks up parent documents for each article.
        Returns unique list of LawVersion entries.
        """
        pass
```

## Integration Points

### ChatService Integration

```python
# services/chat.py — addition
async def chat(self, query: str, session_id: str = None) -> ChatResponse:
    # ... existing RAG pipeline ...
    response = await self._generate_response(query, context)

    # NEW: Save research audit
    audit = ResearchAudit(
        session_id=session_id,
        query=query,
        sources=[ArticleSource(
            article_id=a.id,
            article_number=a.article_number,
            document_title=a.document_title,
            similarity=a.similarity,
        ) for a in retrieved_articles],
        response=response.answer,
        law_versions=self.audit.build_law_versions(
            [a.id for a in retrieved_articles]
        ),
    )
    self.audit.save_research_audit(audit)

    return response
```

### GeneratorService Integration

```python
# services/generator.py — addition
def generate(self, template_id, data, output_path) -> GenerationResult:
    # ... existing generation logic ...
    result = self._generate_pdf(template, data, output_path)

    # NEW: Save contract audit
    audit = ContractAudit(
        contract_type=template.type,
        input_data=data,
        generated_content=result.content_text,
        legal_references=[...],
        law_versions=self.audit.build_law_versions(template.legal_references),
        pdf_storage_path=str(output_path),
    )
    self.audit.save_contract_audit(audit)

    return result
```

## CLI Contract

```bash
# List recent audits
python -m legal_chatbot audit list --limit 10
# Output:
# ┌─ Recent Audits ─────────────────────────────────────────────┐
# │ ID        Type       Query/Contract        Date             │
# │ a1b2c3    research   "Điều kiện mua đất?"  2026-02-10 14:30│
# │ d4e5f6    contract   sale_land             2026-02-10 13:15│
# │ g7h8i9    research   "Thuế chuyển nhượng?" 2026-02-10 12:00│
# └─────────────────────────────────────────────────────────────┘

# Verify a specific audit
python -m legal_chatbot audit verify a1b2c3
# Output:
# ┌─ Audit Verification ───────────────────────────────────────┐
# │ Audit: a1b2c3 (research)                                   │
# │ Query: "Điều kiện mua đất?"                                │
# │ Date: 2026-02-10 14:30                                     │
# │                                                             │
# │ Law Versions Used:                                          │
# │ ✓ Luật Đất đai 2024 (31/2024/QH15) — still active         │
# │ ✓ NĐ 102/2024 — still active                              │
# │                                                             │
# │ Status: ✓ All law versions current                         │
# └─────────────────────────────────────────────────────────────┘

# Show audit details
python -m legal_chatbot audit show a1b2c3
# Output: Full audit entry with sources, response, law versions
```

## Error Handling

| Error | Handling |
|-------|----------|
| DB insert fails | Log warning, don't fail the main operation |
| Audit not found | Return None, CLI shows "Audit not found" |
| Law version check fails | Mark as "unknown" status |

## Testing Contract

```python
def test_save_research_audit():
    """Should save and retrieve research audit"""
    audit = ResearchAudit(query="test", response="answer", sources=[...])
    audit_id = service.save_research_audit(audit)
    retrieved = service.get_research_audit(audit_id)
    assert retrieved.query == "test"

def test_verify_current_laws():
    """Should confirm laws are still current"""
    # Insert audit with active law version
    result = service.verify_audit(audit_id)
    assert result["is_current"] is True
    assert len(result["outdated_laws"]) == 0

def test_verify_outdated_laws():
    """Should detect outdated law versions"""
    # Insert audit, then update law status to 'repealed'
    result = service.verify_audit(audit_id)
    assert result["is_current"] is False
    assert len(result["outdated_laws"]) == 1

def test_list_audits_combined():
    """Should list both research and contract audits"""
    audits = service.list_audits(audit_type="all")
    types = {a["type"] for a in audits}
    assert "research" in types or "contract" in types

def test_audit_does_not_fail_main_operation():
    """Audit failure should not prevent chat/generate from completing"""
    # Mock DB to fail on audit insert
    # Verify chat() still returns response
```
