"""Audit trail service for research and contract verification"""

import logging
import uuid
from datetime import datetime
from typing import List, Optional

from legal_chatbot.db.base import DatabaseInterface
from legal_chatbot.models.audit import (
    ArticleSource,
    ContractAudit,
    LawVersion,
    ResearchAudit,
)

logger = logging.getLogger(__name__)


class AuditService:
    """Records and retrieves audit trails for research and contracts."""

    def __init__(self, db: DatabaseInterface):
        self.db = db

    def save_research_audit(self, audit: ResearchAudit) -> str:
        """Save a research audit entry. Returns audit ID."""
        try:
            if not audit.id:
                audit.id = str(uuid.uuid4())

            data = {
                "id": audit.id,
                "session_id": audit.session_id,
                "query": audit.query,
                "sources": [s.model_dump() for s in audit.sources],
                "response": audit.response,
                "law_versions": [lv.model_dump() for lv in audit.law_versions],
                "confidence_score": audit.confidence_score,
                "created_at": datetime.now().isoformat(),
            }

            self._insert_audit("research_audits", data)
            logger.info(f"Saved research audit: {audit.id}")
            return audit.id
        except Exception as e:
            logger.warning(f"Failed to save research audit: {e}")
            return audit.id or ""

    def save_contract_audit(self, audit: ContractAudit) -> str:
        """Save a contract audit entry. Returns audit ID."""
        try:
            if not audit.id:
                audit.id = str(uuid.uuid4())

            data = {
                "id": audit.id,
                "session_id": audit.session_id,
                "contract_type": audit.contract_type,
                "input_data": audit.input_data,
                "generated_content": audit.generated_content,
                "legal_references": [r.model_dump() for r in audit.legal_references],
                "law_versions": [lv.model_dump() for lv in audit.law_versions],
                "pdf_storage_path": audit.pdf_storage_path,
                "created_at": datetime.now().isoformat(),
            }

            self._insert_audit("contract_audits", data)
            logger.info(f"Saved contract audit: {audit.id}")
            return audit.id
        except Exception as e:
            logger.warning(f"Failed to save contract audit: {e}")
            return audit.id or ""

    def get_research_audit(self, audit_id: str) -> Optional[ResearchAudit]:
        """Get a specific research audit by ID."""
        try:
            row = self._get_audit("research_audits", audit_id)
            if not row:
                return None
            return self._row_to_research_audit(row)
        except Exception as e:
            logger.warning(f"Failed to get research audit {audit_id}: {e}")
            return None

    def get_contract_audit(self, audit_id: str) -> Optional[ContractAudit]:
        """Get a specific contract audit by ID."""
        try:
            row = self._get_audit("contract_audits", audit_id)
            if not row:
                return None
            return self._row_to_contract_audit(row)
        except Exception as e:
            logger.warning(f"Failed to get contract audit {audit_id}: {e}")
            return None

    def list_audits(self, limit: int = 20, audit_type: str = "all") -> list[dict]:
        """List recent audit entries.

        audit_type: 'research', 'contract', or 'all'
        Returns combined list sorted by created_at desc.
        """
        results = []
        try:
            if audit_type in ("all", "research"):
                rows = self._list_table("research_audits", limit)
                for row in rows:
                    results.append({
                        "id": row.get("id", ""),
                        "type": "research",
                        "summary": row.get("query", "")[:60],
                        "created_at": row.get("created_at", ""),
                    })

            if audit_type in ("all", "contract"):
                rows = self._list_table("contract_audits", limit)
                for row in rows:
                    results.append({
                        "id": row.get("id", ""),
                        "type": "contract",
                        "summary": row.get("contract_type", ""),
                        "created_at": row.get("created_at", ""),
                    })

            # Sort by created_at descending
            results.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            return results[:limit]
        except Exception as e:
            logger.warning(f"Failed to list audits: {e}")
            return []

    def verify_audit(self, audit_id: str) -> dict:
        """Verify if an audit entry's law versions are still current.

        Checks each law_version against current DB document status.
        """
        # Try research audit first, then contract
        audit = self.get_research_audit(audit_id)
        audit_type = "research"
        if audit is None:
            contract = self.get_contract_audit(audit_id)
            if contract is None:
                return {
                    "audit_id": audit_id,
                    "is_current": False,
                    "error": "Audit not found",
                    "verified_at": datetime.now().isoformat(),
                }
            law_versions = contract.law_versions
            audit_type = "contract"
        else:
            law_versions = audit.law_versions

        outdated_laws = []
        for lv in law_versions:
            try:
                doc = self.db.get_document(lv.document_id)
                if doc is None:
                    outdated_laws.append({
                        "document_number": lv.document_number,
                        "old_status": lv.status,
                        "new_status": "not_found",
                    })
                elif doc.get("status") != lv.status:
                    outdated_laws.append({
                        "document_number": lv.document_number,
                        "old_status": lv.status,
                        "new_status": doc.get("status", "unknown"),
                    })
            except Exception as e:
                outdated_laws.append({
                    "document_number": lv.document_number,
                    "old_status": lv.status,
                    "new_status": f"error: {e}",
                })

        return {
            "audit_id": audit_id,
            "audit_type": audit_type,
            "is_current": len(outdated_laws) == 0,
            "outdated_laws": outdated_laws,
            "law_versions_checked": len(law_versions),
            "verified_at": datetime.now().isoformat(),
        }

    def build_law_versions(self, article_ids: List[str]) -> List[LawVersion]:
        """Build law version list from article IDs.

        Looks up parent documents for each article.
        Returns unique list of LawVersion entries.
        """
        seen_doc_ids = set()
        versions = []

        for article_id in article_ids:
            try:
                # Get article's parent document info
                # Articles store document_id as a field
                doc_id = self._get_document_id_for_article(article_id)
                if doc_id and doc_id not in seen_doc_ids:
                    seen_doc_ids.add(doc_id)
                    doc = self.db.get_document(doc_id)
                    if doc:
                        versions.append(LawVersion(
                            document_id=doc_id,
                            document_number=doc.get("document_number", ""),
                            title=doc.get("title", ""),
                            effective_date=doc.get("effective_date"),
                            status=doc.get("status", "active"),
                        ))
            except Exception as e:
                logger.warning(f"Failed to build law version for article {article_id}: {e}")

        return versions

    # ---- Internal helpers ----

    def _insert_audit(self, table: str, data: dict) -> None:
        """Insert audit data using the underlying database."""
        # Convert list/dict fields to JSON-compatible format
        import json
        for key in ("sources", "law_versions", "legal_references", "input_data"):
            if key in data and not isinstance(data[key], str):
                data[key] = json.dumps(data[key], ensure_ascii=False, default=str)

        # Use the db's underlying client for direct table access
        if hasattr(self.db, "_write"):
            # Supabase mode
            client = self.db._write()
            client.table(table).insert(data).execute()
        else:
            # SQLite mode - audits not supported, just log
            logger.info(f"SQLite mode: audit saved to log only (table={table}, id={data.get('id')})")

    def _get_audit(self, table: str, audit_id: str) -> Optional[dict]:
        """Get a single audit row by ID."""
        # Use service role key to bypass RLS on audit tables
        if hasattr(self.db, "_write"):
            client = self.db._write()
            result = client.table(table).select("*").eq("id", audit_id).execute()
            return result.data[0] if result.data else None
        return None

    def _list_table(self, table: str, limit: int) -> list[dict]:
        """List rows from an audit table ordered by created_at desc."""
        # Use service role key to bypass RLS on audit tables
        if hasattr(self.db, "_write"):
            client = self.db._write()
            # Each table has different columns
            if table == "research_audits":
                columns = "id,created_at,query"
            else:
                columns = "id,created_at,contract_type"
            result = (
                client.table(table)
                .select(columns)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data
        return []

    def _get_document_id_for_article(self, article_id: str) -> Optional[str]:
        """Look up the document_id for an article."""
        if hasattr(self.db, "_read"):
            client = self.db._read()
            result = (
                client.table("articles")
                .select("document_id")
                .eq("id", article_id)
                .limit(1)
                .execute()
            )
            if result.data:
                return result.data[0].get("document_id")
        return None

    def _row_to_research_audit(self, row: dict) -> ResearchAudit:
        """Convert a DB row to ResearchAudit model."""
        import json
        sources = row.get("sources", "[]")
        if isinstance(sources, str):
            sources = json.loads(sources)
        law_versions = row.get("law_versions", "[]")
        if isinstance(law_versions, str):
            law_versions = json.loads(law_versions)

        return ResearchAudit(
            id=row.get("id", ""),
            session_id=row.get("session_id"),
            query=row.get("query", ""),
            sources=[ArticleSource(**s) for s in sources],
            response=row.get("response", ""),
            law_versions=[LawVersion(**lv) for lv in law_versions],
            confidence_score=row.get("confidence_score"),
            created_at=row.get("created_at"),
        )

    def _row_to_contract_audit(self, row: dict) -> ContractAudit:
        """Convert a DB row to ContractAudit model."""
        import json
        legal_refs = row.get("legal_references", "[]")
        if isinstance(legal_refs, str):
            legal_refs = json.loads(legal_refs)
        law_versions = row.get("law_versions", "[]")
        if isinstance(law_versions, str):
            law_versions = json.loads(law_versions)
        input_data = row.get("input_data", "{}")
        if isinstance(input_data, str):
            input_data = json.loads(input_data)

        return ContractAudit(
            id=row.get("id", ""),
            session_id=row.get("session_id"),
            contract_type=row.get("contract_type", ""),
            input_data=input_data,
            generated_content=row.get("generated_content", ""),
            legal_references=[ArticleSource(**r) for r in legal_refs],
            law_versions=[LawVersion(**lv) for lv in law_versions],
            pdf_storage_path=row.get("pdf_storage_path"),
            created_at=row.get("created_at"),
        )
