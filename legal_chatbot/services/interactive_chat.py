"""Interactive chat service with session state and contract management"""

import asyncio
import json
import random
import re
import tempfile
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel

from legal_chatbot.utils.config import get_settings
from legal_chatbot.utils.llm import (
    call_llm, call_llm_json, call_llm_stream_async,
    call_llm_sonnet, call_llm_stream_sonnet_async,
)
from legal_chatbot.utils.vietnamese import remove_diacritics
from legal_chatbot.services.chat import CATEGORY_KEYWORDS
from legal_chatbot.services.research import ResearchService, ResearchResult
from legal_chatbot.services.dynamic_template import DynamicTemplate, DynamicField
from legal_chatbot.services.generator import GeneratorService
from legal_chatbot.services.pdf_generator import UniversalPDFGenerator


class ContractDraft(BaseModel):
    """A contract draft being edited in the session"""
    id: str
    contract_type: str
    template: Optional[DynamicTemplate] = None
    field_values: dict = {}
    legal_basis: list[str] = []
    created_at: datetime = datetime.now()
    last_modified: datetime = datetime.now()
    # Track which field we're currently asking about
    current_field_index: int = 0
    # State: 'collecting' | 'ready' | 'exported'
    state: str = 'collecting'
    # Generated articles (ĐIỀU 1-9) from LLM
    articles: list[dict] = []
    # Path to saved contract JSON
    contract_json_path: Optional[str] = None


class ChatSession(BaseModel):
    """Chat session with state management"""
    id: str
    messages: list[dict] = []
    current_draft: Optional[ContractDraft] = None
    research_results: list[ResearchResult] = []
    created_at: datetime = datetime.now()
    # Conversation mode: 'normal' | 'contract_creation'
    mode: str = 'normal'

    class Config:
        arbitrary_types_allowed = True


class AgentCommand(BaseModel):
    """A parsed agent command from user input"""
    command: str
    args: dict = {}
    original_text: str


class InteractiveChatResponse(BaseModel):
    """Response from interactive chat"""
    message: str
    contract_draft: Optional[ContractDraft] = None
    html_preview: Optional[str] = None
    pdf_path: Optional[str] = None
    action_taken: Optional[str] = None


class InteractiveChatService:
    """Interactive chat service with research, contract generation, and editing"""

    # System prompt — detailed legal analysis with article citations
    SYSTEM_PROMPT = """Bạn là một chuyên viên tư vấn pháp lý Việt Nam. Hãy nói chuyện thân thiện nhưng CHUYÊN SÂU.

PHONG CÁCH:
- Thân thiện, gần gũi nhưng vẫn chuyên nghiệp
- Câu hỏi đơn giản → trả lời ngắn gọn (KHÔNG cần dùng [SECTION])
- Câu hỏi pháp lý → trả lời THẬT CHI TIẾT, phân tích sâu, dùng cấu trúc bên dưới

ĐỊNH DẠNG ĐẶC BIỆT (dùng khi trả lời câu hỏi pháp lý):

1. Bao bọc mỗi phần nội dung trong [SECTION: Tên phần] ... [/SECTION]
   Các phần thường dùng: "Căn cứ pháp lý", "Phân tích chi tiết", "Trường hợp cụ thể", "Tóm tắt & Gợi ý"

2. Khi trích dẫn NGUYÊN VĂN điều luật, dùng [QUOTE]nội dung nguyên văn[/QUOTE]
   Chỉ dùng cho nội dung copy chính xác từ điều luật. Không dùng cho diễn giải.

3. Khi nêu con số quan trọng (thời hạn, số tiền, tỷ lệ %), dùng [HL]giá trị[/HL]
   Ví dụ: [HL]90 ngày[/HL], [HL]30 triệu đồng[/HL], [HL]50%[/HL]

4. Giữ nguyên markdown thông thường:
   - **in đậm** cho nhấn mạnh
   - Điều X (Luật Y) cho trích dẫn điều luật
   - ⚠️ Lưu ý: cho cảnh báo quan trọng
   - Danh sách - hoặc 1. 2. 3.

KHI TRẢ LỜI CÂU HỎI PHÁP LÝ, BẮT BUỘC:
1. Liệt kê TẤT CẢ điều luật liên quan từ CONTEXT (Điều X, Luật Y năm Z)
2. Phân nhóm theo chủ đề trong các [SECTION] riêng biệt
3. Trích dẫn nguyên văn nội dung quan trọng bằng [QUOTE]...[/QUOTE]
4. Nêu rõ trường hợp ngoại lệ, lưu ý đặc biệt
5. Kết thúc bằng [SECTION: Tóm tắt & Gợi ý] với tóm tắt ngắn và gợi ý câu hỏi tiếp theo
6. Trả lời DÀI và ĐẦY ĐỦ — không cắt ngắn, không tóm lược quá mức

VÍ DỤ CẤU TRÚC TRẢ LỜI TỐT:
---
[SECTION: Căn cứ pháp lý]
Các luật áp dụng: Luật Đất đai 2024, Nghị định 88/2024/NĐ-CP

**Trường hợp 1: Chuyển nhượng quyền sử dụng đất**
Điều 138 (Luật Đất đai 2024) quy định:
[QUOTE]Người sử dụng đất được chuyển nhượng quyền sử dụng đất khi có Giấy chứng nhận, đất không có tranh chấp...[/QUOTE]
Thời hạn xử lý: [HL]30 ngày làm việc[/HL]

**Trường hợp 2: Tặng cho quyền sử dụng đất**
Điều 139 (Luật Đất đai 2024) quy định:
[QUOTE]Người sử dụng đất được tặng cho quyền sử dụng đất theo quy định...[/QUOTE]
[/SECTION]

[SECTION: Phân tích chi tiết]
**Điều kiện cần đáp ứng:**
1. Có giấy chứng nhận quyền sử dụng đất
2. Đất không có tranh chấp
3. Không bị kê biên để thi hành án

Lệ phí: [HL]0.5% giá trị chuyển nhượng[/HL]
[/SECTION]

[SECTION: Tóm tắt & Gợi ý]
**Tóm tắt:** Việc chuyển nhượng cần đáp ứng đủ điều kiện theo Điều 138 và mất [HL]30 ngày[/HL] xử lý.

⚠️ Lưu ý: Đây chỉ là tham khảo, cần xác minh với cơ quan có thẩm quyền.

Bạn muốn tìm hiểu thêm về thủ tục cụ thể hay chi phí không?
[/SECTION]
---

NGUYÊN TẮC:
1. DỰA HOÀN TOÀN vào các điều luật trong CONTEXT — không tự suy diễn
2. Nếu CONTEXT có 20 điều luật, hãy phân tích hết 20 điều — không bỏ qua
3. Khi tạo hợp đồng, HỎI TỪNG THÔNG TIN MỘT (KHÔNG dùng [SECTION] cho contract flow)
4. Chủ động gợi ý bước tiếp theo

Lưu ý: Đây chỉ là tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp."""

    # Human-like responses for various situations
    HUMAN_RESPONSES = {
        'greeting': [
            "Chào bạn! Mình có thể giúp gì cho bạn?",
            "Hey! Bạn cần tư vấn về vấn đề gì?",
            "Chào! Hôm nay bạn cần hỗ trợ gì nè?",
        ],
        'contract_start': [
            "OK, mình sẽ giúp bạn làm {type}. Để bắt đầu, cho mình hỏi nhé:",
            "Được rồi, làm {type} ha. Mình cần hỏi bạn vài thông tin:",
            "{type} nhé! Để mình hỏi từng cái một cho dễ:",
        ],
        'field_ask': [
            "{label} là gì?",
            "Cho mình biết {label} nhé?",
            "{label}?",
            "Tiếp theo, {label} là gì?",
        ],
        'field_confirm': [
            "OK, ghi nhận rồi!",
            "Được rồi!",
            "Noted!",
            "Đã lưu!",
        ],
        'contract_ready': [
            "Xong rồi! Hợp đồng đã sẵn sàng.",
            "Đã đủ thông tin! Hợp đồng của bạn đã sẵn sàng rồi.",
            "OK, mình đã ghi nhận đầy đủ. Hợp đồng sẵn sàng rồi!",
        ],
        'missing_contract': [
            "Chưa có hợp đồng nào nè. Bạn muốn tạo loại hợp đồng gì?",
            "Chưa tạo hợp đồng. Bạn muốn tạo mới không?",
        ],
        'pdf_success': [
            "Đã xuất PDF xong rồi! Bạn có thể tải về ngay.",
            "OK, hợp đồng PDF đã sẵn sàng tải về!",
            "Xong! Hợp đồng đã được xuất PDF.",
        ],
        'preview_opened': [
            "Đây là bản xem trước hợp đồng của bạn.",
            "Bản xem trước hợp đồng đây!",
        ],
    }

    def __init__(self, api_mode: bool = False):
        self._research_service = None  # lazy-loaded (needs embedding model)
        self._db = None  # lazy-loaded
        self._available_types_cache = None  # cached from DB
        self._categories_cache = None  # cached category stats
        self.pdf_generator = GeneratorService()
        self.session: Optional[ChatSession] = None
        self.api_mode = api_mode

    @property
    def db(self):
        """Lazy-load database client."""
        if self._db is None:
            from legal_chatbot.db.supabase import get_database
            self._db = get_database()
        return self._db

    @property
    def research_service(self):
        """Lazy-load ResearchService (avoids loading embedding model on startup)"""
        if self._research_service is None:
            self._research_service = ResearchService()
        return self._research_service

    def _get_available_categories(self) -> list[dict]:
        """Get categories that have actual data in DB (cached)."""
        if self._categories_cache is not None:
            return self._categories_cache

        try:
            all_cats = self.db.get_all_categories_with_stats()
            self._categories_cache = [
                {
                    "name": c["name"],
                    "display_name": c.get("display_name", c["name"]),
                    "article_count": c.get("article_count", 0),
                }
                for c in all_cats
                if c.get("article_count", 0) > 0
            ]
        except Exception:
            self._categories_cache = []

        return self._categories_cache

    def _build_system_prompt(self) -> str:
        """Build system prompt with actual available data from DB."""
        categories = self._get_available_categories()
        contracts = self._get_available_contract_types()

        if categories:
            cat_list = ", ".join(
                f"{c['display_name']} ({c['article_count']} điều)"
                for c in categories
            )
            data_section = f"\nDỮ LIỆU HIỆN CÓ: {cat_list}."
            data_section += "\nKhi chào hỏi hoặc giới thiệu, CHỈ liệt kê các lĩnh vực có trong dữ liệu trên. KHÔNG liệt kê lĩnh vực không có dữ liệu."
        else:
            data_section = "\nDỮ LIỆU HIỆN CÓ: Chưa có dữ liệu nào. Thông báo cho người dùng biết hệ thống đang được cập nhật."

        if contracts:
            contract_list = ", ".join(c["name"] for c in contracts)
            data_section += f"\nHỢP ĐỒNG HỖ TRỢ: {contract_list}."

        return self.SYSTEM_PROMPT + data_section

    def _get_available_contract_types(self) -> list[dict]:
        """Get available contract types from DB (cached).

        Returns list of {"type": "cho_thue_nha", "name": "Hợp đồng thuê nhà ở"}
        Only includes templates with required_fields defined.
        """
        if self._available_types_cache is not None:
            return self._available_types_cache

        try:
            templates = self.db.list_all_active_templates()
            self._available_types_cache = [
                {"type": t["contract_type"], "name": t["display_name"]}
                for t in templates
            ]
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"Failed to load templates from DB: {e}")
            self._available_types_cache = []

        return self._available_types_cache

    async def _resolve_contract_type(self, input_text: str) -> Optional[str]:
        """Resolve user input to a Vietnamese DB contract_type slug.

        Fully DB-driven — no hardcoded mappings. When new templates are added
        to Supabase, they are automatically available without code changes.

        Resolution order:
          1. DB display_name substring match (fast, no LLM)
          2. Direct slug match (for already-resolved slugs)
          3. LLM classification (handles ambiguous/short input)
        """
        from legal_chatbot.utils.vietnamese import remove_diacritics as _rd

        input_normalized = _rd(input_text.lower().strip())
        available = self._get_available_contract_types()

        # 1. Substring match against DB display_names
        for t in available:
            display_normalized = _rd(t["name"].lower())
            if display_normalized in input_normalized or input_normalized in display_normalized:
                return t["type"]

        # 2. Check if input is already a valid DB slug (e.g. "cho_thue_dat")
        slug_candidate = input_normalized.replace(" ", "_")
        for t in available:
            if t["type"] == slug_candidate:
                return t["type"]

        # 3. LLM fallback — handles short/ambiguous input like "chuyển nhượng đất"
        if available:
            return await self._detect_contract_type_with_llm(input_text)

        return None

    def _load_template_from_db(self, contract_type_slug: str) -> DynamicTemplate:
        """Load contract template from Supabase and build DynamicTemplate.

        Args:
            contract_type_slug: Vietnamese slug like 'cho_thue_nha'

        Raises:
            ValueError if template not found or has no required_fields
        """
        template_row = self.db.get_contract_template(contract_type_slug)
        if not template_row:
            raise ValueError(f"Template không tồn tại trong DB: {contract_type_slug}")

        required_fields = template_row.get("required_fields")
        if not required_fields:
            raise ValueError(f"Template '{contract_type_slug}' chưa có định nghĩa trường (required_fields)")

        # Build DynamicField list from JSONB
        fields = [
            DynamicField(
                name=f["name"],
                label=f["label"],
                required=f.get("required", True),
                field_type=f.get("field_type", "text"),
                default_value=f.get("default_value"),
                description=f.get("description"),
            )
            for f in required_fields.get("fields", [])
        ]

        return DynamicTemplate(
            contract_type=contract_type_slug,
            name=template_row["display_name"],
            description=template_row.get("description") or "",
            fields=fields,
            legal_references=required_fields.get("legal_refs", []),
            key_terms=required_fields.get("key_terms", []),
            field_groups=required_fields.get("field_groups", []),
            common_groups=required_fields.get("common_groups", []),
            generated_from="Supabase contract_templates",
        )

    def _call_llm(self, messages: list, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """Call LLM via shared Anthropic client."""
        try:
            return call_llm(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as e:
            return f"Lỗi khi gọi LLM: {e}"

    def _random_response(self, key: str, **kwargs) -> str:
        """Get a random human-like response"""
        responses = self.HUMAN_RESPONSES.get(key, [key])
        response = random.choice(responses)
        return response.format(**kwargs) if kwargs else response

    def _validate_field_input(self, field: DynamicField, value: str) -> Optional[str]:
        """Validate user input for a contract field — basic check only."""
        if not value or not value.strip():
            return f"Vui lòng nhập {field.label.lower()}."
        return None

    def start_session(self) -> ChatSession:
        """Start a new chat session"""
        self.session = ChatSession(id=str(uuid4()))
        return self.session

    def get_session(self) -> ChatSession:
        """Get current session or start new one"""
        if not self.session:
            self.start_session()
        return self.session

    def should_stream(self, user_input: str) -> bool:
        """Check if this input should use streaming (legal Q&A) vs non-streaming (contract flow).

        Mirrors the routing logic of chat() without actually processing.
        Returns True only when the input would go to _handle_natural_input()
        and is NOT a contract-related interaction.
        """
        session = self.get_session()
        input_normalized = remove_diacritics(user_input.lower().strip())

        # In contract creation mode → non-streaming
        if session.mode == 'contract_creation' and session.current_draft:
            return False

        # Check if user is answering contract type question
        if session.messages:
            last_assistant_msgs = [m for m in session.messages if m.get('role') == 'assistant']
            if last_assistant_msgs:
                last_content = last_assistant_msgs[-1].get('content', '')
                if 'loai hop dong' in remove_diacritics(last_content.lower()):
                    return False

        # Check if command would be parsed (contract creation, preview, export, etc.)
        command = self._parse_command(user_input)
        if command:
            return False

        # Check if _handle_natural_input would detect contract creation intent
        wants_contract = any(kw in input_normalized for kw in [
            'tao hop dong', 'lap hop dong', 'soan hop dong',
            'tao mau', 'viet hop dong', 'can hop dong',
            'muon tao hop dong', 'giup tao hop dong',
        ])
        if wants_contract:
            return False

        # Everything else → legal Q&A → stream
        return True

    async def chat(self, user_input: str) -> InteractiveChatResponse:
        """Process user input and return response"""
        session = self.get_session()

        # Add user message to history
        session.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })

        # Normalize input for comparison (remove Vietnamese diacritics)
        input_normalized = remove_diacritics(user_input.lower().strip())

        # Check if user is answering contract type question
        last_action = session.messages[-2].get('content', '') if len(session.messages) >= 2 else ''
        if 'loai hop dong' in remove_diacritics(last_action.lower()):
            # Resolve contract type from user input (DB + LLM, fully dynamic)
            resolved_slug = await self._resolve_contract_type(user_input)
            if resolved_slug:
                response = await self._create_contract(resolved_slug)
                session.messages.append({
                    "role": "assistant",
                    "content": response.message,
                    "timestamp": datetime.now().isoformat()
                })
                return response
            else:
                # LLM couldn't match either — show available types
                available = self._get_available_contract_types()
                if available:
                    type_list = "\n".join(f"• {t['name']}" for t in available)
                    msg = f"Mình chưa nhận diện được loại hợp đồng này. Hiện tại hỗ trợ:\n\n{type_list}\n\nBạn muốn tạo loại nào?"
                else:
                    msg = "Hiện tại chưa có mẫu hợp đồng nào trong hệ thống."
                response = InteractiveChatResponse(
                    message=msg,
                    action_taken="ask_contract_type"
                )
                session.messages.append({
                    "role": "assistant",
                    "content": response.message,
                    "timestamp": datetime.now().isoformat()
                })
                return response

        # Check if we're in contract creation mode (collecting fields)
        if session.mode == 'contract_creation' and session.current_draft:
            if session.current_draft.state == 'collecting':
                # Check for skip/cancel commands first
                _cancel_phrases = {'huy', 'huy hop dong', 'huy bo', 'cancel', 'thoat', 'bo qua'}
                if input_normalized in _cancel_phrases:
                    session.mode = 'normal'
                    session.current_draft = None
                    response = InteractiveChatResponse(
                        message="OK, đã hủy. Bạn cần gì khác không?",
                        action_taken="contract_cancelled"
                    )
                # Check for preview/export commands even during collection
                elif any(kw in input_normalized for kw in ['xem truoc', 'preview', 'xem hop dong']):
                    response = self._preview_contract(open_browser=not self.api_mode)
                elif any(kw in input_normalized for kw in ['xuat pdf', 'export pdf', 'luu pdf']):
                    response = self._export_pdf()
                else:
                    # Process the answer and ask next question
                    response = await self._process_field_answer(user_input)
            else:
                # Contract is ready, handle commands
                command = self._parse_command(user_input)
                if command:
                    response = await self._handle_command(command)
                else:
                    response = await self._handle_natural_input(user_input)
        else:
            # Normal mode - parse for commands first
            command = self._parse_command(user_input)

            if command:
                response = await self._handle_command(command)
            else:
                response = await self._handle_natural_input(user_input)

        # Add assistant response to history
        session.messages.append({
            "role": "assistant",
            "content": response.message,
            "timestamp": datetime.now().isoformat()
        })

        return response

    async def _process_field_answer(self, user_input: str) -> InteractiveChatResponse:
        """Process user's answer for current field and ask next question"""
        session = self.get_session()
        draft = session.current_draft

        if not draft or not draft.template:
            return InteractiveChatResponse(
                message=self._random_response('missing_contract'),
                action_taken="no_contract"
            )

        # Get current field
        fields = draft.template.fields
        required_fields = [f for f in fields if f.required]

        if draft.current_field_index < len(required_fields):
            current_field = required_fields[draft.current_field_index]

            # Validate the input before accepting
            validation_error = self._validate_field_input(current_field, user_input.strip())
            if validation_error:
                return InteractiveChatResponse(
                    message=validation_error,
                    contract_draft=draft,
                    action_taken="field_validation_error"
                )

            # Save the answer
            draft.field_values[current_field.name] = user_input.strip()
            draft.last_modified = datetime.now()

            # Move to next field
            draft.current_field_index += 1

            # Check if there are more required fields
            if draft.current_field_index < len(required_fields):
                next_field = required_fields[draft.current_field_index]
                confirm = self._random_response('field_confirm')
                question = self._random_response('field_ask', label=next_field.label.lower())
                return InteractiveChatResponse(
                    message=f"{confirm} {question}",
                    contract_draft=draft,
                    action_taken="field_collected"
                )
            else:
                # All required fields collected — auto-generate PDF
                draft.state = 'ready'
                session.mode = 'normal'
                return self._finalize_contract(draft)
        else:
            # Shouldn't reach here, but just in case
            draft.state = 'ready'
            session.mode = 'normal'
            return self._finalize_contract(draft)

    def _finalize_contract(self, draft: ContractDraft) -> InteractiveChatResponse:
        """Auto-generate PDF when all fields collected and return Supabase download URL.

        Uses temp files for PDF generation, uploads to Supabase Storage,
        then cleans up local files.
        """
        try:
            json_filename, json_bytes = self._build_contract_json(draft)
            pdf_filename = json_filename.replace('.json', '.pdf')

            # Write temp JSON → generate PDF → read PDF bytes → clean up
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_json = Path(tmp_dir) / json_filename
                tmp_pdf = Path(tmp_dir) / pdf_filename

                tmp_json.write_bytes(json_bytes)

                pdf_gen = UniversalPDFGenerator()
                pdf_gen.generate(contract_path=str(tmp_json), output_path=str(tmp_pdf))

                pdf_bytes = tmp_pdf.read_bytes()

            # Upload PDF to Supabase Storage
            pdf_url = self._upload_to_supabase_storage(pdf_filename, pdf_bytes, "application/pdf")

            draft.state = 'exported'

            return InteractiveChatResponse(
                message=self._random_response('contract_ready'),
                contract_draft=draft,
                pdf_path=pdf_url,
                action_taken="contract_ready"
            )
        except Exception as e:
            import logging
            import traceback
            logging.getLogger(__name__).error(
                f"Auto PDF generation failed: {e}\n{traceback.format_exc()}"
            )
            # Still mark as ready so user can retry with "xuất pdf"
            draft.state = 'ready'
            return InteractiveChatResponse(
                message=f"{self._random_response('contract_ready')}\n\n⚠️ Tạo PDF tự động thất bại. Bạn có thể thử lại bằng cách nói 'xuất pdf'.",
                contract_draft=draft,
                action_taken="contract_ready"
            )

    def _parse_command(self, user_input: str) -> Optional[AgentCommand]:
        """Parse user input for commands"""
        # Normalize Vietnamese text - remove diacritics for matching
        input_normalized = remove_diacritics(user_input.lower().strip())

        # Create contract command - more flexible matching
        create_patterns = [
            r'(?:tao|create|lap|lam)\s+(?:hop dong|contract)\s+(\w+)',
            r'(?:hop dong|contract)\s+(\w+)\s+(?:moi|new)',
            r'(?:tao|create|lap|lam)\s+(?:hop dong|contract)$',  # Without type
        ]
        for pattern in create_patterns:
            create_match = re.search(pattern, input_normalized)
            if create_match:
                # Check if we captured a type
                contract_type = create_match.group(1) if create_match.lastindex and create_match.lastindex >= 1 else None
                if contract_type:
                    return AgentCommand(
                        command='create_contract',
                        args={'type': contract_type},
                        original_text=user_input
                    )
                else:
                    # No type specified - ask user
                    return AgentCommand(
                        command='ask_contract_type',
                        args={},
                        original_text=user_input
                    )

        # Preview command - more keywords
        preview_keywords = ['xem truoc', 'preview', 'xem hop dong', 'mo hop dong',
                          'hien thi hop dong', 'show contract', 'view contract',
                          'xem trong trinh duyet', 'mo trinh duyet']
        if any(kw in input_normalized for kw in preview_keywords):
            return AgentCommand(command='preview', args={}, original_text=user_input)

        # Export PDF command
        if any(kw in input_normalized for kw in ['xuat pdf', 'export pdf', 'tao pdf', 'generate pdf', 'luu pdf', 'save pdf']):
            # Check for custom filename
            filename_match = re.search(r'(?:ten|filename|file)[:=]?\s*([^\s]+\.pdf)', input_normalized)
            filename = filename_match.group(1) if filename_match else None
            return AgentCommand(
                command='export_pdf',
                args={'filename': filename},
                original_text=user_input
            )

        # Edit field command
        edit_match = re.search(r'(?:sua|edit|thay doi|cap nhat)\s+(\w+)\s*[=:]\s*(.+)', input_normalized)
        if edit_match:
            return AgentCommand(
                command='edit_field',
                args={'field': edit_match.group(1), 'value': edit_match.group(2).strip()},
                original_text=user_input
            )

        # Research command
        if input_normalized.startswith('nghien cuu ') or input_normalized.startswith('research '):
            topic = user_input[11:].strip()
            return AgentCommand(
                command='research',
                args={'topic': topic},
                original_text=user_input
            )

        return None

    async def _handle_command(self, command: AgentCommand) -> InteractiveChatResponse:
        """Handle a parsed command"""
        session = self.get_session()

        if command.command == 'create_contract':
            return await self._create_contract(command.args['type'])

        elif command.command == 'ask_contract_type':
            # User wants to create contract but didn't specify type — build list from DB
            available = self._get_available_contract_types()
            if available:
                type_list = "\n".join(f"• {t['name']}" for t in available)
                msg = f"OK! Bạn muốn tạo loại hợp đồng nào?\n\n{type_list}\n\nNói tên loại hợp đồng nhé!"
            else:
                msg = "Hiện tại chưa có loại hợp đồng nào trong hệ thống. Vui lòng chạy seed-templates trước."
            return InteractiveChatResponse(
                message=msg,
                action_taken="ask_contract_type"
            )

        elif command.command == 'preview':
            return self._preview_contract(open_browser=not self.api_mode)

        elif command.command == 'export_pdf':
            return self._export_pdf(command.args.get('filename'))

        elif command.command == 'edit_field':
            return self._edit_field(command.args['field'], command.args['value'])

        elif command.command == 'show_contract':
            return self._show_contract()

        elif command.command == 'research':
            return await self._research_topic(command.args['topic'])

        return InteractiveChatResponse(
            message="Hmm, không hiểu lệnh này lắm. Bạn thử lại nhé!",
            action_taken="unknown_command"
        )

    def _detect_category_from_query(self, query: str) -> Optional[str]:
        """Detect legal category from query using keyword matching."""
        query_lower = query.lower()
        best_match = None
        best_score = 0
        for category, keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > best_score:
                best_score = score
                best_match = category
        return best_match if best_score > 0 else None

    def _check_data_for_query(self, query: str) -> Optional[str]:
        """Check if DB has data for the detected category. Returns friendly message if no data, None if data exists."""
        settings = get_settings()
        if settings.db_mode != "supabase":
            return None

        category = self._detect_category_from_query(query)
        if not category:
            return None  # Can't determine category, let LLM handle it

        try:
            from legal_chatbot.db.supabase import get_database
            db = get_database()
            all_cats = db.get_all_categories_with_stats()

            available = [
                {
                    "name": c["name"],
                    "display_name": c["display_name"],
                    "article_count": c.get("article_count", 0),
                }
                for c in all_cats
                if c.get("article_count", 0) > 0
            ]

            cat_stats = next((c for c in all_cats if c["name"] == category), None)
            if cat_stats and cat_stats.get("article_count", 0) > 0:
                return None  # Has data, proceed normally

            # No data for this category — build friendly message
            category_display = category.replace("_", " ")
            msg = f"Hiện tại mình chưa có dữ liệu về lĩnh vực **{category_display}** nên không thể tư vấn chính xác được."
            if available:
                cat_list = ", ".join(
                    f"{c['display_name']} ({c['article_count']} điều luật)"
                    for c in available
                )
                msg += f"\n\nMình có thể giúp bạn về: {cat_list}."
                msg += "\n\nBạn muốn hỏi về lĩnh vực nào?"
            return msg
        except Exception:
            return None  # On error, let LLM handle it

    async def _handle_natural_input(self, user_input: str) -> InteractiveChatResponse:
        """Handle natural language input - flexible for any legal topic"""
        session = self.get_session()
        # Normalize for comparison
        input_normalized = remove_diacritics(user_input.lower())

        # Check if user explicitly wants to CREATE a contract (not just asking about law)
        wants_contract = any(kw in input_normalized for kw in [
            'tao hop dong', 'lap hop dong', 'soan hop dong',
            'tao mau', 'viet hop dong', 'can hop dong',
            'muon tao hop dong', 'giup tao hop dong'
        ])

        # If user explicitly wants to create a contract, detect type and start flow
        if wants_contract and not session.current_draft:
            contract_type = await self._detect_contract_type_with_llm(user_input)
            if contract_type:
                return await self._create_contract(contract_type)

        # Check if DB has data for the topic before calling LLM
        no_data_msg = self._check_data_for_query(user_input)
        if no_data_msg:
            return InteractiveChatResponse(
                message=no_data_msg,
                action_taken="no_data"
            )

        # Build context for LLM response
        context = await self._build_context_for_query(user_input, session)

        # Generate response with LLM - using human-like prompt
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]

        # Add conversation history (last 6 messages, truncated to avoid token overflow)
        MAX_MSG_CHARS = 3000
        for msg in session.messages[-6:]:
            if msg['role'] in ['user', 'assistant']:
                content = msg['content']
                if len(content) > MAX_MSG_CHARS:
                    content = content[:MAX_MSG_CHARS] + "…(lược bớt)"
                messages.append({"role": msg['role'], "content": content})

        # Add context — structured format so LLM knows to cite specific articles
        if context:
            user_content = f"""CÁC ĐIỀU LUẬT LIÊN QUAN (từ cơ sở dữ liệu pháp luật):

{context}

---

CÂU HỎI CỦA NGƯỜI DÙNG:
{user_input}

Hãy trả lời CHI TIẾT dựa trên các điều luật ở trên. Trích dẫn cụ thể số Điều và tên văn bản."""
        else:
            user_content = user_input
        messages.append({"role": "user", "content": user_content})

        answer = call_llm_sonnet(messages, temperature=0.3, max_tokens=4096)

        result = InteractiveChatResponse(message=answer)

        # If we have a ready draft, add subtle reminder
        if session.current_draft and session.current_draft.state == 'ready':
            result.contract_draft = session.current_draft
            result.action_taken = "chat_with_draft"

        return result

    async def _build_llm_messages(self, user_input: str) -> list[dict] | None:
        """Build LLM messages with context for a legal question.

        Returns messages list ready for LLM, or None if handled by other flow
        (contract creation, greeting, etc.)
        """
        session = self.get_session()
        context = await self._build_context_for_query(user_input, session)

        messages = [{"role": "system", "content": self._build_system_prompt()}]

        # Truncate history messages to avoid token overflow
        MAX_MSG_CHARS = 3000
        for msg in session.messages[-6:]:
            if msg['role'] in ['user', 'assistant']:
                content = msg['content']
                if len(content) > MAX_MSG_CHARS:
                    content = content[:MAX_MSG_CHARS] + "…(lược bớt)"
                messages.append({"role": msg['role'], "content": content})

        if context:
            user_content = f"""CÁC ĐIỀU LUẬT LIÊN QUAN (từ cơ sở dữ liệu pháp luật):

{context}

---

CÂU HỎI CỦA NGƯỜI DÙNG:
{user_input}

Hãy trả lời CHI TIẾT dựa trên các điều luật ở trên. Trích dẫn cụ thể số Điều và tên văn bản."""
        else:
            user_content = user_input
        messages.append({"role": "user", "content": user_content})
        return messages

    async def stream_llm_response(self, messages: list[dict]):
        """Stream LLM response — uses Sonnet for accurate legal Q&A."""
        async for chunk in call_llm_stream_sonnet_async(messages, temperature=0.3, max_tokens=4096):
            yield chunk

    async def _detect_contract_type_with_llm(self, user_input: str) -> Optional[str]:
        """Use LLM to detect contract type from user input.

        Returns Vietnamese DB slug (e.g. 'cho_thue_nha') or None.
        """
        # Build dynamic prompt from DB templates
        available = self._get_available_contract_types()
        if not available:
            return None

        type_lines = "\n".join(
            f"- {t['type']}: {t['name']}"
            for t in available
        )
        valid_slugs = [t['type'] for t in available]

        system_prompt = f"""Bạn là trợ lý phân loại hợp đồng. Từ yêu cầu của người dùng, hãy xác định loại hợp đồng cần tạo.

Các loại hợp đồng hỗ trợ:
{type_lines}

Trả về CHỈ MỘT slug: {', '.join(valid_slugs)}
Nếu không xác định được, trả về: none"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]

        result = self._call_llm(messages, temperature=0.1, max_tokens=30)
        result = result.strip().lower()

        if result in valid_slugs:
            return result

        return None

    async def _build_context_for_query(self, user_input: str, session: ChatSession) -> str:
        """Build relevant context — tries vector search first, falls back to keyword.

        Priority:
        1. Vector search (ResearchService) — best quality, needs embedding model
        2. Keyword search (SQL ilike) — fallback for serverless (no embedding model)
        """
        input_normalized = remove_diacritics(user_input.lower())

        # Quick check: skip trivially short / greeting-like inputs
        _words = input_normalized.split()
        if len(_words) <= 3:
            _skip_patterns = [
                'ban la ai', 'ban la gi', 'ban khoe', 'xin chao', 'chao ban',
                'chao', 'cam on', 'hello', 'hi', 'hey', 'ok', 'bye',
            ]
            if any(input_normalized.startswith(p) or input_normalized == p for p in _skip_patterns):
                return ""

        # Check if this is a legal question that needs research
        # Use word-boundary aware matching to avoid false positives
        # (e.g. 'ban' matching in 'bạn là ai')

        # Multi-word phrases: safe to use substring match
        _phrase_keywords = [
            'dieu luat', 'quy dinh', 'phap ly', 'phap luat',
            'nghia vu', 'dieu kien', 'thu tuc', 'ho so',
            'la gi', 'nhu the nao', 'can gi', 'duoc khong',
            'lao dong', 'hop dong', 'chung nhan', 'giay phep',
            'dang ky', 'cap phep', 'tranh chap', 'boi thuong',
            'xu phat', 'hinh su', 'dan su', 'hanh chinh',
            'mua ban', 'cho thue', 'quyen su dung',
        ]
        # Single-word keywords: require word boundary (space-padded) to avoid
        # partial matches.  Only words that are unambiguously legal terms.
        # Ambiguous ones like 'ban', 'mua', 'nha' are handled as phrases above.
        _word_keywords = [
            'luat', 'quyen',
        ]

        is_legal_question = any(kw in input_normalized for kw in _phrase_keywords)
        if not is_legal_question:
            # Pad with spaces for word-boundary matching
            padded = f' {input_normalized} '
            is_legal_question = any(f' {kw} ' in padded for kw in _word_keywords)
        if not is_legal_question:
            return ""

        # 1. LLM-enhanced keyword search (primary — no embedding model needed)
        try:
            smart_terms = self._extract_search_terms_with_llm(user_input)
            if smart_terms:
                result = self._search_db_articles(user_input, llm_terms=smart_terms)
                if result:
                    return result
        except Exception:
            pass

        # 2. Basic keyword search fallback (no LLM)
        try:
            return self._search_db_articles(user_input)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"DB search error: {e}")
            return ""

    def _extract_search_terms_with_llm(self, query: str) -> list[str]:
        """Use LLM to extract targeted legal search phrases from user question.

        Cost: ~$0.001 per call (small prompt, short response).
        Returns 3-6 Vietnamese search phrases optimized for SQL ilike matching.
        """
        messages = [
            {"role": "system", "content": (
                "Từ câu hỏi pháp lý, trích xuất 3-6 cụm từ tìm kiếm ngắn (2-5 từ) "
                "để tìm điều luật liên quan trong cơ sở dữ liệu. "
                "Ưu tiên cụm từ pháp lý chính xác. Trả về JSON array. CHỈ JSON."
            )},
            {"role": "user", "content": query}
        ]
        result = call_llm_json(messages, temperature=0.1, max_tokens=150)
        if isinstance(result, list):
            return [str(t).lower().strip() for t in result if isinstance(t, str) and len(t) > 1]
        return []

    def _build_search_terms(self, query: str) -> list[str]:
        """Build Vietnamese n-gram search terms from query — NO LLM call.

        Generates compound terms (2-4 words) that preserve Vietnamese
        phrasing like "giấy chứng nhận", "quyền sử dụng đất", "không có giấy tờ".

        Stop words are kept INSIDE n-grams (for accurate phrase matching)
        but filtered as standalone search terms.
        """
        words = query.lower().split()
        # Remove punctuation from words
        words = [w.strip('.,?!;:()[]{}"\'-') for w in words if w.strip('.,?!;:()[]{}"\'-')]

        if not words:
            return []

        # Stop words — only used to filter STANDALONE terms, not inside n-grams
        stop_words = {
            'là', 'gì', 'của', 'và', 'trong', 'cho', 'như', 'thế', 'nào',
            'có', 'không', 'được', 'phải', 'cần', 'bao', 'nhiều', 'một',
            'các', 'những', 'này', 'đó', 'khi', 'nếu', 'thì', 'sẽ', 'đã',
            'đang', 'từ', 'đến', 'với', 'tại', 'về', 'theo', 'bằng',
            'để', 'mà', 'hay', 'hoặc', 'vì', 'sao', 'tôi', 'bạn',
        }

        # Build n-grams per length — ensure a MIX of term lengths
        # Long queries would otherwise fill all slots with 4-grams,
        # missing useful shorter terms like "thông báo", "thu hồi đất"
        seen = set()
        by_length: dict[int, list[str]] = {4: [], 3: [], 2: []}
        for n in [4, 3, 2]:
            for i in range(len(words) - n + 1):
                gram = " ".join(words[i:i + n])
                has_meaningful = any(w not in stop_words for w in words[i:i + n])
                if has_meaningful and gram not in seen:
                    seen.add(gram)
                    by_length[n].append(gram)

        # 3-grams = sweet spot (specific enough, good recall)
        # Take ALL 3-grams, supplement with 2-grams and 4-grams
        result = by_length[3] + by_length[2][:8] + by_length[4][:4]
        return result[:20]

    def _search_db_articles(self, query: str, limit: int = 20, llm_terms: list[str] | None = None) -> str:
        """Keyword search with optional LLM-generated terms.

        Uses Supabase or_() to combine all search terms into 2 queries:
        1 title query + 1 content query. Title matches score 3x.

        Args:
            llm_terms: If provided, uses these instead of n-gram terms.
        """
        settings = get_settings()
        if settings.db_mode != "supabase":
            return ""

        from legal_chatbot.db.supabase import get_database

        db = get_database()
        client = db._read()

        # Step 1: Use LLM terms if provided, otherwise fall back to n-grams
        search_terms = llm_terms if llm_terms else self._build_search_terms(query)
        if not search_terms:
            return ""

        # Step 2: Batch into 2 queries using or_()
        article_scores: dict[tuple, dict] = {}

        # Query 1: Title search (all terms combined) — score 3x
        title_or = ",".join(f"title.ilike.%{t}%" for t in search_terms)
        try:
            title_result = (
                client.table("articles")
                .select("article_number, title, content, legal_documents(title, document_number)")
                .or_(title_or)
                .limit(100)
                .execute()
            )
            for a in title_result.data or []:
                doc_info = a.get("legal_documents") or {}
                art_key = (a.get("article_number"), doc_info.get("title", ""))
                if art_key not in article_scores:
                    article_scores[art_key] = {"data": a, "doc_info": doc_info, "score": 0}
                # Score by how many terms match the title
                art_title = (a.get("title") or "").lower()
                for t in search_terms:
                    if t in art_title:
                        article_scores[art_key]["score"] += 3
        except Exception:
            pass

        # Query 2: Content search (all terms combined) — score 1x
        content_or = ",".join(f"content.ilike.%{t}%" for t in search_terms[:8])
        try:
            content_result = (
                client.table("articles")
                .select("article_number, title, content, legal_documents(title, document_number)")
                .or_(content_or)
                .limit(200)
                .execute()
            )
            for a in content_result.data or []:
                doc_info = a.get("legal_documents") or {}
                art_key = (a.get("article_number"), doc_info.get("title", ""))
                if art_key not in article_scores:
                    article_scores[art_key] = {"data": a, "doc_info": doc_info, "score": 0}
                # Score by how many terms match the content
                art_content = (a.get("content") or "").lower()
                for t in search_terms:
                    if t in art_content:
                        article_scores[art_key]["score"] += 1
        except Exception:
            pass

        if not article_scores:
            return ""

        # Step 3: Rank by score DESC
        ranked = sorted(
            article_scores.values(),
            key=lambda x: x["score"],
            reverse=True,
        )[:limit]

        # Step 4: Format results
        # Keep articles generous — they're the primary source for legal Q&A.
        # Token overflow is mainly caused by conversation history, not articles.
        MAX_ARTICLE_CHARS = 3000
        MAX_TOTAL_CHARS = 120_000
        results = []
        total_chars = 0
        for item in ranked:
            a = item["data"]
            doc_info = item["doc_info"]
            content = a.get("content", "")
            if len(content) > MAX_ARTICLE_CHARS:
                content = content[:MAX_ARTICLE_CHARS] + "…(lược bớt)"
            header = f"Điều {a.get('article_number', '?')}"
            title = a.get("title", "")
            if title:
                header += f": {title}"
            doc_title = doc_info.get("title", "")
            entry = f"**{header}** ({doc_title})\n{content}"
            total_chars += len(entry)
            if total_chars > MAX_TOTAL_CHARS:
                break
            results.append(entry)

        return "\n\n---\n\n".join(results)

    def _get_flexible_system_prompt(self, session: ChatSession) -> str:
        """Get flexible system prompt that handles any legal topic"""
        base_prompt = """Bạn là trợ lý pháp lý Việt Nam thông minh. Bạn có thể:

1. TRẢ LỜI bất kỳ câu hỏi pháp lý nào (luật dân sự, hình sự, lao động, đất đai, kinh doanh, v.v.)
2. TẠO hợp đồng khi người dùng yêu cầu (nói "tạo hợp đồng [loại]")
3. CHỈNH SỬA hợp đồng theo yêu cầu
4. XUẤT hợp đồng ra PDF

Khi trả lời câu hỏi pháp lý:
- Cung cấp thông tin chính xác dựa trên pháp luật Việt Nam
- Trích dẫn điều luật cụ thể nếu có
- Giải thích rõ ràng, dễ hiểu

Khi tạo hợp đồng:
- Xác định loại hợp đồng phù hợp
- Hướng dẫn người dùng cung cấp thông tin cần thiết
- Cho phép xem trước và xuất PDF

Các lệnh:
- "tạo hợp đồng [loại]" - Tạo hợp đồng mới
- "xem hợp đồng" / "preview" - Xem trước trong trình duyệt
- "xuất pdf" - Xuất file PDF
- "sửa [trường] = [giá trị]" - Cập nhật thông tin

Lưu ý: Đây chỉ là thông tin tham khảo, không thay thế tư vấn pháp lý chuyên nghiệp."""

        if session.current_draft:
            draft = session.current_draft
            filled_fields = "\n".join([f"- {k}: {v}" for k, v in draft.field_values.items()])
            unfilled = [f.label for f in draft.template.fields if f.name not in draft.field_values and f.required]

            base_prompt += f"""

---
HỢP ĐỒNG ĐANG SOẠN: {draft.template.name}
Đã điền: {len(draft.field_values)}/{len(draft.template.fields)} trường
{f'Thông tin: {chr(10)}{filled_fields}' if filled_fields else ''}
{f'Chưa điền: {", ".join(unfilled)}' if unfilled else 'Đã đầy đủ thông tin!'}
---"""

        return base_prompt

    def _detect_contract_type(self, input_lower: str, session: ChatSession) -> Optional[str]:
        """Detect contract type from input and conversation history"""
        # Check current input
        if any(kw in input_lower for kw in ['xe may', 'o to', 'xe', 'mua ban xe']):
            return 'sale'
        if any(kw in input_lower for kw in ['mua ban', 'ban', 'mua']):
            return 'sale'
        if any(kw in input_lower for kw in ['thue nha', 'cho thue', 'thue phong']):
            return 'rental'
        if any(kw in input_lower for kw in ['dich vu', 'cung cap']):
            return 'service'
        if any(kw in input_lower for kw in ['lao dong', 'tuyen dung', 'nhan vien']):
            return 'employment'

        # Check conversation history
        for msg in reversed(session.messages[-10:]):
            content = msg.get('content', '').lower()
            if 'xe may' in content or 'mua ban' in content:
                return 'sale'
            if 'thue' in content:
                return 'rental'
            if 'dich vu' in content:
                return 'service'

        return None

    async def _auto_create_contract(self, contract_type: str, user_input: str) -> None:
        """Auto-create a contract draft based on detected type"""
        session = self.get_session()

        # Resolve to Vietnamese DB slug
        resolved = self._resolve_contract_type(
            remove_diacritics(contract_type.lower().strip())
        ) or contract_type

        try:
            template = self._load_template_from_db(resolved)
            draft = ContractDraft(
                id=str(uuid4()),
                contract_type=resolved,
                template=template,
                field_values={},
                legal_basis=template.legal_references
            )
            session.current_draft = draft
        except Exception as e:
            print(f"Error auto-creating contract: {e}")

    async def _extract_fields_from_text(self, text: str, draft: ContractDraft) -> dict:
        """Use LLM to extract field values from natural language text"""
        field_names = [f.name for f in draft.template.fields]
        field_labels = {f.name: f.label for f in draft.template.fields}

        system_prompt = """Bạn là trợ lý trích xuất thông tin. Từ văn bản người dùng cung cấp,
hãy trích xuất các trường thông tin hợp đồng.

Trả về JSON với format:
{"field_name": "giá trị", ...}

Chỉ trả về các trường có thông tin rõ ràng trong văn bản.
Nếu không tìm thấy, trả về {}"""

        fields_info = "\n".join([f"- {name}: {label}" for name, label in field_labels.items()])

        user_prompt = f"""CÁC TRƯỜNG CẦN TRÍCH XUẤT:
{fields_info}

VĂN BẢN:
{text}

Hãy trích xuất thông tin và trả về JSON."""

        try:
            extracted = call_llm_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500,
            )

            if not isinstance(extracted, dict):
                return {}

            # Filter to only valid fields
            return {k: v for k, v in extracted.items() if k in field_names and v}

        except Exception as e:
            print(f"Error extracting fields: {e}")
            return {}

    def _get_enhanced_system_prompt(self, session: ChatSession) -> str:
        """Get enhanced system prompt based on session state"""
        base_prompt = self._build_system_prompt()

        if session.current_draft:
            draft = session.current_draft
            filled_fields = "\n".join([
                f"- {k}: {v}" for k, v in draft.field_values.items()
            ])
            unfilled_fields = [
                f.label for f in draft.template.fields
                if f.name not in draft.field_values and f.required
            ]

            base_prompt += f"""

THÔNG TIN HỢP ĐỒNG HIỆN TẠI:
Loại: {draft.template.name}
Các trường đã điền:
{filled_fields if filled_fields else '(chưa có)'}

Các trường cần điền:
{', '.join(unfilled_fields) if unfilled_fields else '(đã đầy đủ)'}

Khi người dùng cung cấp thông tin, hãy xác nhận và ghi nhận.
Khi người dùng muốn xem hợp đồng, hãy hướng dẫn họ nói 'xem hợp đồng' để mở trong trình duyệt."""

        return base_prompt

    async def _create_contract(self, contract_type: str) -> InteractiveChatResponse:
        """Create a new contract draft and start step-by-step collection.

        Args:
            contract_type: Vietnamese slug (e.g. 'cho_thue_nha') or user input text.
        """
        session = self.get_session()

        # Resolve to Vietnamese DB slug (DB + LLM, fully dynamic)
        resolved_slug = await self._resolve_contract_type(contract_type)
        if not resolved_slug:
            raise ValueError(f"Không nhận diện được loại hợp đồng: {contract_type}")

        try:
            # Load template from Supabase (no hardcoded fallback)
            template = self._load_template_from_db(resolved_slug)

            # Create draft with collecting state
            draft = ContractDraft(
                id=str(uuid4()),
                contract_type=resolved_slug,
                template=template,
                field_values={},
                legal_basis=template.legal_references,
                current_field_index=0,
                state='collecting'
            )
            session.current_draft = draft
            session.mode = 'contract_creation'

            # Get Vietnamese type name from template (DB display_name)
            type_name = template.name

            # Get first required field
            required_fields = [f for f in template.fields if f.required]
            if required_fields:
                first_field = required_fields[0]
                intro = self._random_response('contract_start', type=type_name)
                question = self._random_response('field_ask', label=first_field.label.lower())
                message = f"{intro}\n\n{question}"
            else:
                # No required fields (unlikely)
                draft.state = 'ready'
                session.mode = 'normal'
                message = self._random_response('contract_ready')

            return InteractiveChatResponse(
                message=message,
                contract_draft=draft,
                action_taken="contract_created"
            )

        except ValueError as e:
            # Build dynamic error message from DB
            available = self._get_available_contract_types()
            if available:
                type_list = ", ".join(t["name"] for t in available)
                msg = f"Hmm, chưa hỗ trợ loại hợp đồng này. Hiện tại mình có: {type_list} nhé!"
            else:
                msg = "Hiện tại chưa có loại hợp đồng nào trong hệ thống."
            return InteractiveChatResponse(
                message=msg,
                action_taken="error"
            )

    def _preview_contract(self, open_browser: bool = True) -> InteractiveChatResponse:
        """Generate HTML preview of current contract"""
        session = self.get_session()

        if not session.current_draft:
            return InteractiveChatResponse(
                message=self._random_response('missing_contract'),
                action_taken="no_contract"
            )

        draft = session.current_draft

        # Generate articles if not already done (for richer preview)
        if not draft.articles and draft.state == 'ready':
            draft.articles = self._generate_articles_with_llm(draft)

        html = self._generate_html_preview(draft)

        if open_browser:
            # Save to temp file and open in browser (CLI mode)
            temp_dir = Path(tempfile.gettempdir())
            html_path = temp_dir / f"contract_preview_{draft.id[:8]}.html"

            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(html)

            webbrowser.open(f'file://{html_path}')

        return InteractiveChatResponse(
            message=self._random_response('preview_opened'),
            html_preview=html,
            action_taken="preview_opened"
        )

    def _generate_html_preview(self, draft: ContractDraft) -> str:
        """Generate HTML preview of contract with detailed legal basis"""
        template = draft.template
        values = draft.field_values

        # Build field rows
        field_rows = ""
        for field in template.fields:
            value = values.get(field.name, '________________')
            required = ' <span style="color: red;">*</span>' if field.required else ''
            field_rows += f"""
            <tr>
                <td style="padding: 8px; border: 1px solid #ddd;"><strong>{field.label}</strong>{required}</td>
                <td style="padding: 8px; border: 1px solid #ddd;">{value}</td>
            </tr>
            """

        # Build detailed legal articles section
        legal_articles_html = ""
        if template.legal_articles:
            for article in template.legal_articles:
                # Format content with proper line breaks
                content_formatted = article.content.replace('\n', '<br>')
                legal_articles_html += f"""
                <div class="legal-article">
                    <div class="article-header">
                        <strong>Dieu {article.article_number}: {article.article_title}</strong>
                        <span class="document-name">({article.document_name})</span>
                    </div>
                    <div class="article-summary">
                        <em>Tóm tắt: {article.summary}</em>
                    </div>
                    <div class="article-content">
                        {content_formatted}
                    </div>
                </div>
                """
        else:
            # Fallback to simple references
            legal_articles_html = "<br>".join([f"- {ref}" for ref in template.legal_references])

        # Build key terms
        key_terms = "<br>".join([f"- {term}" for term in template.key_terms])

        html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <title>Xem trước: {template.name}</title>
    <style>
        body {{ font-family: 'Times New Roman', serif; max-width: 900px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .title {{ font-size: 24px; font-weight: bold; margin: 20px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}

        /* Legal basis section */
        .legal-basis-section {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 20px;
            margin: 25px 0;
        }}
        .legal-basis-section h3 {{
            color: #1a5f7a;
            margin-top: 0;
            border-bottom: 2px solid #1a5f7a;
            padding-bottom: 10px;
        }}
        .legal-article {{
            background: white;
            border: 1px solid #e0e0e0;
            border-left: 4px solid #1a5f7a;
            padding: 15px;
            margin: 15px 0;
            border-radius: 4px;
        }}
        .article-header {{
            color: #1a5f7a;
            font-size: 16px;
            margin-bottom: 8px;
        }}
        .document-name {{
            font-size: 12px;
            color: #666;
            display: block;
            margin-top: 4px;
        }}
        .article-summary {{
            background: #e8f4f8;
            padding: 8px 12px;
            border-radius: 4px;
            margin: 10px 0;
            font-size: 14px;
            color: #555;
        }}
        .article-content {{
            font-size: 14px;
            color: #333;
            padding: 10px;
            background: #fafafa;
            border-radius: 4px;
        }}

        /* Contract info section */
        .contract-info {{
            background: #fff;
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 20px;
            margin: 25px 0;
        }}
        .contract-info h3 {{
            color: #2c5530;
            margin-top: 0;
        }}

        .key-terms {{
            background: #e8f5e9;
            border: 1px solid #c8e6c9;
            padding: 15px;
            margin: 20px 0;
            border-radius: 8px;
        }}
        .key-terms h4 {{
            color: #2e7d32;
            margin-top: 0;
        }}

        .disclaimer {{
            color: #666;
            font-size: 12px;
            margin-top: 30px;
            padding: 15px;
            border: 1px dashed #ccc;
            border-radius: 5px;
            background: #fff9e6;
        }}
        .signature {{ display: flex; justify-content: space-between; margin-top: 50px; }}
        .signature-box {{ width: 45%; text-align: center; }}

        @media print {{
            .legal-basis-section {{ page-break-inside: avoid; }}
            .legal-article {{ page-break-inside: avoid; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div>CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</div>
        <div><strong>Độc lập - Tự do - Hạnh phúc</strong></div>
        <div>---oOo---</div>
    </div>

    <div class="title" style="text-align: center;">
        {template.name.upper()}
    </div>

    <p><em>{template.description}</em></p>

    <!-- DETAILED LEGAL BASIS SECTION -->
    <div class="legal-basis-section">
        <h3>CƠ SỞ PHÁP LÝ</h3>
        <p><em>Hợp đồng này được lập dựa trên các quy định pháp luật sau:</em></p>
        {legal_articles_html}
    </div>

    <!-- CONTRACT INFORMATION -->
    <div class="contract-info">
        <h3>THÔNG TIN HỢP ĐỒNG</h3>
        <table>
            {field_rows}
        </table>
    </div>

    <!-- GENERATED CONTRACT ARTICLES -->
    {self._build_articles_html(draft)}

    <!-- KEY TERMS -->
    <div class="key-terms">
        <h4>CÁC ĐIỀU KHOẢN QUAN TRỌNG THEO QUY ĐỊNH PHÁP LUẬT:</h4>
        {key_terms}
    </div>

    <!-- SIGNATURES -->
    <div class="signature">
        <div class="signature-box">
            <strong>BÊN A</strong><br>
            (Ký và ghi rõ họ tên)<br><br><br><br>
        </div>
        <div class="signature-box">
            <strong>BÊN B</strong><br>
            (Ký và ghi rõ họ tên)<br><br><br><br>
        </div>
    </div>

    <div class="disclaimer">
        <strong>Lưu ý:</strong> Đây chỉ là bản xem trước mang tính chất tham khảo.
        Các điều khoản pháp lý được trích dẫn từ các văn bản pháp luật hiện hành.
        Vui lòng kiểm tra kỹ thông tin trước khi xuất PDF chính thức.
        <strong>Không thay thế tư vấn pháp lý chuyên nghiệp.</strong>
    </div>

    <script>
        // Auto-print option
        // window.print();
    </script>
</body>
</html>"""

        return html

    def _build_articles_html(self, draft: ContractDraft) -> str:
        """Build HTML for generated contract articles (ĐIỀU 1-9)."""
        if not draft.articles:
            return ""

        html = '<div style="margin: 25px 0;">\n'
        html += '<h3 style="color: #1a5f7a; border-bottom: 2px solid #1a5f7a; padding-bottom: 10px;">NỘI DUNG HỢP ĐỒNG</h3>\n'

        for article in draft.articles:
            title = article.get('title', '')
            content_items = article.get('content', [])
            html += f'<div style="margin: 15px 0;">\n'
            html += f'<h4 style="color: #1a5f7a; margin-bottom: 8px;">{title}</h4>\n'
            for item in content_items:
                html += f'<p style="margin: 4px 0 4px 20px; text-align: justify;">{item}</p>\n'
            html += '</div>\n'

        html += '</div>\n'
        return html

    def _group_fields(self, draft: ContractDraft) -> dict:
        """Group flat field_values into sections using field_groups from DB template.

        Reads field_groups and common_groups from DynamicTemplate (loaded from Supabase).
        """
        groups = {}
        field_labels = {f.name: f.label for f in draft.template.fields}
        assigned = set()

        # Type-specific groups from template (loaded from DB required_fields.field_groups)
        for group_def in draft.template.field_groups:
            prefix = group_def.get("prefix", "")
            section_key = group_def.get("key", prefix.rstrip("_"))
            section_label = group_def.get("label", section_key.upper())

            for field_name, value in draft.field_values.items():
                if field_name.startswith(prefix) and field_name not in assigned:
                    if section_key not in groups:
                        groups[section_key] = {'_label': section_label}
                    short_key = field_name[len(prefix):] if field_name.startswith(prefix) else field_name
                    groups[section_key][short_key] = {
                        'value': value,
                        'label': field_labels.get(field_name, field_name)
                    }
                    assigned.add(field_name)

        # Common groups from template (loaded from DB required_fields.common_groups)
        for group_def in draft.template.common_groups:
            prefix = group_def.get("prefix", "")
            section_key = group_def.get("key", prefix.rstrip("_"))
            section_label = group_def.get("label", section_key.upper())

            for field_name, value in draft.field_values.items():
                if field_name.startswith(prefix) and field_name not in assigned:
                    if section_key not in groups:
                        groups[section_key] = {'_label': section_label}
                    groups[section_key][field_name] = {
                        'value': value,
                        'label': field_labels.get(field_name, field_name)
                    }
                    assigned.add(field_name)

        # Remaining unassigned fields → "THÔNG TIN KHÁC"
        for field_name, value in draft.field_values.items():
            if field_name not in assigned:
                if 'thong_tin_khac' not in groups:
                    groups['thong_tin_khac'] = {'_label': 'THÔNG TIN KHÁC'}
                groups['thong_tin_khac'][field_name] = {
                    'value': value,
                    'label': field_labels.get(field_name, field_name)
                }

        return groups

    def _generate_articles_with_llm(self, draft: ContractDraft) -> list[dict]:
        """Generate contract articles (ĐIỀU 1-9) using LLM based on template and field values."""

        contract_type_vn = draft.template.name if draft.template else 'Hợp đồng'
        legal_refs = ', '.join(draft.legal_basis) if draft.legal_basis else 'Bộ luật Dân sự 2015'

        # Build field summary for the LLM
        field_summary = []
        for field in draft.template.fields:
            val = draft.field_values.get(field.name)
            if val:
                field_summary.append(f"- {field.label}: {val}")
        fields_text = '\n'.join(field_summary)

        # Build legal articles context from template
        legal_context = ""
        if draft.template.legal_articles:
            for art in draft.template.legal_articles:
                legal_context += f"\n- Điều {art.article_number} ({art.document_name}): {art.content[:200]}"

        system_prompt = """Bạn là chuyên gia soạn thảo hợp đồng pháp lý Việt Nam. Nhiệm vụ: tạo các ĐIỀU khoản cho hợp đồng.

QUY TẮC:
- Tạo đúng 9 ĐIỀU (articles)
- Mỗi ĐIỀU có title (ví dụ: "ĐIỀU 1: ĐỐI TƯỢNG CỦA HỢP ĐỒNG") và content (mảng các khoản)
- Nội dung phải cụ thể, chi tiết, trích dẫn luật khi cần
- Sử dụng thông tin các bên và tài sản đã cung cấp
- Trả về JSON array, KHÔNG có text nào khác

FORMAT:
[
  {"title": "ĐIỀU 1: ĐỐI TƯỢNG CỦA HỢP ĐỒNG", "content": ["1.1. ...", "1.2. ..."]},
  {"title": "ĐIỀU 2: GIÁ VÀ PHƯƠNG THỨC THANH TOÁN", "content": ["2.1. ...", "2.2. ..."]},
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
9. Điều khoản chung"""

        user_prompt = f"""Tạo 9 ĐIỀU cho {contract_type_vn}.

CĂN CỨ PHÁP LÝ: {legal_refs}
{f"ĐIỀU LUẬT THAM KHẢO:{legal_context}" if legal_context else ""}

THÔNG TIN HỢP ĐỒNG:
{fields_text}

Trả về JSON array (9 articles). CHỈ JSON, không có text giải thích."""

        try:
            result = call_llm_sonnet(
                [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=4000
            )

            # Parse JSON from response
            result = result.strip()
            if result.startswith('```'):
                result = result.split('```')[1]
                if result.startswith('json'):
                    result = result[4:]
                result = result.strip()
            articles = json.loads(result)
            if isinstance(articles, list) and len(articles) > 0:
                return articles
        except Exception as e:
            print(f"Error generating articles: {e}")

        return []

    def _upload_to_supabase_storage(self, filename: str, content: bytes, content_type: str) -> Optional[str]:
        """Upload file to Supabase Storage, return filename (not signed URL).

        Returns just the filename so it can be served via /api/files/{filename}
        which generates fresh signed URLs on demand (never expires).
        """
        settings = get_settings()
        if settings.db_mode != "supabase":
            return None
        try:
            from legal_chatbot.db.supabase import get_database
            db = get_database()
            db.upload_contract_file(filename, content, content_type)
            return filename  # Return filename, not signed URL
        except Exception as e:
            print(f"Supabase Storage upload failed: {e}")
            return None

    def _build_contract_json(self, draft: ContractDraft) -> tuple[str, bytes]:
        """Build complete contract JSON, upload to Supabase, return (filename, bytes).

        Uses temp file for PDF generation, does NOT persist locally.
        """
        # Generate articles if not already done
        if not draft.articles:
            draft.articles = self._generate_articles_with_llm(draft)

        contract_type_vn = draft.template.name if draft.template else 'Hợp đồng'

        # Build legal_references in proper format
        legal_references = []
        if draft.template and draft.template.legal_articles:
            for art in draft.template.legal_articles:
                legal_references.append({
                    'article': f'Điều {art.article_number}',
                    'law': art.document_name,
                    'description': art.summary or art.article_title,
                })
        elif draft.legal_basis:
            for ref in draft.legal_basis:
                legal_references.append({'article': ref, 'law': '', 'description': ''})

        # Build the complete contract JSON
        contract_data = {
            'contract_type': draft.contract_type,
            'contract_type_vn': contract_type_vn,
            'created_at': datetime.now().isoformat(),
            'status': 'draft',
            'legal_references': legal_references,
            'fields': self._group_fields(draft),
            'articles': draft.articles,
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_filename = f"{draft.contract_type}_{timestamp}.json"
        json_bytes = json.dumps(contract_data, ensure_ascii=False, indent=2).encode('utf-8')

        # Upload JSON to Supabase Storage
        self._upload_to_supabase_storage(json_filename, json_bytes, "application/json")

        return json_filename, json_bytes

    def _export_pdf(self, filename: Optional[str] = None) -> InteractiveChatResponse:
        """Export current contract to PDF — Supabase Storage only, no local files."""
        session = self.get_session()

        if not session.current_draft:
            return InteractiveChatResponse(
                message=self._random_response('missing_contract'),
                action_taken="no_contract"
            )

        draft = session.current_draft

        try:
            json_filename, json_bytes = self._build_contract_json(draft)
            pdf_filename = filename or json_filename.replace('.json', '.pdf')

            # Temp files for PDF generation → upload → clean up
            with tempfile.TemporaryDirectory() as tmp_dir:
                tmp_json = Path(tmp_dir) / json_filename
                tmp_pdf = Path(tmp_dir) / pdf_filename

                tmp_json.write_bytes(json_bytes)

                pdf_gen = UniversalPDFGenerator()
                pdf_gen.generate(contract_path=str(tmp_json), output_path=str(tmp_pdf))

                pdf_bytes = tmp_pdf.read_bytes()

            # Upload to Supabase Storage
            pdf_url = self._upload_to_supabase_storage(pdf_filename, pdf_bytes, "application/pdf")

            draft.state = 'exported'

            return InteractiveChatResponse(
                message=self._random_response('pdf_success'),
                pdf_path=pdf_url,
                action_taken="pdf_exported"
            )

        except Exception as e:
            return InteractiveChatResponse(
                message=f"Ui, có lỗi khi xuất PDF: {e}. Thử lại nhé!",
                action_taken="error"
            )

    def _edit_field(self, field_name: str, value: str) -> InteractiveChatResponse:
        """Edit a field in the current contract draft"""
        session = self.get_session()

        if not session.current_draft:
            return InteractiveChatResponse(
                message=self._random_response('missing_contract'),
                action_taken="no_contract"
            )

        draft = session.current_draft

        # Find matching field
        field_names = [f.name for f in draft.template.fields]
        field_labels = {f.label.lower(): f.name for f in draft.template.fields}

        actual_name = None

        # Try exact match first
        if field_name in field_names:
            actual_name = field_name
        # Try label match
        elif field_name.lower() in field_labels:
            actual_name = field_labels[field_name.lower()]
        else:
            # Try partial match
            for name in field_names:
                if field_name.lower() in name.lower():
                    actual_name = name
                    break

        if actual_name:
            draft.field_values[actual_name] = value
            draft.last_modified = datetime.now()
            return InteractiveChatResponse(
                message=f"OK, đã sửa {actual_name} thành \"{value}\" rồi!",
                contract_draft=draft,
                action_taken="field_updated"
            )

        return InteractiveChatResponse(
            message=f"Hmm, không tìm thấy trường '{field_name}'. Thử: {', '.join(field_names[:3])}...",
            action_taken="field_not_found"
        )

    def _show_contract(self) -> InteractiveChatResponse:
        """Show brief contract status - redirect to web for full view"""
        session = self.get_session()

        if not session.current_draft:
            return InteractiveChatResponse(
                message=self._random_response('missing_contract'),
                action_taken="no_contract"
            )

        draft = session.current_draft
        type_name = draft.template.name if draft.template else draft.contract_type

        # Just show brief status
        filled_count = len(draft.field_values)
        required_fields = [f for f in draft.template.fields if f.required]
        total_required = len(required_fields)

        # Check what's missing
        missing = [f.label for f in required_fields if f.name not in draft.field_values]

        if missing:
            status_msg = f"Hợp đồng {type_name}: {filled_count}/{total_required} trường bắt buộc đã điền."
            if len(missing) <= 3:
                status_msg += f"\nCòn thiếu: {', '.join(missing)}"
            status_msg += "\n\nNói 'xem hợp đồng' để xem chi tiết trên web!"
        else:
            status_msg = f"Hợp đồng {type_name} đã đủ thông tin rồi! Nói 'xem hợp đồng' để xem trước, hoặc 'xuất pdf' để tải về."

        return InteractiveChatResponse(
            message=status_msg,
            contract_draft=draft,
            action_taken="contract_status"
        )

    async def _research_topic(self, topic: str) -> InteractiveChatResponse:
        """Research a specific legal topic"""
        result = await self.research_service.research(topic, max_sources=3)

        message = f"""KẾT QUẢ NGHIÊN CỨU: {topic}

{result.analyzed_content}

Nguồn tham khảo: {len(result.crawled_sources)} văn bản
"""

        if result.legal_articles:
            message += f"\nCác điều luật liên quan: {len(result.legal_articles)} điều"

        if result.suggested_contract_type:
            message += f"\n\n[Gợi ý: Bạn có thể tạo hợp đồng {result.suggested_contract_type}]"

        return InteractiveChatResponse(
            message=message,
            action_taken="research_completed"
        )


# Singleton instance
_interactive_service: Optional[InteractiveChatService] = None


def get_interactive_chat_service() -> InteractiveChatService:
    """Get or create interactive chat service singleton"""
    global _interactive_service
    if _interactive_service is None:
        _interactive_service = InteractiveChatService()
    return _interactive_service
