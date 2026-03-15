from dataclasses import dataclass
from datetime import datetime
from typing import List


CATEGORY_WEIGHTS = {
    "pembunuhan": 10,
    "pemerkosaan": 9,
    "kekerasan seksual": 9,
    "pelecehan seksual": 8,
    "perampokan": 9,
    "penculikan": 8,
    "penganiayaan": 7,
    "kdrt": 7,
    "kekerasan": 6,
    "narkoba": 6,
    "pencurian": 5,
    "tawuran": 5,
    "penipuan": 4,
    "verbal_harassment": 5,
    "physical_harassment": 7,
    "stalking": 6,
    "theft": 5,
    "intimidation": 6,
    "other": 3,
}


@dataclass
class IncidentPoint:
    latitude: float
    longitude: float
    timestamp: datetime
    category: str
    severity: int
    source: str


def from_scraped_news(articles: list) -> List[IncidentPoint]:
    points = []
    for article in articles:
        if article.latitude is None or article.longitude is None:
            continue
        points.append(IncidentPoint(
            latitude=article.latitude,
            longitude=article.longitude,
            timestamp=article.published_at or datetime.utcnow(),
            category=article.crime_type or "other",
            severity=article.severity or CATEGORY_WEIGHTS.get(article.crime_type, 3),
            source="news",
        ))
    return points


def from_user_reports(reports: list) -> List[IncidentPoint]:
    points = []
    for report in reports:
        lat = float(report.get("latitude", 0))
        lng = float(report.get("longitude", 0))
        if lat == 0 or lng == 0:
            continue
        category = report.get("incident_type", "other")
        points.append(IncidentPoint(
            latitude=lat,
            longitude=lng,
            timestamp=report.get("incident_at", datetime.utcnow()),
            category=category,
            severity=report.get("severity_score") or CATEGORY_WEIGHTS.get(category, 3),
            source="user_report",
        ))
    return points


def build_dataset(news_articles: list = None, user_reports: list = None) -> List[IncidentPoint]:
    dataset = []
    if news_articles:
        dataset.extend(from_scraped_news(news_articles))
    if user_reports:
        dataset.extend(from_user_reports(user_reports))
    return dataset


def filter_by_time(points: List[IncidentPoint], days: int = 90) -> List[IncidentPoint]:
    cutoff = datetime.utcnow().timestamp() - (days * 86400)
    return [p for p in points if p.timestamp and p.timestamp.timestamp() > cutoff]


def get_category_weight(category: str) -> int:
    return CATEGORY_WEIGHTS.get(category, 3)


def run(news_articles: list = None, user_reports: list = None, filter_days: int = 90) -> List[IncidentPoint]:
    dataset = build_dataset(news_articles, user_reports)
    if filter_days > 0:
        dataset = filter_by_time(dataset, filter_days)
    return dataset
