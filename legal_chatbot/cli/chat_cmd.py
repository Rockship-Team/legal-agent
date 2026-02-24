"""Chat command implementation"""

import json
import sys
import io
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table

from legal_chatbot.services.chat import get_chat_service

# Force UTF-8 output on Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

console = Console(force_terminal=True)


def chat_command(query: str, json_output: bool = False):
    """Process a chat query and display the response"""

    if json_output:
        _chat_json(query)
    else:
        _chat_rich(query)


def _chat_json(query: str):
    """Output chat response as JSON"""
    try:
        service = get_chat_service()
        response = service.chat(query)

        output = {
            "answer": response.answer,
            "citations": [
                {
                    "article_id": c.article_id,
                    "article_number": c.article_number,
                    "document_title": c.document_title,
                    "relevance_score": c.relevance_score,
                }
                for c in response.citations
            ],
            "suggested_templates": response.suggested_templates,
        }

        print(json.dumps(output, ensure_ascii=False, indent=2))

    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))


def _chat_rich(query: str):
    """Output chat response with Rich formatting"""

    print()
    print(f"=== Cau hoi ===")
    print(query)
    print()

    try:
        print("Dang tim kiem va phan tich...")
        service = get_chat_service()
        response = service.chat(query)

        # Display answer
        print()
        print("=== Tra loi ===")
        print(response.answer)
        print()

        # Display citations if any
        if response.citations:
            print("=== Nguon tham khao ===")
            for citation in response.citations:
                print(f"  - Dieu {citation.article_number}: {citation.document_title} (score: {citation.relevance_score:.2f})")
            print()

        # Display suggested templates if any
        if response.suggested_templates:
            print("=== Goi y mau hop dong ===")
            print(f"  Templates: {', '.join(response.suggested_templates)}")
            print("  Su dung lenh: python -m legal_chatbot generate --template <ten>")
            print()

        # Disclaimer
        print("---")
        print("Luu y: Thong tin nay chi mang tinh chat tham khao, khong thay the tu van phap ly chuyen nghiep.")

    except Exception as e:
        print(f"Loi: {e}")
        print()
        print("Hay dam bao:")
        print("1. Da chay: python -m legal_chatbot init")
        print("2. Da them du lieu: python -m legal_chatbot add-sample")
        print("3. File .env co ANTHROPIC_API_KEY hop le")
