"""Keyword-based crime detection, severity scoring, and NTB area mapping."""

from dataclasses import dataclass


CRIME_KEYWORDS: dict[str, tuple[str, int]] = {
    "pembunuhan": ("pembunuhan", 10),
    "membunuh": ("pembunuhan", 10),
    "tewas dibunuh": ("pembunuhan", 10),
    "dibunuh": ("pembunuhan", 10),
    "pemerkosaan": ("pemerkosaan", 9),
    "perkosa": ("pemerkosaan", 9),
    "diperkosa": ("pemerkosaan", 9),
    "kekerasan seksual": ("kekerasan seksual", 9),
    "pelecehan seksual": ("pelecehan seksual", 8),
    "perampokan": ("perampokan", 9),
    "rampok": ("perampokan", 9),
    "merampok": ("perampokan", 9),
    "dirampok": ("perampokan", 9),
    "begal": ("perampokan", 9),
    "penculikan": ("penculikan", 8),
    "culik": ("penculikan", 8),
    "diculik": ("penculikan", 8),
    "menculik": ("penculikan", 8),
    "penganiayaan": ("penganiayaan", 7),
    "aniaya": ("penganiayaan", 7),
    "dianiaya": ("penganiayaan", 7),
    "menganiaya": ("penganiayaan", 7),
    "kdrt": ("kdrt", 7),
    "kekerasan dalam rumah tangga": ("kdrt", 7),
    "kekerasan": ("kekerasan", 6),
    "pemerasan": ("pemerasan", 6),
    "memeras": ("pemerasan", 6),
    "narkoba": ("narkoba", 6),
    "narkotika": ("narkoba", 6),
    "sabu": ("narkoba", 6),
    "ganja": ("narkoba", 6),
    "obat terlarang": ("narkoba", 6),
    "pencurian": ("pencurian", 5),
    "mencuri": ("pencurian", 5),
    "dicuri": ("pencurian", 5),
    "maling": ("pencurian", 5),
    "curat": ("pencurian", 5),
    "curas": ("pencurian", 5),
    "tawuran": ("tawuran", 5),
    "bentrok": ("tawuran", 5),
    "penipuan": ("penipuan", 4),
    "menipu": ("penipuan", 4),
    "ditipu": ("penipuan", 4),
    "penggelapan": ("penggelapan", 4),
    "korupsi": ("korupsi", 4),
    "perjudian": ("perjudian", 3),
    "judi": ("perjudian", 3),
    "berjudi": ("perjudian", 3),
    "vandalisme": ("vandalisme", 3),
    "merusak": ("vandalisme", 3),
    "perusakan": ("vandalisme", 3),
}

NTB_AREA_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Bima Kota", ["kota bima"]),
    ("Sumbawa Barat", [
        "sumbawa barat", "ksb", "taliwang", "maluk", "jereweh", "sekongkang",
    ]),
    ("Bima Kabupaten", [
        "kabupaten bima", "woha", "bolo", "monta", "donggo", "wawo", "sape",
    ]),
    ("Lombok Barat", [
        "lombok barat", "lobar", "gerung", "lembar", "narmada", "lingsar",
        "gunung sari", "gunungsari", "batulayar", "batu layar", "labuapi",
        "kediri",
    ]),
    ("Lombok Tengah", [
        "lombok tengah", "loteng", "praya", "jonggat", "pujut", "batukliang",
        "kopang", "janapria",
    ]),
    ("Lombok Timur", [
        "lombok timur", "lotim", "selong", "aikmel", "masbagik", "sukamulia",
        "sakra", "terara", "montong gading", "pringgabaya", "labuhan haji",
        "keruak", "jerowaru",
    ]),
    ("Lombok Utara", [
        "lombok utara", "klu", "tanjung", "gangga", "kayangan", "bayan",
        "pemenang",
    ]),
    ("Sumbawa", [
        "sumbawa besar", "kabupaten sumbawa", "alas", "utan", "moyo",
        "empang", "plampang", "lunyuk",
    ]),
    ("Dompu", [
        "dompu", "woja", "hu'u", "kilo", "manggelewa", "pekat",
    ]),
    ("Mataram", [
        "mataram", "ampenan", "cakranegara", "selaparang", "sekarbela",
        "sandubaya",
    ]),
    ("Bima Kabupaten", ["bima"]),
    ("Sumbawa", ["sumbawa"]),
]


@dataclass
class CrimeScore:
    crime_type: str
    severity: int


@dataclass
class ArticleAnalysis:
    crime_type: str | None
    severity_score: int | None
    area: str | None


def detect_crime(text: str) -> CrimeScore | None:
    """Detect crime type and severity from article text.

    Checks all keywords and returns the one with the highest severity.
    """
    text_lower = text.lower()
    best: CrimeScore | None = None

    for keyword, (crime_type, severity) in CRIME_KEYWORDS.items():
        if keyword in text_lower:
            if best is None or severity > best.severity:
                best = CrimeScore(crime_type=crime_type, severity=severity)

    return best


def detect_area(text: str) -> str | None:
    """Detect NTB area from article text.

    Checks keywords in order from most specific to least specific.
    """
    text_lower = text.lower()

    for area_name, keywords in NTB_AREA_KEYWORDS:
        for keyword in keywords:
            if keyword in text_lower:
                return area_name

    return None


def analyze_article(title: str, snippet: str | None = None) -> ArticleAnalysis:
    """Analyze an article's title and snippet for crime type, severity, and area."""
    combined_text = title
    if snippet:
        combined_text += " " + snippet

    crime = detect_crime(combined_text)
    area = detect_area(combined_text)

    return ArticleAnalysis(
        crime_type=crime.crime_type if crime else None,
        severity_score=crime.severity if crime else None,
        area=area,
    )
