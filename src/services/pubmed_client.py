"""PubMed E-utilities async client.

Endpoints used:
  esearch — search PubMed and return PMIDs
  efetch  — fetch full article records as XML

Rate limits (NCBI policy):
  3 req/s without an API key
  10 req/s with an API key (set NCBI_API_KEY in .env)

Reference: https://www.ncbi.nlm.nih.gov/books/NBK25497/
"""

from __future__ import annotations

import asyncio
import logging
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Any

import httpx
from pydantic import BaseModel, Field

from src.core.config import settings

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EFETCH_BATCH_SIZE = 200  # NCBI recommended max per request

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "may": 5, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class AuthorData(BaseModel):
    name: str
    affiliation: str | None = None


class ArticleData(BaseModel):
    pmid: str
    title: str
    abstract: str | None = None
    authors: list[AuthorData] = Field(default_factory=list)
    journal: str | None = None
    publication_date: date | None = None
    doi: str | None = None
    mesh_headings: list[str] = Field(default_factory=list)
    article_type: str | None = None


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Async token-bucket rate limiter (serialises requests through a lock)."""

    def __init__(self, rate: float) -> None:
        self._min_interval = 1.0 / rate
        self._last_call_at: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            wait = self._min_interval - (now - self._last_call_at)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_call_at = time.monotonic()


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class PubMedClient:
    """Async PubMed E-utilities client.

    Prefer using as an async context manager so the underlying
    httpx session is properly closed::

        async with PubMedClient() as client:
            pmids = await client.esearch("SGLT2 inhibitors AND heart failure")
            articles = await client.efetch(pmids)
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._api_key = api_key or settings.ncbi_api_key
        rate = 10.0 if self._api_key else 3.0
        self._rate_limiter = RateLimiter(rate)
        self._client = httpx.AsyncClient(
            base_url=EUTILS_BASE,
            timeout=timeout,
            # NCBI requires a descriptive User-Agent for API access
            headers={"User-Agent": "MedLitAgent/1.0 (contact@medlit.example.com)"},
        )

    async def __aenter__(self) -> PubMedClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def esearch(
        self,
        query: str,
        max_results: int = 100,
        date_range: tuple[str, str] | None = None,
    ) -> list[str]:
        """Search PubMed and return a list of PMIDs.

        Args:
            query: PubMed query string (E-utilities syntax / MeSH terms).
            max_results: Maximum number of PMIDs to return (default 100).
            date_range: Optional ``(mindate, maxdate)`` pair in
                ``"YYYY/MM/DD"`` format, e.g. ``("2024/01/01", "2024/12/31")``.

        Returns:
            Ordered list of PMID strings (most recent first).
        """
        await self._rate_limiter.acquire()

        params: dict[str, str] = {
            "db": "pubmed",
            "term": query,
            "retmax": str(max_results),
            "retmode": "json",
            "sort": "pub+date",
        }
        if date_range:
            params["mindate"] = date_range[0]
            params["maxdate"] = date_range[1]
            params["datetype"] = "pdat"
        if self._api_key:
            params["api_key"] = self._api_key

        response = await self._client.get("/esearch.fcgi", params=params)
        response.raise_for_status()

        data = response.json()
        pmids: list[str] = data["esearchresult"]["idlist"]
        logger.info(
            "esearch: %d PMIDs for query %r (max_results=%d)",
            len(pmids),
            query[:80],
            max_results,
        )
        return pmids

    async def efetch(self, pmids: list[str]) -> list[ArticleData]:
        """Fetch full article records for a list of PMIDs.

        PMIDs are batched automatically in groups of
        :data:`EFETCH_BATCH_SIZE` to stay within NCBI limits.

        Args:
            pmids: List of PubMed IDs to fetch.

        Returns:
            Parsed :class:`ArticleData` objects (order matches input where
            parsing succeeds; failed articles are skipped with a warning).
        """
        if not pmids:
            return []

        articles: list[ArticleData] = []
        for i in range(0, len(pmids), EFETCH_BATCH_SIZE):
            batch = pmids[i : i + EFETCH_BATCH_SIZE]
            articles.extend(await self._efetch_batch(batch))
        return articles

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _efetch_batch(self, pmids: list[str]) -> list[ArticleData]:
        await self._rate_limiter.acquire()

        params: dict[str, str] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "rettype": "xml",
            "retmode": "xml",
        }
        if self._api_key:
            params["api_key"] = self._api_key

        response = await self._client.get("/efetch.fcgi", params=params)
        response.raise_for_status()

        root = ET.fromstring(response.text)
        articles: list[ArticleData] = []
        for elem in root.findall(".//PubmedArticle"):
            try:
                articles.append(self._parse_article(elem))
            except Exception:
                pmid = elem.findtext(".//PMID", default="?")
                logger.warning("Failed to parse article PMID=%s", pmid, exc_info=True)

        logger.info("efetch: parsed %d / %d articles", len(articles), len(pmids))
        return articles

    # ------------------------------------------------------------------
    # XML parsers
    # ------------------------------------------------------------------

    def _parse_article(self, elem: ET.Element) -> ArticleData:
        mc = elem.find("MedlineCitation")
        if mc is None:
            raise ValueError("Missing MedlineCitation element")
        article = mc.find("Article")
        if article is None:
            raise ValueError("Missing Article element")

        return ArticleData(
            pmid=mc.findtext("PMID", default="").strip(),
            title=self._parse_title(article),
            abstract=self._parse_abstract(article),
            authors=self._parse_authors(article),
            journal=self._parse_journal(article),
            publication_date=self._parse_pub_date(article),
            doi=self._parse_doi(article, elem),
            mesh_headings=self._parse_mesh(mc),
            article_type=self._parse_article_type(article),
        )

    @staticmethod
    def _text(parent: ET.Element, path: str) -> str | None:
        elem = parent.find(path)
        if elem is None:
            return None
        text = "".join(elem.itertext()).strip()
        return text or None

    def _parse_title(self, article: ET.Element) -> str:
        return self._text(article, "ArticleTitle") or "(no title)"

    def _parse_abstract(self, article: ET.Element) -> str | None:
        abstract_elem = article.find("Abstract")
        if abstract_elem is None:
            return None

        parts: list[str] = []
        for text_elem in abstract_elem.findall("AbstractText"):
            content = "".join(text_elem.itertext()).strip()
            if not content:
                continue
            label = text_elem.get("Label")
            parts.append(f"{label}: {content}" if label else content)

        return "\n\n".join(parts) if parts else None

    def _parse_authors(self, article: ET.Element) -> list[AuthorData]:
        authors: list[AuthorData] = []
        for author_elem in article.findall(".//AuthorList/Author"):
            # Corporate / collective authors
            collective = self._text(author_elem, "CollectiveName")
            if collective:
                authors.append(AuthorData(name=collective))
                continue

            last = self._text(author_elem, "LastName") or ""
            fore = self._text(author_elem, "ForeName") or ""
            name = f"{fore} {last}".strip() if fore else last
            if not name:
                continue

            affiliation = self._text(author_elem, "AffiliationInfo/Affiliation")
            authors.append(AuthorData(name=name, affiliation=affiliation))
        return authors

    def _parse_journal(self, article: ET.Element) -> str | None:
        return self._text(article, "Journal/Title")

    def _parse_pub_date(self, article: ET.Element) -> date | None:
        # Priority: electronic ArticleDate > JournalIssue PubDate
        for path in ("ArticleDate", "Journal/JournalIssue/PubDate"):
            date_elem = article.find(path)
            if date_elem is None:
                continue

            year_str = self._text(date_elem, "Year")
            month_str = self._text(date_elem, "Month") or "1"
            day_str = self._text(date_elem, "Day") or "1"
            medline_date = self._text(date_elem, "MedlineDate")

            if year_str:
                try:
                    return date(
                        int(year_str),
                        self._parse_month(month_str),
                        int(day_str),
                    )
                except (ValueError, TypeError):
                    logger.debug("Could not parse date: year=%s month=%s day=%s", year_str, month_str, day_str)

            if medline_date:
                # e.g. "2024 Jan-Feb" or "2024 Winter"
                parts = medline_date.split()
                try:
                    return date(int(parts[0]), 1, 1)
                except (ValueError, IndexError):
                    pass

        return None

    @staticmethod
    def _parse_month(month_str: str) -> int:
        try:
            return int(month_str)
        except ValueError:
            return _MONTH_MAP.get(month_str[:3].lower(), 1)

    def _parse_doi(self, article: ET.Element, pubmed_article: ET.Element) -> str | None:
        # 1. ELocationID inside Article
        for loc in article.findall("ELocationID"):
            if loc.get("EIdType") == "doi":
                return (loc.text or "").strip() or None

        # 2. ArticleId inside PubmedData
        for aid in pubmed_article.findall(".//ArticleIdList/ArticleId"):
            if aid.get("IdType") == "doi":
                return (aid.text or "").strip() or None

        return None

    def _parse_mesh(self, mc: ET.Element) -> list[str]:
        return [
            "".join(desc.itertext()).strip()
            for desc in mc.findall(".//MeshHeadingList/MeshHeading/DescriptorName")
            if "".join(desc.itertext()).strip()
        ]

    def _parse_article_type(self, article: ET.Element) -> str | None:
        types = [
            "".join(pt.itertext()).strip()
            for pt in article.findall(".//PublicationTypeList/PublicationType")
            if "".join(pt.itertext()).strip()
        ]
        if not types:
            return None
        # Prefer a specific type over the generic "Journal Article" label
        specific = [t for t in types if t != "Journal Article"]
        return "; ".join(specific) if specific else types[0]
