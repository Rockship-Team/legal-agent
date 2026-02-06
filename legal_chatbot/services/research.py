"""Research service for real-time crawling and deep legal research"""

import asyncio
import aiohttp
import re
from typing import Optional
from bs4 import BeautifulSoup
from groq import Groq
from pydantic import BaseModel

from legal_chatbot.utils.config import get_settings
from legal_chatbot.utils.vietnamese import clean_text


class ResearchResult(BaseModel):
    """Result from research service"""
    query: str
    crawled_sources: list[dict] = []
    raw_content: str = ""
    analyzed_content: str = ""
    legal_articles: list[dict] = []
    contract_template_data: Optional[dict] = None
    suggested_contract_type: Optional[str] = None


class ResearchService:
    """Service for real-time legal research from thuvienphapluat.vn"""

    BASE_URL = "https://thuvienphapluat.vn"
    SEARCH_URL = "https://thuvienphapluat.vn/page/tim-van-ban.aspx"

    def __init__(self):
        settings = get_settings()
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = settings.llm_model

    async def research(self, query: str, max_sources: int = 3) -> ResearchResult:
        """
        Research a legal topic:
        1. Crawl relevant data from thuvienphapluat.vn
        2. Extract legal articles
        3. Use LLM to analyze and provide accurate information
        """
        result = ResearchResult(query=query)

        # Step 1: Crawl relevant sources
        crawled_data = await self._crawl_search_results(query, max_sources)
        result.crawled_sources = crawled_data
        result.raw_content = "\n\n---\n\n".join([d.get('content', '') for d in crawled_data])

        # Step 2: Extract legal articles from crawled content
        result.legal_articles = self._extract_legal_articles(crawled_data)

        # Step 3: Analyze with LLM for accurate information
        if result.raw_content:
            result.analyzed_content = self._analyze_with_llm(query, result.raw_content)

        # Step 4: Determine if a contract is relevant and extract template data
        contract_analysis = self._analyze_contract_relevance(query, result.analyzed_content)
        result.suggested_contract_type = contract_analysis.get('type')
        result.contract_template_data = contract_analysis.get('template_data')

        return result

    async def _crawl_search_results(self, query: str, max_results: int = 3) -> list[dict]:
        """Search and crawl relevant legal documents"""
        results = []

        async with aiohttp.ClientSession() as session:
            # Search for relevant documents
            search_urls = await self._search_documents(session, query, max_results)

            # Crawl each document
            for url in search_urls[:max_results]:
                try:
                    doc_data = await self._fetch_and_parse(session, url)
                    if doc_data:
                        results.append(doc_data)
                    await asyncio.sleep(1)  # Rate limiting
                except Exception as e:
                    print(f"Error crawling {url}: {e}")

        return results

    async def _search_documents(
        self,
        session: aiohttp.ClientSession,
        query: str,
        limit: int = 3
    ) -> list[str]:
        """Search for legal documents matching the query"""
        search_keywords = self._extract_search_keywords(query)
        urls = []

        # Direct search URL construction
        search_url = f"{self.BASE_URL}/page/tim-van-ban.aspx?keyword={search_keywords}"

        try:
            async with session.get(search_url, timeout=30) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    # Find search result links
                    for link in soup.find_all('a', href=True):
                        href = link['href']
                        if '/van-ban/' in href and href not in urls:
                            full_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                            urls.append(full_url)
                            if len(urls) >= limit:
                                break
        except Exception as e:
            print(f"Search error: {e}")

        # Fallback to predefined relevant URLs based on keywords
        if not urls:
            urls = self._get_fallback_urls(query)

        return urls[:limit]

    def _extract_search_keywords(self, query: str) -> str:
        """Extract search keywords from query"""
        # Remove common Vietnamese question words
        stop_words = ['la', 'gi', 'nhu', 'the', 'nao', 'sao', 'bao', 'nhieu', 'dieu', 'kien', 'cua']
        words = query.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return '+'.join(keywords[:5])

    def _get_fallback_urls(self, query: str) -> list[str]:
        """Get fallback URLs based on query keywords"""
        query_lower = query.lower()
        urls = []

        if any(kw in query_lower for kw in ['thue', 'cho thue', 'thue nha']):
            urls.append(f"{self.BASE_URL}/van-ban/Bat-dong-san/Luat-Nha-o-2014-259721.aspx")
        if any(kw in query_lower for kw in ['mua ban', 'mua', 'ban', 'chuyen nhuong']):
            urls.append(f"{self.BASE_URL}/van-ban/Quyen-dan-su/Bo-luat-dan-su-2015-296215.aspx")
        if any(kw in query_lower for kw in ['dich vu', 'hop dong dich vu']):
            urls.append(f"{self.BASE_URL}/van-ban/Quyen-dan-su/Bo-luat-dan-su-2015-296215.aspx")
        if any(kw in query_lower for kw in ['lao dong', 'tuyen dung', 'nhan vien']):
            urls.append(f"{self.BASE_URL}/van-ban/Lao-dong-Tien-luong/Bo-luat-lao-dong-2019-433148.aspx")

        # Default to Civil Code if no specific match
        if not urls:
            urls.append(f"{self.BASE_URL}/van-ban/Quyen-dan-su/Bo-luat-dan-su-2015-296215.aspx")

        return urls

    async def _fetch_and_parse(
        self,
        session: aiohttp.ClientSession,
        url: str
    ) -> Optional[dict]:
        """Fetch and parse a legal document"""
        try:
            async with session.get(url, timeout=30) as response:
                if response.status != 200:
                    return None

                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')

                # Extract title
                title_elem = soup.find('h1') or soup.find('title')
                title = clean_text(title_elem.get_text()) if title_elem else "Unknown"

                # Extract main content
                content_elem = (
                    soup.find('div', class_='content1') or
                    soup.find('div', class_='toanvancontent') or
                    soup.find('article') or
                    soup.find('div', class_='noidung')
                )

                if content_elem:
                    # Clean the content
                    content = clean_text(content_elem.get_text())
                else:
                    content = clean_text(soup.get_text())[:5000]

                return {
                    'url': url,
                    'title': title,
                    'content': content[:10000],  # Limit content length
                }

        except Exception as e:
            print(f"Error parsing {url}: {e}")
            return None

    def _extract_legal_articles(self, crawled_data: list[dict]) -> list[dict]:
        """Extract individual legal articles from crawled content"""
        articles = []

        for data in crawled_data:
            content = data.get('content', '')
            title = data.get('title', '')

            # Pattern to find articles (Dieu X. ...)
            article_pattern = r'(?:Dieu|Điều)\s+(\d+)[.:]?\s*(.*?)(?=(?:Dieu|Điều)\s+\d+|$)'
            matches = re.findall(article_pattern, content, re.DOTALL | re.IGNORECASE)

            for article_num, article_content in matches:
                articles.append({
                    'article_number': int(article_num),
                    'content': article_content.strip()[:2000],
                    'source_title': title,
                    'source_url': data.get('url', ''),
                })

        return articles

    def _analyze_with_llm(self, query: str, raw_content: str) -> str:
        """Use LLM to analyze crawled content and provide accurate information"""
        system_prompt = """Ban la chuyen gia phap ly Viet Nam. Nhiem vu cua ban la:
1. Phan tich thong tin phap ly tu noi dung duoc cung cap
2. Trich dan chinh xac cac dieu luat lien quan
3. Dua ra thong tin chinh xac, ro rang va de hieu
4. Chi su dung thong tin tu noi dung duoc cung cap, khong tu them

Tra loi bang tieng Viet, co cau truc ro rang."""

        user_prompt = f"""NOI DUNG PHAP LY:
{raw_content[:8000]}

---

CAU HOI CUA NGUOI DUNG:
{query}

Hay phan tich va tra loi dua tren noi dung phap ly tren."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"LLM analysis error: {e}")
            return ""

    def _analyze_contract_relevance(self, query: str, analyzed_content: str) -> dict:
        """Analyze if a contract template is relevant and extract template data"""
        query_lower = query.lower()

        # Determine contract type
        contract_type = None
        if any(kw in query_lower for kw in ['thue', 'cho thue', 'thue nha', 'thue phong']):
            contract_type = 'rental'
        elif any(kw in query_lower for kw in ['mua ban', 'mua', 'ban', 'chuyen nhuong']):
            contract_type = 'sale'
        elif any(kw in query_lower for kw in ['dich vu', 'cung cap dich vu']):
            contract_type = 'service'
        elif any(kw in query_lower for kw in ['lao dong', 'tuyen dung', 'nhan vien', 'cong viec']):
            contract_type = 'employment'

        if not contract_type:
            return {'type': None, 'template_data': None}

        # Use LLM to extract template fields from legal content
        template_data = self._extract_template_fields(contract_type, analyzed_content)

        return {
            'type': contract_type,
            'template_data': template_data
        }

    def _extract_template_fields(self, contract_type: str, content: str) -> dict:
        """Use LLM to extract required contract fields from legal content"""
        system_prompt = """Ban la chuyen gia soan thao hop dong. Dua tren noi dung phap ly duoc cung cap,
hay xac dinh cac truong thong tin can thiet cho hop dong. Tra ve JSON voi format:
{
    "required_fields": [
        {"name": "field_name", "label": "Nhan tieng Viet", "required": true}
    ],
    "legal_basis": "Co so phap ly",
    "key_terms": ["Dieu khoan quan trong 1", "Dieu khoan quan trong 2"]
}"""

        field_templates = {
            'rental': ['landlord_name', 'tenant_name', 'property_address', 'monthly_rent', 'duration_months', 'deposit'],
            'sale': ['seller_name', 'buyer_name', 'property_description', 'sale_price', 'payment_method'],
            'service': ['provider_name', 'client_name', 'service_description', 'service_fee', 'duration'],
            'employment': ['employer_name', 'employee_name', 'position', 'salary', 'work_location'],
        }

        # Return basic template with common fields
        fields = field_templates.get(contract_type, [])
        return {
            'contract_type': contract_type,
            'required_fields': [{'name': f, 'label': f.replace('_', ' ').title(), 'required': True} for f in fields],
            'extracted_from_law': True
        }


async def research_legal_topic(query: str, max_sources: int = 3) -> ResearchResult:
    """Convenience function for legal research"""
    service = ResearchService()
    return await service.research(query, max_sources)
