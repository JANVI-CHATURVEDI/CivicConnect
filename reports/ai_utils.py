"""
CivicConnect AI — lightweight, dependency-free "AI" layer.

This module implements the intelligence behind the features advertised on the
homepage (issue detection, severity analysis, smart routing, duplicate
detection) using transparent, explainable rule-based techniques instead of a
black-box ML model. This is a deliberate choice for a project like this:

- It runs instantly, offline, with zero extra dependencies or API keys —
  important for a college demo where you can't guarantee internet access.
- It is fully explainable in a viva: you can point at the exact keyword or
  distance threshold that produced a decision.
- It is a genuine, working implementation of "AI-assisted" civic triage
  (keyword-based NLP classification + geospatial clustering), not just a
  marketing label with nothing behind it.

If you want to swap in a real ML/vision model later (e.g. an image
classifier for the photo, or a call to an LLM API for the text), every
function below has a single, clearly-marked entry point
(`analyze_report`) — replace its internals and nothing else in the app
needs to change.
"""

import math
from datetime import timedelta

from django.utils import timezone


# ---------------------------------------------------------------------------
# 1. TEXT -> CATEGORY  (keyword-based "AI issue detection")
# ---------------------------------------------------------------------------

CATEGORY_KEYWORDS = {
    "road": ["pothole", "road", "crack", "asphalt", "highway", "footpath", "pavement", "sinkhole"],
    "water": ["leak", "pipe", "water", "burst", "sewage", "drain", "tap", "pipeline"],
    "garbage": ["garbage", "trash", "waste", "bin", "dump", "litter", "rubbish"],
    "light": ["streetlight", "street light", "lamp", "bulb", "dark street", "electric pole"],
    "tree": ["tree", "branch", "fallen tree", "uprooted"],
    "manhole": ["manhole", "open drain", "open hole", "sewer cover"],
    "traffic": ["signal", "traffic light", "traffic signal", "junction light"],
}

# Words that suggest urgency / danger — used for severity scoring below.
HIGH_PRIORITY_KEYWORDS = [
    "urgent", "danger", "dangerous", "emergency", "accident", "injury", "injured",
    "fire", "collapsed", "collapse", "flood", "flooding", "electrocution",
    "live wire", "exposed wire", "blocking road", "child", "school", "hospital",
    "death", "died", "life threat", "leaking gas", "gas leak",
]

MEDIUM_PRIORITY_KEYWORDS = [
    "large", "big", "heavy traffic", "overflowing", "broken", "cracked",
    "several days", "weeks", "repeated", "worsening", "smell", "stagnant",
]


def suggest_category(text: str):
    """Return the category key whose keywords best match the given text,
    or None if nothing scores above zero."""
    if not text:
        return None

    text = text.lower()
    best_category, best_score = None, 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_category, best_score = category, score

    return best_category


# ---------------------------------------------------------------------------
# 2. SEVERITY / PRIORITY SCORING
# ---------------------------------------------------------------------------

def suggest_priority(title: str, description: str, category: str = ""):
    """Score the combined text for urgency signals and return
    ('low' | 'medium' | 'high', matched_keywords list)."""

    text = f"{title or ''} {description or ''}".lower()

    high_hits = [kw for kw in HIGH_PRIORITY_KEYWORDS if kw in text]
    medium_hits = [kw for kw in MEDIUM_PRIORITY_KEYWORDS if kw in text]

    # Some categories are inherently higher risk (open manholes, live traffic
    # signals, downed trees on roads) even without alarming keywords.
    risky_categories = {"manhole", "traffic"}

    if high_hits or (category in risky_categories and medium_hits):
        return "high", high_hits or medium_hits

    if medium_hits or category in risky_categories:
        return "medium", medium_hits

    return "low", []


# ---------------------------------------------------------------------------
# 3. DEPARTMENT ROUTING
# ---------------------------------------------------------------------------

DEPARTMENT_MAP = {
    "road": "Roads & Infrastructure Dept.",
    "water": "Water Supply Dept.",
    "garbage": "Sanitation Dept.",
    "light": "Electrical Dept.",
    "tree": "Parks & Horticulture Dept.",
    "manhole": "Public Works Dept.",
    "traffic": "Traffic Police Dept.",
    "other": "General Grievance Cell",
}


def suggest_department(category: str) -> str:
    return DEPARTMENT_MAP.get(category, "General Grievance Cell")


# ---------------------------------------------------------------------------
# 4. GEO-BASED DUPLICATE DETECTION
# ---------------------------------------------------------------------------

EARTH_RADIUS_M = 6371000
DUPLICATE_RADIUS_M = 150       # reports within 150m of each other
DUPLICATE_WINDOW_DAYS = 14     # ...and reported within the last 14 days


def haversine_distance_m(lat1, lon1, lat2, lon2) -> float:
    """Great-circle distance between two lat/lon points, in meters."""
    lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_M * c


def find_possible_duplicates(category, latitude, longitude, exclude_pk=None):
    """Return a list of (report, distance_m) for existing reports of the
    same category, within DUPLICATE_RADIUS_M meters and reported in the
    last DUPLICATE_WINDOW_DAYS days."""

    from .models import Report  # local import avoids circular import

    if latitude is None or longitude is None:
        return []

    since = timezone.now() - timedelta(days=DUPLICATE_WINDOW_DAYS)

    candidates = Report.objects.filter(
        category=category,
        created_at__gte=since,
        latitude__isnull=False,
        longitude__isnull=False,
    )

    if exclude_pk:
        candidates = candidates.exclude(pk=exclude_pk)

    matches = []
    for report in candidates:
        distance = haversine_distance_m(
            latitude, longitude, report.latitude, report.longitude
        )
        if distance <= DUPLICATE_RADIUS_M:
            matches.append((report, round(distance, 1)))

    matches.sort(key=lambda pair: pair[1])
    return matches


# ---------------------------------------------------------------------------
# 5. SINGLE ENTRY POINT — used by the view and the live-preview API
# ---------------------------------------------------------------------------

def analyze_report(title="", description="", category="", latitude=None,
                    longitude=None, exclude_pk=None):
    """Run every AI step and return one combined result dict."""

    detected_category = suggest_category(f"{title} {description}")
    priority, matched_keywords = suggest_priority(title, description, category or detected_category)
    department = suggest_department(category or detected_category or "other")
    duplicates = find_possible_duplicates(category, latitude, longitude, exclude_pk)

    return {
        "suggested_category": detected_category,
        "suggested_priority": priority,
        "matched_keywords": matched_keywords,
        "department": department,
        "duplicates": [
            {
                "id": report.pk,
                "title": report.title,
                "status": report.get_status_display(),
                "distance_m": distance,
            }
            for report, distance in duplicates[:5]
        ],
    }
