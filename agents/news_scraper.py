import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
TIMEOUT = 60.0


CRIME_KEYWORDS = {
    "pembunuhan": ("pembunuhan", 10),
    "membunuh": ("pembunuhan", 10),
    "pemerkosaan": ("pemerkosaan", 9),
    "perkosa": ("pemerkosaan", 9),
    "kekerasan seksual": ("kekerasan seksual", 9),
    "pelecehan seksual": ("pelecehan seksual", 8),
    "perampokan": ("perampokan", 9),
    "begal": ("perampokan", 9),
    "penculikan": ("penculikan", 8),
    "culik": ("penculikan", 8),
    "penganiayaan": ("penganiayaan", 7),
    "kdrt": ("kdrt", 7),
    "kekerasan": ("kekerasan", 6),
    "narkoba": ("narkoba", 6),
    "pencurian": ("pencurian", 5),
    "maling": ("pencurian", 5),
    "tawuran": ("tawuran", 5),
    "penipuan": ("penipuan", 4),
    "curanmor": ("pencurian", 6),
    "curat": ("pencurian", 6),
    "curas": ("perampokan", 7),
    "penadah": ("pencurian", 5),
    "napi": ("kekerasan", 4),
    "tersangka": ("kekerasan", 4),
    "terdakwa": ("kekerasan", 4),
    "ditangkap": ("kekerasan", 4),
    "ditahan": ("kekerasan", 4),
    "penjara": ("kekerasan", 4),
    "korupsi": ("penipuan", 6),
    "tipikor": ("penipuan", 6),
    "narkotika": ("narkoba", 6),
    "sabu": ("narkoba", 6),
}


NTB_AREAS = {
    "mataram": (-8.5833, 116.1167),
    "ampenan": (-8.5667, 116.0833),
    "cakranegara": (-8.6000, 116.1333),
    "lombok barat": (-8.6000, 116.0833),
    "gerung": (-8.6333, 116.1000),
    "lombok tengah": (-8.7167, 116.2833),
    "praya": (-8.7167, 116.2833),
    "lombok timur": (-8.5333, 116.5333),
    "selong": (-8.6500, 116.5333),
    "lombok utara": (-8.3167, 116.2833),
    "tanjung": (-8.3167, 116.3000),
    "sumbawa": (-8.5000, 117.4167),
    "sumbawa besar": (-8.5000, 117.4167),
    "dompu": (-8.5333, 118.4667),
    "bima": (-8.4500, 118.7167),
    "ntb": (-8.6500, 116.3333),
    "kota mataram": (-8.5833, 116.1167),
    "loteng": (-8.7167, 116.2833),
    "lotim": (-8.5333, 116.5333),
    "lobar": (-8.6000, 116.0833),
    "lotara": (-8.3167, 116.3000),
    "kota bima": (-8.4500, 118.7167),
}


SOURCE_BASE_URL = {
    "detik": "https://www.detik.com",
    "insidelombok": "https://insidelombok.id",
    "postlombok": "https://postlombok.com",
}


MIN_TITLE_LENGTH = 20
RELEVANT_HINTS = (
    "kriminal", "hukum", "polisi", "tersangka", "terdakwa", "kejari", "ditangkap",
    "ditahan", "penjara", "curanmor", "pencurian", "korupsi", "tipikor", "narkoba",
    "sabu", "begal", "tawuran", "penganiayaan", "pemerkosaan", "pembunuhan", "penipuan",
)


@dataclass
class ScrapedArticle:
    source: str
    title: str
    url: str
    snippet: str = ""
    published_at: datetime = None
    crime_type: str = None
    severity: int = 0
    area: str = None
    latitude: float = None
    longitude: float = None


@dataclass
class ScrapeConfig:
    max_articles: int = 100
    max_pages: int = 5
    sources: list = field(default_factory=lambda: ["detik", "insidelombok", "postlombok"])


async def fetch_html(url: str) -> str:
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except Exception:
        return ""


def normalize_link(link: str, source: str) -> str:
    if not link:
        return ""
    return urljoin(SOURCE_BASE_URL.get(source, ""), link)


def is_article_link(link: str, source: str) -> bool:
    if not link:
        return False
    parsed = urlparse(link)
    domain = parsed.netloc.lower()
    if source == "detik" and "detik.com" not in domain:
        return False
    if source == "insidelombok" and "insidelombok.id" not in domain:
        return False
    if source == "postlombok" and "postlombok.com" not in domain:
        return False

    path = (parsed.path or "").lower()
    if source == "detik":
        return "/d-" in path and any(p in path for p in ("/hukum", "/kriminal", "/nusra", "/berita"))
    return path.count("/") >= 2 and not path.endswith("/category/") and "wp-content" not in path


def is_relevant_news(text: str, url: str = "") -> bool:
    combined = f"{text} {url}".lower()
    return any(hint in combined for hint in RELEVANT_HINTS)


async def fetch_article_detail_text(url: str) -> str:
    html = await fetch_html(url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")

    meta_desc = soup.select_one('meta[property="og:description"], meta[name="description"]')
    desc = meta_desc.get("content", "").strip() if meta_desc else ""

    paragraphs = []
    for p in soup.select("article p, .detail__body-text p, .entry-content p, .post-content p, .content p"):
        text = p.get_text(" ", strip=True)
        if text:
            paragraphs.append(text)
        if len(paragraphs) >= 6:
            break

    return f"{desc} {' '.join(paragraphs)}".strip()


def fallback_ntb_area() -> tuple:
    area = "mataram"
    lat, lng = NTB_AREAS[area]
    return area, lat, lng


def build_article_item(source: str, title: str, link: str, snippet: str = "", published_at: datetime = None) -> ScrapedArticle | None:
    combined = f"{title} {snippet}".strip()
    if not is_relevant_news(combined, link):
        return None

    crime_type, severity = detect_crime(combined)
    area, lat, lng = detect_area(f"{combined} {link}")

    if not crime_type:
        crime_type, severity = ("kekerasan", 3)

    if not area:
        area, lat, lng = fallback_ntb_area()

    return ScrapedArticle(
        source=source,
        title=title,
        url=str(link),
        snippet=snippet,
        published_at=published_at,
        crime_type=crime_type,
        severity=severity,
        area=area,
        latitude=lat,
        longitude=lng,
    )


async def extract_candidate_links(source: str, html: str, fallback_selector: str = "a[href]") -> list:
    soup = BeautifulSoup(html, "html.parser")
    candidates = []
    for a in soup.select(fallback_selector):
        href = normalize_link(a.get("href", ""), source)
        title = a.get_text(" ", strip=True)
        if len(title) < MIN_TITLE_LENGTH:
            continue
        if not is_article_link(href, source):
            continue
        candidates.append((title, href))

    seen = set()
    unique = []
    for title, href in candidates:
        if href in seen:
            continue
        seen.add(href)
        unique.append((title, href))
    return unique


def detect_crime(text: str) -> tuple:
    text_lower = text.lower()
    best_type, best_severity = None, 0
    for keyword, (crime_type, severity) in CRIME_KEYWORDS.items():
        if keyword in text_lower and severity > best_severity:
            best_type, best_severity = crime_type, severity
    return best_type, best_severity


def detect_area(text: str) -> tuple:
    text_lower = text.lower()
    for area, coords in NTB_AREAS.items():
        if area in text_lower:
            return area, coords[0], coords[1]
    return None, None, None


def parse_date(date_str: str) -> datetime:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except Exception:
        return None


async def scrape_detik(config: ScrapeConfig) -> list:
    articles = []
    urls = ["https://www.detik.com/bali/hukum-kriminal"]
    for page in range(2, config.max_pages + 1):
        urls.append(f"https://www.detik.com/bali/hukum-kriminal/indeks/{page}")

    for url in urls:
        if len(articles) >= config.max_articles:
            break
        html = await fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("article") or soup.select(".list-content article, .media__item")
        page_candidates = []
        for item in items:
            if len(articles) >= config.max_articles:
                break
            title_el = item.select_one("h3.media__title a, h2 a, .media__title a, a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = normalize_link(title_el.get("href", ""), "detik")
            if not title or not link:
                continue
            snippet_el = item.select_one(".media__desc, .media__subtitle, p")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            date_el = item.select_one(".media__date span, time, .date")
            published_at = parse_date(date_el.get("title") or date_el.get("datetime") if date_el else None)
            page_candidates.append((title, link, snippet, published_at))

        if not page_candidates:
            for title, link in await extract_candidate_links("detik", html):
                page_candidates.append((title, link, "", None))

        for title, link, snippet, published_at in page_candidates:
            if len(articles) >= config.max_articles:
                break
            detail = await fetch_article_detail_text(link)
            enriched_snippet = f"{snippet} {detail}".strip()
            article = build_article_item("detik", title, link, enriched_snippet, published_at)
            if article:
                articles.append(article)
    return articles


async def scrape_insidelombok(config: ScrapeConfig) -> list:
    articles = []
    base_urls = ["https://insidelombok.id/category/hukum/", "https://insidelombok.id/category/kriminal/"]
    urls = []
    for base in base_urls:
        urls.append(base)
        for page in range(2, config.max_pages + 1):
            urls.append(f"{base}page/{page}/")

    for url in urls:
        if len(articles) >= config.max_articles:
            break
        html = await fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("article") or soup.select(".post, .entry")
        page_candidates = []
        for item in items:
            if len(articles) >= config.max_articles:
                break
            title_el = item.select_one("h2 a, h3 a, .entry-title a, .post-title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = normalize_link(title_el.get("href", ""), "insidelombok")
            if not title or not link:
                continue
            snippet_el = item.select_one(".entry-content p, .entry-summary p, .post-excerpt")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            date_el = item.select_one("time, .entry-date, .post-date")
            published_at = parse_date(date_el.get("datetime") if date_el else None)
            page_candidates.append((title, link, snippet, published_at))

        if not page_candidates:
            for title, link in await extract_candidate_links("insidelombok", html):
                page_candidates.append((title, link, "", None))

        for title, link, snippet, published_at in page_candidates:
            if len(articles) >= config.max_articles:
                break
            detail = await fetch_article_detail_text(link)
            enriched_snippet = f"{snippet} {detail}".strip()
            article = build_article_item("insidelombok", title, link, enriched_snippet, published_at)
            if article:
                articles.append(article)
    return articles


async def scrape_postlombok(config: ScrapeConfig) -> list:
    articles = []
    base_url = "https://postlombok.com/"
    urls = [base_url]
    for page in range(2, config.max_pages + 1):
        urls.append(f"{base_url}page/{page}/")

    for url in urls:
        if len(articles) >= config.max_articles:
            break
        html = await fetch_html(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        items = soup.select("article, .post, .entry")
        page_candidates = []
        for item in items:
            if len(articles) >= config.max_articles:
                break
            title_el = item.select_one("h2 a, h3 a, .entry-title a, .post-title a")
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            link = normalize_link(title_el.get("href", ""), "postlombok")
            if not title or not link:
                continue
            snippet_el = item.select_one(".entry-content p, .entry-summary p, .post-excerpt")
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            date_el = item.select_one("time, .entry-date, .post-date")
            published_at = parse_date(date_el.get("datetime") if date_el else None)
            page_candidates.append((title, link, snippet, published_at))

        if not page_candidates:
            for title, link in await extract_candidate_links("postlombok", html):
                page_candidates.append((title, link, "", None))

        for title, link, snippet, published_at in page_candidates:
            if len(articles) >= config.max_articles:
                break
            detail = await fetch_article_detail_text(link)
            enriched_snippet = f"{snippet} {detail}".strip()
            article = build_article_item("postlombok", title, link, enriched_snippet, published_at)
            if article:
                articles.append(article)
    return articles


async def run(config: ScrapeConfig = None) -> list:
    if config is None:
        config = ScrapeConfig()
    all_articles = []
    scrapers = {"detik": scrape_detik, "insidelombok": scrape_insidelombok, "postlombok": scrape_postlombok}
    for source in config.sources:
        if source in scrapers:
            articles = await scrapers[source](config)
            all_articles.extend(articles)
    seen_urls = set()
    unique = []
    for a in all_articles:
        if a.url not in seen_urls:
            seen_urls.add(a.url)
            unique.append(a)
    return unique
