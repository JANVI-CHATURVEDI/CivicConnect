"""Backwards-compat shim — new code should import from reports.ai."""
import requests  # noqa: F401  (kept so old patch target reports.ai_utils.requests still resolves)
from .ai.rule_engine import (  # noqa: F401
    CATEGORY_KEYWORDS, HIGH_PRIORITY_KEYWORDS, MEDIUM_PRIORITY_KEYWORDS,
    DEPARTMENT_MAP, suggest_category, suggest_flag,
    suggest_department,
)
from .ai.duplicates import haversine_distance_m, find_possible_duplicates, EARTH_RADIUS_M, DUPLICATE_RADIUS_M, DUPLICATE_WINDOW_DAYS  # noqa: F401
from .ai.service import analyze_report, analyze_report_full  # noqa: F401
from .ai.gemini_client import gemini_analyze, VALID_CATEGORIES, VALID_FLAGS, VALID_PRIORITIES  # noqa: F401

GEMINI_MODEL = "gemini-2.0-flash"


def suggest_priority(title="", description="", category=""):
    from .ai import rule_engine as re
    urgency, hits, sensitive = re.text_urgency(title, description)
    risky = {"manhole", "traffic"}
    if hits and (any(k in HIGH_PRIORITY_KEYWORDS for k in hits) or (category in risky and hits)):
        tier = "high" if any(k in HIGH_PRIORITY_KEYWORDS for k in hits) else "medium"
    elif hits or category in risky:
        tier = "medium"
    else:
        tier = "low"
    return tier, hits
