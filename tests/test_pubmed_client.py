"""Tests for src/services/pubmed_client.py.

HTTP calls are mocked by replacing pubmed_client._client.get with AsyncMock
so tests are independent of the real NCBI API and of URL-merging quirks.
"""

from datetime import date
from unittest.mock import AsyncMock

import httpx
import pytest

from src.services.pubmed_client import (
    PubMedClient,
    RateLimiter,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DUMMY_REQUEST = httpx.Request("GET", "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/test")


def _esearch_response(pmids: list[str]) -> httpx.Response:
    return httpx.Response(
        200, json={"esearchresult": {"idlist": pmids}}, request=_DUMMY_REQUEST
    )


def _efetch_response(xml_text: str) -> httpx.Response:
    return httpx.Response(
        200,
        text=xml_text,
        headers={"content-type": "application/xml"},
        request=_DUMMY_REQUEST,
    )


def _error_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, request=_DUMMY_REQUEST)


def _article_xml(
    *,
    pmid: str = "12345",
    title: str = "Test Title",
    abstract: str | None = "Background text.",
    abstract_structured: dict | None = None,
    authors: list[dict] | None = None,
    journal: str = "Test Journal",
    pub_year: str | None = "2024",
    pub_month: str = "Jan",
    pub_day: str = "15",
    medline_date: str | None = None,
    doi: str | None = "10.1234/test",
    doi_in_articleid: bool = False,
    mesh_headings: list[str] | None = None,
    article_types: list[str] | None = None,
    missing_medline_citation: bool = False,
    missing_article: bool = False,
) -> str:
    if missing_medline_citation:
        return "<PubmedArticle></PubmedArticle>"
    if missing_article:
        return "<PubmedArticle><MedlineCitation><PMID>99</PMID></MedlineCitation></PubmedArticle>"

    # Abstract
    if abstract_structured:
        abs_parts = "".join(
            f'<AbstractText Label="{label}">{text}</AbstractText>'
            for label, text in abstract_structured.items()
        )
        abstract_xml = f"<Abstract>{abs_parts}</Abstract>"
    elif abstract:
        abstract_xml = f"<Abstract><AbstractText>{abstract}</AbstractText></Abstract>"
    else:
        abstract_xml = ""

    # Authors
    authors = authors or [{"last": "Smith", "fore": "John", "affiliation": "MIT"}]
    authors_xml = ""
    for a in authors:
        if "collective" in a:
            authors_xml += f"<Author><CollectiveName>{a['collective']}</CollectiveName></Author>"
        else:
            aff = f"<AffiliationInfo><Affiliation>{a.get('affiliation', '')}</Affiliation></AffiliationInfo>"
            authors_xml += (
                f"<Author>"
                f"<LastName>{a.get('last', '')}</LastName>"
                f"<ForeName>{a.get('fore', '')}</ForeName>"
                f"{aff}"
                f"</Author>"
            )

    # DOI
    if doi and not doi_in_articleid:
        doi_xml = f'<ELocationID EIdType="doi">{doi}</ELocationID>'
        articleid_doi_xml = ""
    elif doi and doi_in_articleid:
        doi_xml = ""
        articleid_doi_xml = f'<ArticleId IdType="doi">{doi}</ArticleId>'
    else:
        doi_xml = ""
        articleid_doi_xml = ""

    # Publication date
    if medline_date:
        pubdate_xml = f"<PubDate><MedlineDate>{medline_date}</MedlineDate></PubDate>"
    elif pub_year:
        pubdate_xml = (
            f"<PubDate>"
            f"<Year>{pub_year}</Year>"
            f"<Month>{pub_month}</Month>"
            f"<Day>{pub_day}</Day>"
            f"</PubDate>"
        )
    else:
        pubdate_xml = ""

    # MeSH
    mesh_xml = "".join(
        f"<MeshHeading><DescriptorName>{h}</DescriptorName></MeshHeading>"
        for h in (mesh_headings or ["Heart Failure"])
    )

    # Article types
    types_xml = "".join(
        f"<PublicationType>{t}</PublicationType>"
        for t in (article_types or ["Journal Article"])
    )

    return (
        f"<PubmedArticle>"
        f"<MedlineCitation>"
        f"<PMID>{pmid}</PMID>"
        f"<Article>"
        f"<Journal>"
        f"<Title>{journal}</Title>"
        f"<JournalIssue>{pubdate_xml}</JournalIssue>"
        f"</Journal>"
        f"<ArticleTitle>{title}</ArticleTitle>"
        f"{abstract_xml}"
        f"<AuthorList>{authors_xml}</AuthorList>"
        f"{doi_xml}"
        f"<PublicationTypeList>{types_xml}</PublicationTypeList>"
        f"</Article>"
        f"<MeshHeadingList>{mesh_xml}</MeshHeadingList>"
        f"</MedlineCitation>"
        f"<PubmedData><ArticleIdList>{articleid_doi_xml}</ArticleIdList></PubmedData>"
        f"</PubmedArticle>"
    )


def _wrap_articles(*articles_xml: str) -> str:
    return "<PubmedArticleSet>" + "".join(articles_xml) + "</PubmedArticleSet>"


@pytest.fixture
async def client() -> PubMedClient:
    """PubMedClient with rate limiting disabled."""
    c = PubMedClient()
    c._rate_limiter.acquire = AsyncMock()
    yield c
    await c._client.aclose()


# ---------------------------------------------------------------------------
# esearch tests
# ---------------------------------------------------------------------------

async def test_esearch_returns_pmids(client):
    client._client.get = AsyncMock(return_value=_esearch_response(["111", "222"]))
    pmids = await client.esearch("SGLT2 AND heart failure")
    assert pmids == ["111", "222"]
    client._client.get.assert_called_once()
    _, kwargs = client._client.get.call_args
    assert kwargs["params"]["term"] == "SGLT2 AND heart failure"
    assert kwargs["params"]["retmode"] == "json"


async def test_esearch_empty_results(client):
    client._client.get = AsyncMock(return_value=_esearch_response([]))
    pmids = await client.esearch("obscure query")
    assert pmids == []


async def test_esearch_with_date_range(client):
    client._client.get = AsyncMock(return_value=_esearch_response(["999"]))
    await client.esearch("query", date_range=("2024/01/01", "2024/12/31"))
    _, kwargs = client._client.get.call_args
    assert kwargs["params"]["mindate"] == "2024/01/01"
    assert kwargs["params"]["maxdate"] == "2024/12/31"
    assert kwargs["params"]["datetype"] == "pdat"


async def test_esearch_without_date_range_omits_params(client):
    client._client.get = AsyncMock(return_value=_esearch_response([]))
    await client.esearch("query")
    _, kwargs = client._client.get.call_args
    assert "mindate" not in kwargs["params"]


async def test_esearch_with_api_key_sends_param():
    c = PubMedClient(api_key="MYKEY")
    c._rate_limiter.acquire = AsyncMock()
    c._client.get = AsyncMock(return_value=_esearch_response([]))
    await c.esearch("q")
    _, kwargs = c._client.get.call_args
    assert kwargs["params"]["api_key"] == "MYKEY"
    await c._client.aclose()


async def test_esearch_http_error_raises(client):
    client._client.get = AsyncMock(return_value=_error_response(429))
    with pytest.raises(httpx.HTTPStatusError):
        await client.esearch("q")


async def test_esearch_respects_max_results(client):
    client._client.get = AsyncMock(return_value=_esearch_response([]))
    await client.esearch("q", max_results=50)
    _, kwargs = client._client.get.call_args
    assert kwargs["params"]["retmax"] == "50"


# ---------------------------------------------------------------------------
# efetch tests
# ---------------------------------------------------------------------------

async def test_efetch_empty_list_returns_empty(client):
    result = await client.efetch([])
    assert result == []


async def test_efetch_parses_full_article(client):
    xml = _wrap_articles(_article_xml(
        pmid="12345",
        title="SGLT2 in Heart Failure",
        abstract="We studied SGLT2 inhibitors.",
        authors=[{"last": "Smith", "fore": "John", "affiliation": "Harvard"}],
        journal="NEJM",
        pub_year="2024",
        pub_month="Mar",
        pub_day="15",
        doi="10.1056/test",
        mesh_headings=["Heart Failure", "SGLT2"],
        article_types=["Journal Article", "Randomized Controlled Trial"],
    ))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["12345"])

    assert len(articles) == 1
    a = articles[0]
    assert a.pmid == "12345"
    assert a.title == "SGLT2 in Heart Failure"
    assert a.abstract == "We studied SGLT2 inhibitors."
    assert len(a.authors) == 1
    assert a.authors[0].name == "John Smith"
    assert a.authors[0].affiliation == "Harvard"
    assert a.journal == "NEJM"
    assert a.publication_date == date(2024, 3, 15)
    assert a.doi == "10.1056/test"
    assert a.mesh_headings == ["Heart Failure", "SGLT2"]
    assert a.article_type == "Randomized Controlled Trial"


async def test_efetch_structured_abstract(client):
    xml = _wrap_articles(_article_xml(
        abstract=None,
        abstract_structured={"BACKGROUND": "Background text.", "METHODS": "Methods used."},
    ))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].abstract == "BACKGROUND: Background text.\n\nMETHODS: Methods used."


async def test_efetch_no_abstract_returns_none(client):
    xml = _wrap_articles(_article_xml(abstract=None))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].abstract is None


async def test_efetch_collective_author(client):
    xml = _wrap_articles(_article_xml(authors=[{"collective": "DAPA-HF Investigators"}]))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].authors[0].name == "DAPA-HF Investigators"
    assert articles[0].authors[0].affiliation is None


async def test_efetch_author_last_name_only(client):
    xml = _wrap_articles(_article_xml(authors=[{"last": "Jones", "fore": ""}]))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].authors[0].name == "Jones"


async def test_efetch_doi_from_elocationid(client):
    xml = _wrap_articles(_article_xml(doi="10.1234/eloc", doi_in_articleid=False))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].doi == "10.1234/eloc"


async def test_efetch_doi_from_articleid_list(client):
    xml = _wrap_articles(_article_xml(doi="10.1234/aid", doi_in_articleid=True))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].doi == "10.1234/aid"


async def test_efetch_no_doi_returns_none(client):
    xml = _wrap_articles(_article_xml(doi=None))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].doi is None


async def test_efetch_medline_date_fallback(client):
    xml = _wrap_articles(_article_xml(pub_year=None, medline_date="2024 Jan-Feb"))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].publication_date == date(2024, 1, 1)


async def test_efetch_numeric_month(client):
    xml = _wrap_articles(_article_xml(pub_year="2023", pub_month="6", pub_day="1"))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].publication_date == date(2023, 6, 1)


async def test_efetch_no_pub_date_returns_none(client):
    xml = _wrap_articles(_article_xml(pub_year=None, medline_date=None))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].publication_date is None


async def test_efetch_article_type_prefers_specific_over_journal_article(client):
    xml = _wrap_articles(_article_xml(article_types=["Journal Article", "Randomized Controlled Trial"]))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].article_type == "Randomized Controlled Trial"


async def test_efetch_article_type_only_journal_article(client):
    xml = _wrap_articles(_article_xml(article_types=["Journal Article"]))
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].article_type == "Journal Article"


async def test_efetch_article_type_none_when_no_types(client):
    # Build XML with no PublicationTypeList
    xml = (
        "<PubmedArticleSet><PubmedArticle><MedlineCitation>"
        "<PMID>1</PMID>"
        "<Article>"
        "<Journal><Title>J</Title><JournalIssue></JournalIssue></Journal>"
        "<ArticleTitle>T</ArticleTitle>"
        "<PublicationTypeList></PublicationTypeList>"
        "</Article>"
        "<MeshHeadingList></MeshHeadingList>"
        "</MedlineCitation><PubmedData><ArticleIdList></ArticleIdList></PubmedData>"
        "</PubmedArticle></PubmedArticleSet>"
    )
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["1"])
    assert articles[0].article_type is None


async def test_efetch_malformed_article_skipped_continues(client):
    """A bad article element should be skipped; valid ones still parsed."""
    bad = "<PubmedArticle></PubmedArticle>"  # missing MedlineCitation
    good = _article_xml(pmid="999", title="Good Article")
    xml = _wrap_articles(bad, good)
    client._client.get = AsyncMock(return_value=_efetch_response(xml))
    articles = await client.efetch(["X", "999"])
    assert len(articles) == 1
    assert articles[0].pmid == "999"


async def test_efetch_batches_large_request(client):
    """201 PMIDs should trigger two HTTP calls (batch of 200 + batch of 1)."""
    single_xml = _wrap_articles(_article_xml(pmid="1"))
    client._client.get = AsyncMock(return_value=_efetch_response(single_xml))
    pmids = [str(i) for i in range(201)]
    await client.efetch(pmids)
    assert client._client.get.call_count == 2


async def test_efetch_http_error_raises(client):
    client._client.get = AsyncMock(return_value=_error_response(500))
    with pytest.raises(httpx.HTTPStatusError):
        await client.efetch(["1"])


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

async def test_rate_limiter_first_call_is_immediate():
    import time
    limiter = RateLimiter(rate=3.0)
    start = time.monotonic()
    await limiter.acquire()
    assert time.monotonic() - start < 0.05  # well under 1/3 s


async def test_rate_limiter_throttles_second_call():
    import time
    limiter = RateLimiter(rate=20.0)  # 50ms interval — fast but measurable
    await limiter.acquire()
    start = time.monotonic()
    await limiter.acquire()
    assert time.monotonic() - start >= 0.04


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

async def test_context_manager_closes_client():
    async with PubMedClient() as c:
        assert not c._client.is_closed
    assert c._client.is_closed


async def test_api_key_sets_higher_rate():
    with_key = PubMedClient(api_key="KEY")
    without_key = PubMedClient()
    assert with_key._rate_limiter._min_interval < without_key._rate_limiter._min_interval
    await with_key._client.aclose()
    await without_key._client.aclose()
