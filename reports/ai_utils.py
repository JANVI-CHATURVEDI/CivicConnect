"""AI helpers: category detection, priority scoring, department routing,
and duplicate detection. Uses the Gemini API when GEMINI_API_KEY is set,
and falls back to a rule-based engine when it isn't (or the call fails)."""

import json
import math
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone


CATEGORY_KEYWORDS = {
    "road": ["pothole", "road", "crack", "asphalt", "highway", "footpath", "pavement", "sinkhole"],
    "water": ["leak", "pipe", "water", "burst", "sewage", "drain", "tap", "pipeline"],
    "garbage": ["garbage", "trash", "waste", "bin", "dump", "litter", "rubbish"],
    "light": ["streetlight", "street light", "lamp", "bulb", "dark street", "electric pole"],
    "tree": ["tree", "branch", "fallen tree", "uprooted"],
    "manhole": ["manhole", "open drain", "open hole", "sewer cover"],
    "traffic": ["signal", "traffic light", "traffic signal", "junction light"],
}

VALID_CATEGORIES = set(CATEGORY_KEYWORDS) | {"other"}
VALID_PRIORITIES = {"low", "medium", "high"}

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

GEMINI_MODEL = "gemini-2.0-flash"


def suggest_category(text: str):
    if not text:
        return None

    text = text.lower()
    best_category, best_score = None, 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > best_score:
            best_category, best_score = category, score

    return best_category


def suggest_priority(title: str, description: str, category: str = ""):
    text = f"{title or ''} {description or ''}".lower()

    high_hits = [kw for kw in HIGH_PRIORITY_KEYWORDS if kw in text]
    medium_hits = [kw for kw in MEDIUM_PRIORITY_KEYWORDS if kw in text]

    risky_categories = {"manhole", "traffic"}

    if high_hits or (category in risky_categories and medium_hits):
        return "high", high_hits or medium_hits

    if medium_hits or category in risky_categories:
        return "medium", medium_hits

    return "low", []


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


def gemini_analyze(title: str, description: str):
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key or not (title or description):
        return None

    prompt = (
        "Classify this civic issue report for a city government app. "
        "Respond with ONLY a JSON object, no markdown, no extra text, "
        "with exactly these keys:\n"
        '"category": one of road, water, garbage, light, tree, manhole, traffic, other\n'
        '"priority": one of low, medium, high\n'
        '"department": short name of the government department responsible\n\n'
        f"Title: {title}\nDescription: {description}"
    )

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        f"?key={api_key}"
    )

    try:
        response = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=8,
        )
        response.raise_for_status()
        text = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text)

        if result.get("category") in VALID_CATEGORIES and result.get("priority") in VALID_PRIORITIES:
            return result

    except Exception:
        pass

    return None


EARTH_RADIUS_M = 6371000
DUPLICATE_RADIUS_M = 150
DUPLICATE_WINDOW_DAYS = 14


def haversine_distance_m(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (math.sin(d_phi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS_M * c


def find_possible_duplicates(category, latitude, longitude, exclude_pk=None):
    from .models import Report

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


def analyze_report(title="", description="", category="", latitude=None,
                    longitude=None, exclude_pk=None):
    gemini_result = gemini_analyze(title, description)

    if gemini_result:
        detected_category = gemini_result["category"]
        priority = gemini_result["priority"]
        department = gemini_result.get("department") or suggest_department(category or detected_category)
        matched_keywords = []
        source = "gemini"
    else:
        detected_category = suggest_category(f"{title} {description}")
        priority, matched_keywords = suggest_priority(title, description, category or detected_category)
        department = suggest_department(category or detected_category or "other")
        source = "rules"

    duplicates = find_possible_duplicates(category, latitude, longitude, exclude_pk)

    return {
        "suggested_category": detected_category,
        "suggested_priority": priority,
        "matched_keywords": matched_keywords,
        "department": department,
        "ai_source": source,
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
