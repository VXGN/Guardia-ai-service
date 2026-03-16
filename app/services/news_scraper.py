import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

TIMEOUT = 60.0
DETAIL_FETCH_CONCURRENCY = 8

DEFAULT_MAX_ARTICLES_PER_SOURCE = 200
DEFAULT_MAX_PAGES = 10


@dataclass
class ScrapeConfig:
    """Configuration for controlling scrape behavior."""
    max_articles_per_source: int = DEFAULT_MAX_ARTICLES_PER_SOURCE
    max_pages: int = DEFAULT_MAX_PAGES
    include_sources: list[str] = field(default_factory=lambda: ["detik", "kompas", "insidelombok", "postlombok"])


@dataclass
class RawArticle:
    source: str
    title: str
    url: str
    snippet: str | None = None
    published_at: datetime | None = None


async def _fetch_html(url: str) -> str | None:
    """Fetch HTML content from a URL."""
    try:
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=TIMEOUT,
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as e:
        logger.error("Failed to fetch %s: %s", url, e)
        return None


def _extract_first_paragraph(html: str) -> str | None:
    """Extract the first meaningful paragraph from article detail HTML."""
    soup = BeautifulSoup(html, "html.parser")

    selectors = [
        "article p",
        ".entry-content p",
        ".post-content p",
        ".content p",
        ".article-content p",
        ".read__content p",
        "p",
    ]

    for selector in selectors:
        paragraphs = soup.select(selector)
        for p in paragraphs:
            text = p.get_text(" ", strip=True)
            if len(text) >= 40:
                return text
    return None


async def _fetch_first_paragraph(url: str) -> str | None:
    html = await _fetch_html(url)
    if not html:
        return None
    return _extract_first_paragraph(html)


def _deduplicate_articles(articles: list[RawArticle]) -> list[RawArticle]:
    """Remove duplicate articles by URL."""
    seen_urls: set[str] = set()
    unique: list[RawArticle] = []
    for a in articles:
        if a.url not in seen_urls:
            seen_urls.add(a.url)
            unique.append(a)
    return unique


async def scrape_detik(config: ScrapeConfig | None = None) -> list[RawArticle]:
    """
    Scrape crime news possibly related to NTB from detikBali.

    Catatan:
    - Kanal ini bukan NTB, jadi kata kunci NTB bisa sangat jarang muncul.
    - Untuk memastikan dulu selector benar, kita longgarkan filter NTB.
    """
    if config is None:
        config = ScrapeConfig()

    articles: list[RawArticle] = []
    base_urls = [
        "https://www.detik.com/tag/nusa-tenggara-barat/?sortby=time&page=",
        "https://www.detik.com/bali/hukum-kriminal/indeks?page=",
        "https://www.detik.com/tag/polda-ntb/?sortby=time&page="
    ]
    urls = []
    for base_url in base_urls:
        urls.append(base_url)
        if "indeks" in base_url or "page=" in base_url:
            for page in range(2, config.max_pages + 1):
                urls.append(f"{base_url}{page}")

    ntb_keywords = [
        "ntb",
        "lombok",
        "mataram",
        "sumbawa",
        "bima",
        "dompu",
        "nusa tenggara barat",
        "praya",
        "selong",
    ]

    for url in urls:
        if len(articles) >= config.max_articles_per_source:
            break

        html = await _fetch_html(url)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        items = soup.select("article")
        if not items:
            items = soup.select(".list-content article, .media__item")
        logger.info("detik %s -> %d article items", url, len(items))

        for item in items:
            if len(articles) >= config.max_articles_per_source:
                break

            title_el = item.select_one(
                "h3.media__title a, h2 a, .media__title a, a"
            )
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if not title or not link:
                continue

            snippet_el = item.select_one(".media__desc, .media__subtitle, p")
            snippet = snippet_el.get_text(strip=True) if snippet_el else None

            combined = (title + " " + (snippet or "")).lower()
            # if not any(kw in combined for kw in ntb_keywords):
            #     continue

            date_el = item.select_one(".media__date span, time, .date")
            published_at = None
            if date_el:
                date_str = date_el.get("title") or date_el.get("datetime")
                if date_str:
                    try:
                        published_at = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        pass

            articles.append(
                RawArticle(
                    source="detik",
                    title=title,
                    url=str(link),
                    snippet=snippet,
                    published_at=published_at,
                )
            )

    articles = _deduplicate_articles(articles)
    logger.info("Scraped %d articles from detik.com (unfiltered NTB)", len(articles))
    return articles[:config.max_articles_per_source]


async def scrape_kompas(config: ScrapeConfig | None = None) -> list[RawArticle]:
    logger.warning("Kompas regional Nusa Tenggara 404, scraper_kompas dinonaktifkan sementara.")
    return []


async def scrape_insidelombok(config: ScrapeConfig | None = None) -> list[RawArticle]:
    """Scrape crime / law news from insidelombok.com (kategori Kriminal & Hukum)."""
    if config is None:
        config = ScrapeConfig()

    articles: list[RawArticle] = []
    base_categories = [
        "https://insidelombok.id/category/hukum/",
        "https://insidelombok.id/category/kriminal/",
    ]
    urls = []
    for base_url in base_categories:
        urls.append(base_url)
        for page in range(2, config.max_pages + 1):
            urls.append(f"{base_url}page/{page}/")

    for url in urls:
        if len(articles) >= config.max_articles_per_source:
            break

        html = await _fetch_html(url)
        if not html:
            logger.warning("No HTML for %s", url)
            continue

        soup = BeautifulSoup(html, "html.parser")

        items = soup.select("article")
        if not items:
            items = soup.select(".post, .entry")
        logger.info("InsideLombok %s -> %d article items", url, len(items))

        for item in items:
            if len(articles) >= config.max_articles_per_source:
                break

            title_el = item.select_one("h2 a, h3 a, .entry-title a, .post-title a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if not title or not link:
                continue

            snippet_el = item.select_one(
                ".entry-content p, .entry-summary p, .post-excerpt, .excerpt"
            )
            snippet = snippet_el.get_text(strip=True) if snippet_el else None

            date_el = item.select_one("time, .entry-date, .post-date")
            published_at = None
            if date_el:
                date_str = date_el.get("datetime") or date_el.get_text(strip=True)
                if date_str:
                    try:
                        published_at = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

            articles.append(
                RawArticle(
                    source="insidelombok",
                    title=title,
                    url=str(link),
                    snippet=snippet,
                    published_at=published_at,
                )
            )

    unique = _deduplicate_articles(articles)
    logger.info("Scraped %d articles from insidelombok", len(unique))
    return unique[:config.max_articles_per_source]


async def scrape_postlombok(config: ScrapeConfig | None = None) -> list[RawArticle]:
    """Scrape crime / law news from postlombok.com."""
    if config is None:
        config = ScrapeConfig()

    articles: list[RawArticle] = []
    base_url = "https://postlombok.com/"
    urls = [base_url]
    for page in range(2, config.max_pages + 1):
        urls.append(f"{base_url}page/{page}/")

    for url in urls:
        if len(articles) >= config.max_articles_per_source:
            break

        html = await _fetch_html(url)
        if not html:
            logger.warning("No HTML for %s", url)
            continue

        soup = BeautifulSoup(html, "html.parser")

        items = soup.select("article, .post, .entry")
        logger.info("PostLombok %s -> %d article items", url, len(items))

        for item in items:
            if len(articles) >= config.max_articles_per_source:
                break

            title_el = item.select_one("h2 a, h3 a, .entry-title a, .post-title a")
            if not title_el:
                continue

            title = title_el.get_text(strip=True)
            link = title_el.get("href", "")
            if not title or not link:
                continue

            snippet_el = item.select_one(
                ".entry-content p, .entry-summary p, .post-excerpt, .excerpt"
            )
            snippet = snippet_el.get_text(strip=True) if snippet_el else None

            date_el = item.select_one("time, .entry-date, .post-date")
            published_at = None
            if date_el:
                date_str = date_el.get("datetime") or date_el.get_text(strip=True)
                if date_str:
                    try:
                        published_at = datetime.fromisoformat(
                            date_str.replace("Z", "+00:00")
                        )
                    except Exception:
                        pass

            articles.append(
                RawArticle(
                    source="postlombok",
                    title=title,
                    url=str(link),
                    snippet=snippet,
                    published_at=published_at,
                )
            )

    unique = _deduplicate_articles(articles)
    logger.info("Scraped %d articles from postlombok", len(unique))
    return unique[:config.max_articles_per_source]


async def scrape_all_sources(config: ScrapeConfig | None = None) -> list[RawArticle]:
    if config is None:
        config = ScrapeConfig()

    all_articles: list[RawArticle] = []

    scrapers = [
        ("detik", scrape_detik),
        ("kompas", scrape_kompas),
        ("insidelombok", scrape_insidelombok),
        ("postlombok", scrape_postlombok),
    ]

    for name, scraper_fn in scrapers:
        if name not in config.include_sources:
            logger.info("Skipping scraper %s (not in include_sources)", name)
            continue

        try:
            logger.info("Running scraper: %s", name)
            articles = await scraper_fn(config)
            logger.info("Scraper %s returned %d articles", name, len(articles))
            all_articles.extend(articles)
        except Exception as e:
            logger.error("Scraper %s failed: %s", name, e)

    logger.info("Total scraped: %d articles from all sources", len(all_articles))
    return all_articles


async def enrich_articles_with_first_paragraph(
    articles: list[RawArticle],
    max_to_fetch: int | None = None,
) -> tuple[list[RawArticle], int]:
    """Enrich missing snippets by fetching each article detail's first paragraph."""
    targets = [a for a in articles if not a.snippet]
    if max_to_fetch is not None:
        targets = targets[:max_to_fetch]

    if not targets:
        return articles, 0

    semaphore = asyncio.Semaphore(DETAIL_FETCH_CONCURRENCY)

    async def enrich_one(article: RawArticle) -> bool:
        async with semaphore:
            paragraph = await _fetch_first_paragraph(article.url)
            if paragraph:
                article.snippet = paragraph
                return True
            return False

    results = await asyncio.gather(*(enrich_one(a) for a in targets), return_exceptions=True)

    enriched_count = 0
    for result in results:
        if isinstance(result, bool) and result:
            enriched_count += 1

    if enriched_count > 0:
        logger.info("Enriched %d article snippets from detail pages", enriched_count)

    return articles, enriched_count
