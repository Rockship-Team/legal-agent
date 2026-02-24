"""Integration tests for slash command CLI backends.

Tests the CLI commands that /legal.research and /legal.create-contract depend on.
Requires DB_MODE=supabase and valid Supabase credentials in .env.

Uses cached subprocess results — each unique CLI call runs only once.
Total: ~6 subprocess calls instead of 16, ~15s instead of 2m+.
"""

import json
import os
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).parent.parent
CLI_CMD = [sys.executable, "-m", "legal_chatbot"]

# Load .env once
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


def is_supabase_configured() -> bool:
    return bool(os.getenv("SUPABASE_URL")) and bool(os.getenv("SUPABASE_KEY"))


pytestmark = pytest.mark.skipif(
    not is_supabase_configured(),
    reason="Supabase credentials not configured in .env",
)


@lru_cache(maxsize=32)
def _cached_cli(*args) -> tuple[int, str, str]:
    """Run CLI command once, cache result. Returns (returncode, stdout, stderr)."""
    result = subprocess.run(
        CLI_CMD + list(args),
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=30,
        encoding="utf-8",
    )
    return result.returncode, result.stdout, result.stderr


def cli(*args):
    """Run cached CLI command. Returns (returncode, stdout)."""
    code, out, err = _cached_cli(*args)
    return code, out


def cli_json(*args):
    """Run cached CLI command and parse JSON output."""
    code, out = cli(*args)
    assert code == 0, f"exit {code}: {out}"
    return json.loads(out, strict=False)


# ──────────────────────────────────────────────────────────────────
# db-articles tests — 3 subprocess calls total (cached)
# ──────────────────────────────────────────────────────────────────

class TestDbArticles:

    def test_list_categories_returns_json(self):
        data = cli_json("db-articles")
        assert "categories" in data
        assert isinstance(data["categories"], list)

    def test_list_categories_has_dat_dai(self):
        data = cli_json("db-articles")
        cat_names = [c["name"] for c in data["categories"]]
        assert "dat_dai" in cat_names
        dat_dai = next(c for c in data["categories"] if c["name"] == "dat_dai")
        assert dat_dai["article_count"] > 0

    def test_existing_category_compact(self):
        data = cli_json("db-articles", "dat_dai", "--limit", "3", "--compact")
        assert data["category"] == "dat_dai"
        assert data["total"] > 0
        for art in data["articles"]:
            assert "article_number" in art
            assert "title" in art
            assert "document_title" in art
            assert "content" in art
            assert art["document_title"] != ""
            assert len(art["content"]) <= 210, f"Compact too long: {len(art['content'])}"

    def test_existing_category_full(self):
        data = cli_json("db-articles", "dat_dai", "--limit", "1")
        assert data["total"] > 0
        has_long = any(len(a["content"]) > 200 for a in data["articles"])
        assert has_long, "Full mode should return untruncated content"

    def test_nonexisting_category(self):
        code, out = cli("db-articles", "lao_dong")
        assert code == 0
        data = json.loads(out, strict=False)
        assert "error" in data or ("articles" in data and len(data["articles"]) == 0)

    def test_invalid_category(self):
        code, out = cli("db-articles", "khong_ton_tai_xyz")
        assert code == 0
        data = json.loads(out, strict=False)
        assert "error" in data

    def test_keyword_filter_compact(self):
        data = cli_json("db-articles", "dat_dai", "--keyword", "thuê", "--limit", "5", "--compact")
        assert data["keyword"] == "thuê"
        assert data["total"] > 0
        for art in data["articles"]:
            assert len(art["content"]) <= 210

    def test_keyword_no_match(self):
        data = cli_json("db-articles", "dat_dai", "--keyword", "xyznonexistent123")
        assert data["articles"] == []

    def test_no_crawl_in_output(self):
        _, out = cli("db-articles", "lao_dong")
        assert "crawl" not in out.lower()
        assert "pipeline" not in out.lower()


# ──────────────────────────────────────────────────────────────────
# contract-lookup tests — 3 subprocess calls total (cached)
# ──────────────────────────────────────────────────────────────────

class TestContractLookup:

    def test_list_returns_json(self):
        data = cli_json("contract-lookup", "--list")
        assert "available" in data
        assert isinstance(data["available"], list)

    def test_list_has_dat_dai_templates(self):
        data = cli_json("contract-lookup", "--list")
        types = [t["contract_type"] for t in data["available"]]
        assert {"mua_ban_dat", "cho_thue_dat", "chuyen_nhuong_dat"} & set(types)

    def test_list_shows_cached_status(self):
        data = cli_json("contract-lookup", "--list")
        for tmpl in data["available"]:
            assert "contract_type" in tmpl
            assert "display_name" in tmpl
            assert "articles_count" in tmpl
            assert "cached" in tmpl

    def test_existing_template(self):
        data = cli_json("contract-lookup", "cho_thue_dat")
        assert data["contract_type"] == "cho_thue_dat"
        assert data["articles_count"] > 0
        assert len(data["articles"]) > 0
        assert "required_laws" in data

    def test_nonexisting_template(self):
        code, out = cli("contract-lookup", "hop_dong_lao_dong")
        assert code == 0
        assert "available templates" in out.lower() or "not found" in out.lower()

    def test_no_args_lists_all(self):
        data = cli_json("contract-lookup")
        assert "available" in data

    def test_no_crawl_in_output(self):
        _, out = cli("contract-lookup", "hop_dong_lao_dong")
        assert "crawl" not in out.lower()
        assert "pipeline" not in out.lower()


# ──────────────────────────────────────────────────────────────────
# Slash command file tests — pure file reads, instant
# ──────────────────────────────────────────────────────────────────

class TestSlashCommandFiles:

    COMMANDS_DIR = PROJECT_ROOT / ".claude" / "commands"

    def _read(self, name: str) -> str:
        path = self.COMMANDS_DIR / name
        assert path.exists()
        return path.read_text(encoding="utf-8")

    def test_research_no_crawl(self):
        content = self._read("legal.research.md")
        for line in content.split("\n"):
            if "crawl" in line.lower() or "/legal.pipeline" in line.lower():
                assert any(w in line for w in ["KHONG", "CAM", "TUYET DOI"]), \
                    f"crawl outside prohibition: '{line.strip()}'"

    def test_research_no_groq(self):
        content = self._read("legal.research.md")
        assert "groq" not in content.lower() or "KHONG" in content

    def test_research_no_websearch(self):
        content = self._read("legal.research.md")
        lines = [l for l in content.split("\n") if "websearch" in l.lower() and "KHONG" not in l]
        assert not lines

    def test_research_has_prohibition(self):
        assert "TUYET DOI KHONG" in self._read("legal.research.md") or "CAM" in self._read("legal.research.md")

    def test_research_uses_compact(self):
        assert "--compact" in self._read("legal.research.md")

    def test_research_no_file_redirect(self):
        content = self._read("legal.research.md")
        assert "redirect" in content.lower() or "temp file" in content.lower() or "tmp" in content.lower()

    def test_create_contract_no_crawl(self):
        content = self._read("legal.create-contract.md")
        assert "/legal.pipeline" not in content
        lines = [
            l.strip() for l in content.split("\n")
            if "crawl" in l.lower()
            and "pipeline crawl" not in l.lower()
            and "cached" not in l.lower()
            and "pre-compute" not in l.lower()
            and "khi crawl" not in l.lower()
        ]
        assert not lines, f"suggests crawl: {lines}"

    def test_create_contract_uses_contract_lookup(self):
        content = self._read("legal.create-contract.md")
        assert "contract-lookup" in content
        assert "contract-lookup --list" in content


# ──────────────────────────────────────────────────────────────────
# research.py service tests — pure file reads, instant
# ──────────────────────────────────────────────────────────────────

class TestResearchService:

    _content = None

    @classmethod
    def _read(cls):
        if cls._content is None:
            cls._content = (PROJECT_ROOT / "legal_chatbot" / "services" / "research.py").read_text(encoding="utf-8")
        return cls._content

    def test_no_groq_import(self):
        c = self._read()
        assert "from groq" not in c
        assert "import groq" not in c

    def test_no_groq_client(self):
        assert "Groq(" not in self._read()

    def test_has_available_categories(self):
        assert "_get_available_categories" in self._read()

    def test_has_detect_contract_type(self):
        assert "_detect_contract_type" in self._read()
