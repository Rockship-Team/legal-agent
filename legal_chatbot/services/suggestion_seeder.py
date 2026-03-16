"""Suggestion Seeder — generates sample data and article templates for contract fields using LLM.

Generates once and saves to DB so contract creation doesn't need LLM calls.
"""

import json
import logging
from typing import Optional

from legal_chatbot.db.supabase import SupabaseClient
from legal_chatbot.utils.llm import call_llm_json, call_llm_sonnet

logger = logging.getLogger(__name__)


class SuggestionSeeder:
    """Generate and persist field suggestion examples for contract templates."""

    def __init__(self, db: SupabaseClient):
        self.db = db

    def seed_template(self, contract_type: str, force: bool = False) -> Optional[dict]:
        """Generate sample data for a single template.

        Returns the sample_data dict on success, None if skipped or failed.
        """
        template = self.db.get_contract_template(contract_type)
        if not template:
            logger.warning(f"Template not found: {contract_type}")
            return None

        if template.get("sample_data") and not force:
            logger.info(f"Skipping {contract_type} — already has sample data")
            return None

        required_fields = template.get("required_fields", {})
        fields = required_fields.get("fields", [])
        if not fields:
            logger.warning(f"Template {contract_type} has no fields defined")
            return None

        display_name = template.get("display_name", contract_type)
        sample_data = self._generate_sample_data(display_name, fields)

        if sample_data:
            self.db.update_template_sample_data(contract_type, sample_data)
            logger.info(f"Seeded {len(sample_data)} fields for {contract_type}")
            return sample_data

        logger.warning(f"LLM failed to generate sample data for {contract_type}")
        return None

    def seed_all(self, force: bool = False) -> list[dict]:
        """Generate sample data for all templates.

        Returns list of {contract_type, display_name, status, field_count}.
        """
        if force:
            templates = self.db.list_all_active_templates()
        else:
            templates = self.db.get_templates_needing_seed()

        results = []
        for t in templates:
            ct = t["contract_type"]
            display = t["display_name"]
            sample = self.seed_template(ct, force=force)
            results.append({
                "contract_type": ct,
                "display_name": display,
                "status": "seeded" if sample else "skipped",
                "field_count": len(sample) if sample else 0,
            })

        return results

    def get_status(self) -> list[dict]:
        """Return status of all templates (has sample_data or not)."""
        all_templates = self.db.list_all_active_templates()
        results = []
        for t in all_templates:
            sd = t.get("sample_data")
            results.append({
                "contract_type": t["contract_type"],
                "display_name": t["display_name"],
                "has_data": sd is not None and len(sd) > 0,
                "field_count": len(sd) if sd else 0,
            })
        return results

    # Max fields per LLM call to avoid token truncation
    BATCH_SIZE = 15

    def _generate_sample_data(self, display_name: str, fields: list[dict]) -> Optional[dict]:
        """Use LLM to generate example data for template fields.

        Processes fields in batches to avoid response truncation on large templates.
        """
        all_valid = {}

        for i in range(0, len(fields), self.BATCH_SIZE):
            batch = fields[i : i + self.BATCH_SIZE]
            result = self._generate_batch(display_name, batch)
            if result:
                all_valid.update(result)

        return all_valid if all_valid else None

    def _generate_batch(self, display_name: str, fields: list[dict]) -> Optional[dict]:
        """Generate sample data for a batch of fields."""
        field_list = "\n".join(
            f"- {f['name']} ({f.get('label', f['name'])}): loại {f.get('field_type', 'text')}"
            for f in fields
        )

        system = f"""Bạn là chuyên gia pháp lý Việt Nam. Tạo DỮ LIỆU MẪU cho hợp đồng "{display_name}".

Với mỗi field, tạo:
- examples: mảng 2-3 ví dụ THỰC TẾ bằng tiếng Việt (dữ liệu giả nhưng đúng format)
- format_hint: gợi ý ngắn gọn về format cần nhập

Trả về JSON object (KHÔNG có text khác):
{{
  "field_name": {{
    "examples": ["ví dụ 1", "ví dụ 2"],
    "format_hint": "mô tả format"
  }},
  ...
}}

Lưu ý:
- Tên người: Họ và tên Việt Nam thật (Nguyễn Văn A, Trần Thị B)
- Địa chỉ: Đầy đủ số nhà, đường, phường, quận, TP
- CCCD: 12 chữ số bắt đầu bằng 0
- Số tiền: Có dấu chấm phân cách hàng nghìn + VNĐ
- Ngày tháng: DD/MM/YYYY
- Ví dụ phải PHÙ HỢP với loại hợp đồng "{display_name}"
"""

        messages = [
            {"role": "user", "content": f"Tạo dữ liệu mẫu cho các field sau:\n{field_list}"}
        ]

        result = call_llm_json(messages, temperature=0.3, max_tokens=4000, system=system)

        if not isinstance(result, dict):
            return None

        # Validate structure
        valid = {}
        for f in fields:
            name = f["name"]
            if name in result and isinstance(result[name], dict):
                entry = result[name]
                if "examples" in entry and isinstance(entry["examples"], list):
                    valid[name] = {
                        "examples": entry["examples"][:3],
                        "format_hint": entry.get("format_hint", f.get("label", "")),
                    }

        return valid if valid else None

    # =================================================================
    # Article template generation (ĐIỀU 1-9 with placeholders)
    # =================================================================

    def seed_articles(self, contract_type: str, force: bool = False) -> Optional[list]:
        """Generate default article templates for a single template.

        Returns the articles list on success, None if skipped or failed.
        """
        template = self.db.get_contract_template(contract_type)
        if not template:
            logger.warning(f"Template not found: {contract_type}")
            return None

        if template.get("default_articles") and not force:
            logger.info(f"Skipping {contract_type} — already has default articles")
            return None

        required_fields = template.get("required_fields", {})
        fields = required_fields.get("fields", [])
        if not fields:
            logger.warning(f"Template {contract_type} has no fields defined")
            return None

        display_name = template.get("display_name", contract_type)
        cached_articles = template.get("cached_articles") or []

        articles = self._generate_article_templates(display_name, fields, cached_articles)

        if articles:
            self.db.update_template_default_articles(contract_type, articles)
            logger.info(f"Seeded {len(articles)} article templates for {contract_type}")
            return articles

        logger.warning(f"LLM failed to generate article templates for {contract_type}")
        return None

    def seed_all_articles(self, force: bool = False) -> list[dict]:
        """Generate default articles for all templates.

        Returns list of {contract_type, display_name, status, article_count}.
        """
        if force:
            templates = self.db.list_all_active_templates()
        else:
            templates = self.db.get_templates_needing_articles()

        results = []
        for t in templates:
            ct = t["contract_type"]
            display = t["display_name"]
            articles = self.seed_articles(ct, force=force)
            results.append({
                "contract_type": ct,
                "display_name": display,
                "status": "seeded" if articles else "skipped",
                "article_count": len(articles) if articles else 0,
            })

        return results

    def get_articles_status(self) -> list[dict]:
        """Return status of all templates (has default_articles or not)."""
        all_templates = self.db.list_all_active_templates()
        results = []
        for t in all_templates:
            # Need to fetch full template to check default_articles
            full = self.db.get_contract_template(t["contract_type"])
            da = full.get("default_articles") if full else None
            results.append({
                "contract_type": t["contract_type"],
                "display_name": t["display_name"],
                "has_articles": da is not None and len(da) > 0,
                "article_count": len(da) if da else 0,
            })
        return results

    def _generate_article_templates(
        self, display_name: str, fields: list[dict], cached_articles: list[dict]
    ) -> Optional[list]:
        """Use LLM to generate 9 article templates with field placeholders.

        Placeholders use {field_name} syntax matching the template's field names.
        """
        # Build field info for LLM
        field_info = "\n".join(
            f"- {{{f['name']}}}: {f.get('label', f['name'])} (loại: {f.get('field_type', 'text')})"
            for f in fields
        )

        # Build legal context from cached articles
        legal_context = ""
        if cached_articles:
            for a in cached_articles[:10]:
                content = a.get("content", "")[:300]
                legal_context += f"\n- Điều {a.get('article_number', '?')} ({a.get('document_title', '')}): {content}"

        system_prompt = f"""Bạn là chuyên gia soạn thảo hợp đồng pháp lý Việt Nam. Nhiệm vụ: tạo MẪU ĐIỀU KHOẢN cho hợp đồng "{display_name}".

QUY TẮC QUAN TRỌNG:
- Tạo đúng 9 ĐIỀU (articles)
- Sử dụng PLACEHOLDER {{field_name}} cho các trường thông tin (sẽ được thay thế bằng dữ liệu thực)
- Nội dung phải cụ thể, chi tiết, trích dẫn luật khi cần
- Trả về JSON array, KHÔNG có text nào khác

CÁC PLACEHOLDER CÓ SẴN:
{field_info}

FORMAT:
[
  {{"title": "ĐIỀU 1: ĐỐI TƯỢNG CỦA HỢP ĐỒNG", "content": ["1.1. Bên A ({{ben_a_ten}}) đồng ý ...", "1.2. ..."]}},
  {{"title": "ĐIỀU 2: GIÁ VÀ PHƯƠNG THỨC THANH TOÁN", "content": ["2.1. Giá trị: {{gia_tri}} ...", "2.2. ..."]}},
  ...
]

CÁC ĐIỀU BẮT BUỘC:
1. Đối tượng hợp đồng
2. Giá cả / phương thức thanh toán
3. Thời hạn
4. Quyền và nghĩa vụ Bên A
5. Quyền và nghĩa vụ Bên B
6. Cam kết của các bên
7. Trách nhiệm do vi phạm
8. Giải quyết tranh chấp
9. Điều khoản chung

LƯU Ý:
- Dùng placeholder {{field_name}} ở những chỗ cần thông tin cụ thể
- Những nội dung chung (không phụ thuộc field) thì viết sẵn luôn
- Placeholder phải ĐÚNG tên field đã cho, KHÔNG được tự tạo placeholder mới"""

        user_prompt = f"""Tạo 9 ĐIỀU mẫu cho "{display_name}".
{f"ĐIỀU LUẬT THAM KHẢO:{legal_context}" if legal_context else ""}

Trả về JSON array (9 articles với placeholders). CHỈ JSON, không có text giải thích."""

        try:
            result = call_llm_sonnet(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=6000,
            )

            # Parse JSON from response
            result = result.strip()
            if result.startswith("```"):
                result = result.split("```")[1]
                if result.startswith("json"):
                    result = result[4:]
                result = result.strip()

            articles = json.loads(result)
            if isinstance(articles, list) and len(articles) >= 5:
                return articles
        except Exception as e:
            logger.error(f"Error generating article templates: {e}")

        return None
