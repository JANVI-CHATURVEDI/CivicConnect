"""Backwards-compat shim — new code should import from reports.ai."""

import requests  # noqa: F401  (kept so old patch target reports.ai_utils.requests still resolves)

from .ai.duplicates import (  # noqa: F401
    DUPLICATE_RADIUS_M,
    DUPLICATE_WINDOW_DAYS,
    EARTH_RADIUS_M,
    find_possible_duplicates,
    haversine_distance_m,
)
from .ai.gemini_client import VALID_CATEGORIES, VALID_FLAGS, VALID_PRIORITIES, gemini_analyze  # noqa: F401
from .ai.rule_engine import (  # noqa: F401
    CATEGORY_KEYWORDS,
    DEPARTMENT_MAP,
    HIGH_PRIORITY_KEYWORDS,
    MEDIUM_PRIORITY_KEYWORDS,
    suggest_category,
    suggest_department,
    suggest_flag,
)
from .ai.service import analyze_report, analyze_report_full  # noqa: F401

GEMINI_MODEL = "gemini-2.5-flash"


def suggest_priority(title="", description="", category=""):
    from .ai import rule_engine as re

    hits = re.text_urgency(title, description)[1]
    risky = {"manhole", "traffic"}
    if hits and (any(k in HIGH_PRIORITY_KEYWORDS for k in hits) or (category in risky and hits)):
        tier = "high" if any(k in HIGH_PRIORITY_KEYWORDS for k in hits) else "medium"
    elif hits or category in risky:
        tier = "medium"
    else:
        tier = "low"
    return tier, hits
