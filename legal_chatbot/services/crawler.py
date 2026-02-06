"""Web crawler service for legal documents"""

import asyncio
import aiohttp
import re
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, AsyncIterator
from bs4 import BeautifulSoup
from pydantic import BaseModel

from legal_chatbot.utils.config import get_settings
from legal_chatbot.utils.vietnamese import clean_text, normalize_vietnamese


class CrawlConfig(BaseModel):
    """Configuration for crawling"""
    source: str = "thuvienphapluat"
    limit: Optional[int] = None
    categories: list[str] = []
    rate_limit_seconds: float = 2.0
    output_dir: str = "./data/raw"


class CrawledDocument(BaseModel):
    """A crawled legal document"""
    url: str
    document_number: str
    title: str
    document_type: str
    effective_date: Optional[str] = None
    issuing_authority: Optional[str] = None
    html_content: str
    crawled_at: datetime = datetime.now()


class CrawlerService:
    """Service for crawling legal documents from thuvienphapluat.vn"""

    BASE_URL = "https://thuvienphapluat.vn"

    # Sample legal document URLs for demo purposes
    SAMPLE_URLS = [
        "/van-ban/Bat-dong-san/Luat-Nha-o-2014-259721.aspx",
        "/van-ban/Bat-dong-san/Luat-Kinh-doanh-bat-dong-san-2014-259722.aspx",
        "/van-ban/Quyen-dan-su/Bo-luat-dan-su-2015-296215.aspx",
    ]

    def __init__(self, config: Optional[CrawlConfig] = None):
        self.config = config or CrawlConfig()
        self.output_dir = Path(self.config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def crawl(self, limit: Optional[int] = None) -> AsyncIterator[CrawledDocument]:
        """
        Crawl legal documents.

        For demo purposes, uses sample URLs. In production, would crawl
        the actual website with proper pagination.
        """
        urls_to_crawl = self.SAMPLE_URLS[:limit] if limit else self.SAMPLE_URLS

        async with aiohttp.ClientSession() as session:
            for url in urls_to_crawl:
                full_url = f"{self.BASE_URL}{url}"
                try:
                    doc = await self._fetch_document(session, full_url)
                    if doc:
                        yield doc
                    await asyncio.sleep(self.config.rate_limit_seconds)
                except Exception as e:
                    print(f"Error crawling {full_url}: {e}")
                    continue

    async def _fetch_document(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> Optional[CrawledDocument]:
        """Fetch and parse a single document"""
        try:
            async with session.get(url, timeout=30) as response:
                if response.status != 200:
                    return None

                html = await response.text()
                return self._parse_document(url, html)

        except asyncio.TimeoutError:
            print(f"Timeout fetching {url}")
            return None
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None

    def _parse_document(self, url: str, html: str) -> Optional[CrawledDocument]:
        """Parse HTML to extract document metadata and content"""
        soup = BeautifulSoup(html, 'html.parser')

        # Extract title
        title_elem = soup.find('h1') or soup.find('title')
        title = clean_text(title_elem.get_text()) if title_elem else "Unknown"

        # Extract document number from URL or content
        doc_number = self._extract_document_number(url, soup)

        # Determine document type
        doc_type = self._determine_document_type(title, url)

        # Extract main content
        content_elem = soup.find('div', class_='content1') or soup.find('div', class_='toanvancontent') or soup.find('article')
        content = str(content_elem) if content_elem else html

        # Extract effective date
        effective_date = self._extract_effective_date(soup)

        # Extract issuing authority
        authority = self._extract_authority(soup)

        return CrawledDocument(
            url=url,
            document_number=doc_number,
            title=title,
            document_type=doc_type,
            effective_date=effective_date,
            issuing_authority=authority,
            html_content=content,
        )

    def _extract_document_number(self, url: str, soup: BeautifulSoup) -> str:
        """Extract document number from URL or content"""
        # Try to extract from URL
        match = re.search(r'(\d+/\d+/[A-Z]+\d*)', url)
        if match:
            return match.group(1)

        # Try to find in page content
        for pattern in [r'Số:\s*(\d+/\d+/[A-Z-]+)', r'(\d+/\d+/QH\d+)']:
            text = soup.get_text()
            match = re.search(pattern, text)
            if match:
                return match.group(1)

        return "Unknown"

    def _determine_document_type(self, title: str, url: str) -> str:
        """Determine the type of legal document"""
        title_lower = title.lower()
        url_lower = url.lower()

        if 'bo-luat' in url_lower or 'bộ luật' in title_lower:
            return 'bo_luat'
        elif 'luat' in url_lower or 'luật' in title_lower:
            return 'luat'
        elif 'nghi-dinh' in url_lower or 'nghị định' in title_lower:
            return 'nghi_dinh'
        elif 'thong-tu' in url_lower or 'thông tư' in title_lower:
            return 'thong_tu'
        else:
            return 'luat'

    def _extract_effective_date(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract effective date from document"""
        patterns = [
            r'có hiệu lực.*?(\d{1,2}/\d{1,2}/\d{4})',
            r'ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})',
        ]

        text = soup.get_text()
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 3:
                    return f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
                return match.group(1)

        return None

    def _extract_authority(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract issuing authority from document"""
        authorities = ['Quốc hội', 'Chính phủ', 'Thủ tướng', 'Bộ']

        text = soup.get_text()
        for auth in authorities:
            if auth.lower() in text.lower():
                return auth

        return None

    def save_document(self, doc: CrawledDocument) -> Path:
        """Save crawled document to disk"""
        # Create safe filename
        safe_title = re.sub(r'[^\w\s-]', '', doc.title)[:50]
        filename = f"{doc.document_type}_{safe_title}.json"
        filepath = self.output_dir / filename

        # Save as JSON
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(doc.model_dump(mode='json'), f, ensure_ascii=False, indent=2, default=str)

        return filepath


async def crawl_documents(limit: int = 10, output_dir: str = "./data/raw") -> list[CrawledDocument]:
    """Convenience function to crawl documents"""
    config = CrawlConfig(limit=limit, output_dir=output_dir)
    crawler = CrawlerService(config)

    documents = []
    async for doc in crawler.crawl(limit=limit):
        filepath = crawler.save_document(doc)
        print(f"Saved: {filepath}")
        documents.append(doc)

    return documents
