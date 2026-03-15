import enum


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"
    partner = "partner"


class IncidentType(str, enum.Enum):
    verbal_harassment = "verbal_harassment"
    physical_harassment = "physical_harassment"
    stalking = "stalking"
    theft = "theft"
    intimidation = "intimidation"
    other = "other"


class ReportStatus(str, enum.Enum):
    received = "received"
    verified = "verified"
    in_progress = "in_progress"
    resolved = "resolved"
    rejected = "rejected"


class JourneyStatus(str, enum.Enum):
    active = "active"
    completed = "completed"
    alert_triggered = "alert_triggered"
    cancelled = "cancelled"


class TimeSlot(str, enum.Enum):
    morning = "morning"
    afternoon = "afternoon"
    evening = "evening"
    night = "night"


class HeatmapIntensity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class NewsSource(str, enum.Enum):
    detik = "detik"
    kompas = "kompas"
    insidelombok = "insidelombok"
    postlombok = "postlombok"


class NTBArea(str, enum.Enum):
    mataram = "Mataram"
    lombok_barat = "Lombok Barat"
    lombok_tengah = "Lombok Tengah"
    lombok_timur = "Lombok Timur"
    lombok_utara = "Lombok Utara"
    sumbawa = "Sumbawa"
    sumbawa_barat = "Sumbawa Barat"
    dompu = "Dompu"
    bima_kota = "Bima Kota"
    bima_kabupaten = "Bima Kabupaten"
