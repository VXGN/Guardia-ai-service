"""Helpers for mapping NTB area names to representative coordinates."""

from collections.abc import Mapping


# Representative city/regency center coordinates in NTB.
_NTB_AREA_COORDINATES: dict[str, tuple[float, float]] = {
    "Mataram": (-8.5833, 116.1167),
    "Lombok Barat": (-8.6461, 116.1169),
    "Lombok Tengah": (-8.7046, 116.2705),
    "Lombok Timur": (-8.6529, 116.5300),
    "Lombok Utara": (-8.3595, 116.2460),
    "Sumbawa": (-8.4894, 117.4150),
    "Sumbawa Barat": (-8.7470, 116.8282),
    "Dompu": (-8.5365, 118.4634),
    "Bima Kota": (-8.4544, 118.7266),
    "Bima Kabupaten": (-8.5749, 118.4457),
}

_AREA_ALIASES: Mapping[str, str] = {
    "mataram": "Mataram",
    "lombok barat": "Lombok Barat",
    "lombok tengah": "Lombok Tengah",
    "lombok timur": "Lombok Timur",
    "lombok utara": "Lombok Utara",
    "sumbawa": "Sumbawa",
    "sumbawa barat": "Sumbawa Barat",
    "dompu": "Dompu",
    "bima kota": "Bima Kota",
    "bima kabupaten": "Bima Kabupaten",
}


def get_area_coordinates(area: str | None) -> tuple[float, float] | None:
    """Return representative coordinates for an NTB area name."""
    if not area:
        return None

    normalized = _AREA_ALIASES.get(area.strip().lower())
    if normalized is None:
        return None

    return _NTB_AREA_COORDINATES.get(normalized)
