"""Interactive chat service with session state and contract management"""

import asyncio
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
from legal_chatbot.utils.vietnamese import remove_diacritics
from legal_chatbot.services.research import ResearchService, ResearchResult
from legal_chatbot.services.dynamic_template import DynamicTemplateGenerator, DynamicTemplate
from legal_chatbot.services.generator import GeneratorService


def get_llm_client():
    """Get LLM client based on configuration"""
    settings = get_settings()

    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        from anthropic import Anthropic
        return Anthropic(api_key=settings.anthropic_api_key), "anthropic", settings.llm_model
    elif settings.groq_api_key:
        from groq import Groq
        return Groq(api_key=settings.groq_api_key), "groq", settings.llm_model
    else:
        return None, None, None


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

    # Human-like system prompt - conversational, friendly, natural
    SYSTEM_PROMPT = """Ban la mot chuyen vien tu van phap ly nhiet tinh va than thien. Hay noi chuyen tu nhien nhu mot nguoi that, khong qua trang trong hay may moc.

PHONG CACH GIAO TIEP:
- Noi ngan gon, di thang vao van de
- Dung ngon ngu binh thuong, de hieu, tranh tu ngu qua chuyen mon
- Co the dung cau cam than, cau hoi de tao su gan gui
- Khong liet ke dai dong, chi noi nhung gi can thiet
- The hien su dong cam khi nguoi dung gap van de

VI DU CACH TRA LOI:
- Thay vi: "Theo quy dinh tai Dieu 121 Luat Nha o 2014..."
- Hay noi: "A, viec nay thi theo Luat Nha o 2014 quy dinh kha ro ne. Cu the la..."

- Thay vi: "Toi se giup ban tao hop dong. Cac truong can dien bao gom: 1. Ten ben A, 2. Dia chi..."
- Hay noi: "OK, minh lam hop dong nhe! Cho minh hoi, ben cho thue ten gi?"

NGUYEN TAC:
1. Tra loi dua tren nghien cuu tu thu vien phap luat, nhung dien dat don gian
2. Khi tao hop dong, HOI TUNG THONG TIN MOT, khong liet ke het cac truong
3. Khong show noi dung hop dong trong chat - chi show khi xem tren web
4. Chu dong goi y buoc tiep theo

Luu y: Day chi la tham khao, khong thay the tu van phap ly chuyen nghiep."""

    # Human-like responses for various situations
    HUMAN_RESPONSES = {
        'greeting': [
            "Chao ban! Minh co the giup gi cho ban?",
            "Hey! Ban can tu van ve van de gi?",
            "Chao! Hom nay ban can ho tro gi ne?",
        ],
        'contract_start': [
            "OK, minh se giup ban lam hop dong {type}. De bat dau, cho minh hoi nhe:",
            "Duoc roi, lam hop dong {type} ha. Minh can hoi ban vai thong tin:",
            "Hop dong {type} nhe! De minh hoi tung cai mot cho de:",
        ],
        'field_ask': [
            "{label} la gi?",
            "Cho minh biet {label} nhe?",
            "{label}?",
            "Tiep theo, {label} la gi?",
        ],
        'field_confirm': [
            "OK, ghi nhan roi!",
            "Duoc roi!",
            "Noted!",
            "Da luu!",
        ],
        'contract_ready': [
            "Xong roi! Ban co the noi 'xem hop dong' de xem truoc, hoac 'xuat pdf' de tai ve.",
            "Da du thong tin roi! Noi 'xem hop dong' de xem truoc tren web nhe.",
            "OK, hop dong da san sang. Ban muon xem truoc hay xuat pdf luon?",
        ],
        'missing_contract': [
            "Chua co hop dong nao ne. Ban muon tao loai hop dong gi?",
            "Hic, chua tao hop dong. Ban can tao hop dong gi? (thue nha, mua ban, dich vu, lao dong)",
            "Chua co hop dong. Ban muon tao moi khong?",
        ],
        'pdf_success': [
            "Da xuat PDF xong roi! File o: {path}",
            "OK, da luu PDF tai: {path}",
            "Xong! Hop dong da duoc luu o: {path}",
        ],
        'preview_opened': [
            "Da mo xem truoc trong trinh duyet roi nhe!",
            "OK, check trinh duyet di!",
            "Da mo trang xem truoc roi!",
        ],
    }

    # Contract type names in Vietnamese
    CONTRACT_TYPE_NAMES = {
        'rental': 'thue nha',
        'sale_house': 'mua ban nha',
        'sale_land': 'mua ban dat',
        'sale': 'mua ban tai san',
        'service': 'dich vu',
        'employment': 'lao dong',
    }

    def __init__(self):
        self.client, self.provider, self.model = get_llm_client()
        self.research_service = ResearchService()
        self.template_generator = DynamicTemplateGenerator()
        self.pdf_generator = GeneratorService()
        self.session: Optional[ChatSession] = None

    def _call_llm(self, messages: list, temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """Call LLM with provider-specific handling"""
        if not self.client:
            return "Chua cau hinh API key. Vui long them ANTHROPIC_API_KEY hoac GROQ_API_KEY vao file .env"

        try:
            if self.provider == "anthropic":
                # Extract system message
                system_msg = ""
                user_messages = []
                for msg in messages:
                    if msg['role'] == 'system':
                        system_msg = msg['content']
                    else:
                        user_messages.append(msg)

                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system_msg,
                    messages=user_messages,
                )
                return response.content[0].text
            else:
                # Groq API
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content
        except Exception as e:
            return f"Loi khi goi LLM: {e}"

    def _random_response(self, key: str, **kwargs) -> str:
        """Get a random human-like response"""
        responses = self.HUMAN_RESPONSES.get(key, [key])
        response = random.choice(responses)
        return response.format(**kwargs) if kwargs else response

    def start_session(self) -> ChatSession:
        """Start a new chat session"""
        self.session = ChatSession(id=str(uuid4()))
        return self.session

    def get_session(self) -> ChatSession:
        """Get current session or start new one"""
        if not self.session:
            self.start_session()
        return self.session

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
            # User might be specifying contract type - check in order (more specific first)
            type_map = [
                ('thue nha', 'rental'), ('thue phong', 'rental'), ('thue', 'rental'), ('rental', 'rental'),
                ('mua ban nha', 'sale_house'), ('mua nha', 'sale_house'), ('ban nha', 'sale_house'),
                ('mua ban dat', 'sale_land'), ('mua dat', 'sale_land'), ('ban dat', 'sale_land'), ('chuyen nhuong dat', 'sale_land'),
                ('mua ban', 'sale'), ('mua', 'sale'), ('ban', 'sale'), ('sale', 'sale'),
                ('dich vu', 'service'), ('service', 'service'),
                ('lao dong', 'employment'), ('employment', 'employment'),
            ]
            for key, value in type_map:
                if key in input_normalized:
                    response = await self._create_contract(value)
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
                if input_normalized in ['huy', 'cancel', 'thoat', 'bo qua']:
                    session.mode = 'normal'
                    session.current_draft = None
                    response = InteractiveChatResponse(
                        message="OK, da huy. Ban can gi khac khong?",
                        action_taken="contract_cancelled"
                    )
                # Check for preview/export commands even during collection
                elif any(kw in input_normalized for kw in ['xem truoc', 'preview', 'xem hop dong']):
                    response = self._preview_contract()
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
                # All required fields collected
                draft.state = 'ready'
                session.mode = 'normal'  # Back to normal mode
                return InteractiveChatResponse(
                    message=self._random_response('contract_ready'),
                    contract_draft=draft,
                    action_taken="contract_ready"
                )
        else:
            # Shouldn't reach here, but just in case
            draft.state = 'ready'
            session.mode = 'normal'
            return InteractiveChatResponse(
                message=self._random_response('contract_ready'),
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
            # User wants to create contract but didn't specify type
            return InteractiveChatResponse(
                message="OK! Ban muon tao loai hop dong nao?\n\n"
                        "• thue nha - Hop dong cho thue nha/phong\n"
                        "• mua ban nha - Hop dong mua ban nha o\n"
                        "• mua ban dat - Hop dong chuyen nhuong quyen su dung dat\n"
                        "• mua ban - Hop dong mua ban tai san khac\n"
                        "• dich vu - Hop dong cung cap dich vu\n"
                        "• lao dong - Hop dong lao dong\n\n"
                        "Noi ten loai hop dong nhe (vd: 'thue nha', 'mua ban dat')",
                action_taken="ask_contract_type"
            )

        elif command.command == 'preview':
            return self._preview_contract()

        elif command.command == 'export_pdf':
            return self._export_pdf(command.args.get('filename'))

        elif command.command == 'edit_field':
            return self._edit_field(command.args['field'], command.args['value'])

        elif command.command == 'show_contract':
            return self._show_contract()

        elif command.command == 'research':
            return await self._research_topic(command.args['topic'])

        return InteractiveChatResponse(
            message="Hmm, khong hieu lenh nay lam. Ban thu lai nhe!",
            action_taken="unknown_command"
        )

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

        # Build context for LLM response
        context = await self._build_context_for_query(user_input, session)

        # Generate response with LLM - using human-like prompt
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]

        # Add conversation history (last 6 messages for context)
        for msg in session.messages[-6:]:
            if msg['role'] in ['user', 'assistant']:
                messages.append({"role": msg['role'], "content": msg['content']})

        # Add context if available
        user_content = user_input
        if context:
            user_content = f"{user_input}\n\n[Thong tin tham khao: {context}]"
        messages.append({"role": "user", "content": user_content})

        answer = self._call_llm(messages, temperature=0.7, max_tokens=1000)

        result = InteractiveChatResponse(message=answer)

        # If we have a ready draft, add subtle reminder
        if session.current_draft and session.current_draft.state == 'ready':
            result.contract_draft = session.current_draft
            result.action_taken = "chat_with_draft"

        return result

    async def _detect_contract_type_with_llm(self, user_input: str) -> Optional[str]:
        """Use LLM to detect contract type from user input"""
        system_prompt = """Ban la tro ly phan loai hop dong. Tu yeu cau cua nguoi dung, hay xac dinh loai hop dong can tao.

Cac loai hop dong ho tro:
- rental: Thue nha, thue phong, cho thue
- sale_house: Mua ban nha o, mua ban can ho
- sale_land: Mua ban dat, chuyen nhuong quyen su dung dat
- sale: Mua ban tai san khac (xe, do vat...)
- service: Dich vu, cung cap dich vu
- employment: Lao dong, tuyen dung, nhan vien

Tra ve CHI MOT tu: rental, sale_house, sale_land, sale, service, employment
Neu khong xac dinh duoc, tra ve: none"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ]

        result = self._call_llm(messages, temperature=0.1, max_tokens=20)
        result = result.strip().lower()

        valid_types = ['rental', 'sale_house', 'sale_land', 'sale', 'service', 'employment']
        if result in valid_types:
            return result

        return None

    async def _build_context_for_query(self, user_input: str, session: ChatSession) -> str:
        """Build relevant context for the query - research if needed"""
        # Normalize for comparison
        input_normalized = remove_diacritics(user_input.lower())

        # Check if this is a legal question that needs research
        legal_question_keywords = [
            'dieu luat', 'quy dinh', 'luat', 'phap ly', 'phap luat',
            'quyen', 'nghia vu', 'dieu kien', 'thu tuc', 'ho so',
            'la gi', 'nhu the nao', 'can gi', 'phai', 'duoc khong'
        ]

        is_legal_question = any(kw in input_normalized for kw in legal_question_keywords)

        if is_legal_question:
            try:
                research_result = await self.research_service.research(user_input, max_sources=2)
                if research_result.analyzed_content:
                    return research_result.analyzed_content[:1500]
            except Exception as e:
                print(f"Research error: {e}")

        return ""

    def _get_flexible_system_prompt(self, session: ChatSession) -> str:
        """Get flexible system prompt that handles any legal topic"""
        base_prompt = """Ban la tro ly phap ly Viet Nam thong minh. Ban co the:

1. TRA LOI bat ky cau hoi phap ly nao (luat dan su, hinh su, lao dong, dat dai, kinh doanh, v.v.)
2. TAO hop dong khi nguoi dung yeu cau (noi "tao hop dong [loai]")
3. CHINH SUA hop dong theo yeu cau
4. XUAT hop dong ra PDF

Khi tra loi cau hoi phap ly:
- Cung cap thong tin chinh xac dua tren phap luat Viet Nam
- Trich dan dieu luat cu the neu co
- Giai thich ro rang, de hieu

Khi tao hop dong:
- Xac dinh loai hop dong phu hop
- Huong dan nguoi dung cung cap thong tin can thiet
- Cho phep xem truoc va xuat PDF

Cac lenh:
- "tao hop dong [loai]" - Tao hop dong moi
- "xem hop dong" / "preview" - Xem truoc trong trinh duyet
- "xuat pdf" - Xuat file PDF
- "sua [truong] = [gia tri]" - Cap nhat thong tin

Luu y: Day chi la thong tin tham khao, khong thay the tu van phap ly chuyen nghiep."""

        if session.current_draft:
            draft = session.current_draft
            filled_fields = "\n".join([f"- {k}: {v}" for k, v in draft.field_values.items()])
            unfilled = [f.label for f in draft.template.fields if f.name not in draft.field_values and f.required]

            base_prompt += f"""

---
HOP DONG DANG SOAN: {draft.template.name}
Da dien: {len(draft.field_values)}/{len(draft.template.fields)} truong
{f'Thong tin: {chr(10)}{filled_fields}' if filled_fields else ''}
{f'Chua dien: {", ".join(unfilled)}' if unfilled else 'Da day du thong tin!'}
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

        try:
            template = self.template_generator.generate_template(contract_type)
            draft = ContractDraft(
                id=str(uuid4()),
                contract_type=contract_type,
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

        system_prompt = """Ban la tro ly trich xuat thong tin. Tu van ban nguoi dung cung cap,
hay trich xuat cac truong thong tin hop dong.

Tra ve JSON voi format:
{"field_name": "gia tri", ...}

Chi tra ve cac truong co thong tin ro rang trong van ban.
Neu khong tim thay, tra ve {}"""

        fields_info = "\n".join([f"- {name}: {label}" for name, label in field_labels.items()])

        user_prompt = f"""CAC TRUONG CAN TRICH XUAT:
{fields_info}

VAN BAN:
{text}

Hay trich xuat thong tin va tra ve JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=500,
            )

            response_text = response.choices[0].message.content

            # Extract JSON from response
            import json
            if '```' in response_text:
                json_text = response_text.split('```')[1].replace('json', '').strip()
            else:
                json_text = response_text.strip()

            extracted = json.loads(json_text)
            # Filter to only valid fields
            return {k: v for k, v in extracted.items() if k in field_names and v}

        except Exception as e:
            print(f"Error extracting fields: {e}")
            return {}

    def _get_enhanced_system_prompt(self, session: ChatSession) -> str:
        """Get enhanced system prompt based on session state"""
        base_prompt = self.SYSTEM_PROMPT

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

THONG TIN HOP DONG HIEN TAI:
Loai: {draft.template.name}
Cac truong da dien:
{filled_fields if filled_fields else '(chua co)'}

Cac truong can dien:
{', '.join(unfilled_fields) if unfilled_fields else '(da day du)'}

Khi nguoi dung cung cap thong tin, hay xac nhan va ghi nhan.
Khi nguoi dung muon xem hop dong, hay huong dan ho noi 'xem hop dong' de mo trong trinh duyet."""

        return base_prompt

    async def _create_contract(self, contract_type: str) -> InteractiveChatResponse:
        """Create a new contract draft and start step-by-step collection"""
        session = self.get_session()

        # Normalize contract type - check in order (more specific first)
        type_map = {
            # Thue
            'thue': 'rental', 'rental': 'rental', 'thue nha': 'rental', 'thue phong': 'rental',
            # Mua ban nha
            'sale_house': 'sale_house', 'mua ban nha': 'sale_house', 'mua nha': 'sale_house', 'ban nha': 'sale_house',
            # Mua ban dat
            'sale_land': 'sale_land', 'mua ban dat': 'sale_land', 'mua dat': 'sale_land', 'ban dat': 'sale_land',
            'chuyen nhuong dat': 'sale_land',
            # Mua ban chung
            'mua': 'sale', 'ban': 'sale', 'sale': 'sale', 'mua ban': 'sale',
            # Dich vu
            'dich vu': 'service', 'service': 'service',
            # Lao dong
            'lao dong': 'employment', 'employment': 'employment', 'viec': 'employment'
        }
        normalized_type = type_map.get(contract_type.lower(), contract_type.lower())

        try:
            # Generate template (skip research to be faster)
            template = self.template_generator.generate_template(normalized_type, None)

            # Create draft with collecting state
            draft = ContractDraft(
                id=str(uuid4()),
                contract_type=normalized_type,
                template=template,
                field_values={},
                legal_basis=template.legal_references,
                current_field_index=0,
                state='collecting'
            )
            session.current_draft = draft
            session.mode = 'contract_creation'

            # Get Vietnamese type name
            type_name = self.CONTRACT_TYPE_NAMES.get(normalized_type, normalized_type)

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
            return InteractiveChatResponse(
                message=f"Hmm, chua ho tro loai hop dong nay. Thu: thue nha, mua ban, dich vu, hoac lao dong nhe!",
                action_taken="error"
            )

    def _preview_contract(self) -> InteractiveChatResponse:
        """Generate HTML preview of current contract"""
        session = self.get_session()

        if not session.current_draft:
            return InteractiveChatResponse(
                message=self._random_response('missing_contract'),
                action_taken="no_contract"
            )

        # Now we have a draft - continue with preview
        draft = session.current_draft
        html = self._generate_html_preview(draft)

        # Save to temp file and open in browser
        temp_dir = Path(tempfile.gettempdir())
        html_path = temp_dir / f"contract_preview_{draft.id[:8]}.html"

        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html)

        # Open in browser
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
                        <em>Tom tat: {article.summary}</em>
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
    <title>Xem truoc: {template.name}</title>
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
        <div>CONG HOA XA HOI CHU NGHIA VIET NAM</div>
        <div><strong>Doc lap - Tu do - Hanh phuc</strong></div>
        <div>---oOo---</div>
    </div>

    <div class="title" style="text-align: center;">
        {template.name.upper()}
    </div>

    <p><em>{template.description}</em></p>

    <!-- DETAILED LEGAL BASIS SECTION -->
    <div class="legal-basis-section">
        <h3>CO SO PHAP LY</h3>
        <p><em>Hop dong nay duoc lap dua tren cac quy dinh phap luat sau:</em></p>
        {legal_articles_html}
    </div>

    <!-- CONTRACT INFORMATION -->
    <div class="contract-info">
        <h3>THONG TIN HOP DONG</h3>
        <table>
            {field_rows}
        </table>
    </div>

    <!-- KEY TERMS -->
    <div class="key-terms">
        <h4>CAC DIEU KHOAN QUAN TRONG THEO QUY DINH PHAP LUAT:</h4>
        {key_terms}
    </div>

    <!-- SIGNATURES -->
    <div class="signature">
        <div class="signature-box">
            <strong>BEN A</strong><br>
            (Ky va ghi ro ho ten)<br><br><br><br>
        </div>
        <div class="signature-box">
            <strong>BEN B</strong><br>
            (Ky va ghi ro ho ten)<br><br><br><br>
        </div>
    </div>

    <div class="disclaimer">
        <strong>Luu y:</strong> Day chi la ban xem truoc mang tinh chat tham khao.
        Cac dieu khoan phap ly duoc trich dan tu cac van ban phap luat hien hanh.
        Vui long kiem tra ky thong tin truoc khi xuat PDF chinh thuc.
        <strong>Khong thay the tu van phap ly chuyen nghiep.</strong>
    </div>

    <script>
        // Auto-print option
        // window.print();
    </script>
</body>
</html>"""

        return html

    def _export_pdf(self, filename: Optional[str] = None) -> InteractiveChatResponse:
        """Export current contract to PDF"""
        session = self.get_session()

        if not session.current_draft:
            return InteractiveChatResponse(
                message=self._random_response('missing_contract'),
                action_taken="no_contract"
            )

        draft = session.current_draft

        # Determine output path
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"contract_{draft.contract_type}_{timestamp}.pdf"

        output_path = Path.cwd() / filename

        try:
            # Map dynamic template fields to generator format
            field_data = {}
            for field in draft.template.fields:
                value = draft.field_values.get(field.name, '________________')
                field_data[field.name] = value

            # Generate PDF
            result = self.pdf_generator.generate(
                template_type=draft.contract_type,
                data=field_data,
                output_path=str(output_path),
                skip_validation=True
            )

            # Mark as exported
            draft.state = 'exported'

            return InteractiveChatResponse(
                message=self._random_response('pdf_success', path=str(output_path)),
                pdf_path=str(output_path),
                action_taken="pdf_exported"
            )

        except Exception as e:
            return InteractiveChatResponse(
                message=f"Ui, co loi khi xuat PDF: {e}. Thu lai nhe!",
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
                message=f"OK, da sua {actual_name} thanh \"{value}\" roi!",
                contract_draft=draft,
                action_taken="field_updated"
            )

        return InteractiveChatResponse(
            message=f"Hmm, khong tim thay truong '{field_name}'. Thu: {', '.join(field_names[:3])}...",
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
        type_name = self.CONTRACT_TYPE_NAMES.get(draft.contract_type, draft.contract_type)

        # Just show brief status
        filled_count = len(draft.field_values)
        required_fields = [f for f in draft.template.fields if f.required]
        total_required = len(required_fields)

        # Check what's missing
        missing = [f.label for f in required_fields if f.name not in draft.field_values]

        if missing:
            status_msg = f"Hop dong {type_name}: {filled_count}/{total_required} truong bat buoc da dien."
            if len(missing) <= 3:
                status_msg += f"\nCon thieu: {', '.join(missing)}"
            status_msg += "\n\nNoi 'xem hop dong' de xem chi tiet tren web!"
        else:
            status_msg = f"Hop dong {type_name} da du thong tin roi! Noi 'xem hop dong' de xem truoc, hoac 'xuat pdf' de tai ve."

        return InteractiveChatResponse(
            message=status_msg,
            contract_draft=draft,
            action_taken="contract_status"
        )

    async def _research_topic(self, topic: str) -> InteractiveChatResponse:
        """Research a specific legal topic"""
        result = await self.research_service.research(topic, max_sources=3)

        message = f"""KET QUA NGHIEN CUU: {topic}

{result.analyzed_content}

Nguon tham khao: {len(result.crawled_sources)} van ban
"""

        if result.legal_articles:
            message += f"\nCac dieu luat lien quan: {len(result.legal_articles)} dieu"

        if result.suggested_contract_type:
            message += f"\n\n[Goi y: Ban co the tao hop dong {result.suggested_contract_type}]"

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
