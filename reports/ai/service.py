"""Service layer: full analysis dict used by views + API."""

import hashlib
import time

from . import rule_engine
from .duplicates import find_possible_duplicates
from .gemini_client import gemini_analyze


def content_hash(title="", description="", category="", lat=None, lon=None):
    h = hashlib.sha256()
    h.update(f"{title}|{description}|{category}|{lat}|{lon}".encode("utf-8", "ignore"))
    return h.hexdigest()


def analyze_report_full(
    title="",
    description="",
    category="",
    latitude=None,
    longitude=None,
    exclude_pk=None,
    image_bytes=None,
    image_mime_type=None,
    upvotes=0,
    age_days=0,
):
    t0 = time.monotonic()
    g = gemini_analyze(title, description, image_bytes, image_mime_type)
    if g:
        detected = g["category"]
        priority = g["priority"]
        department = g.get("department") or rule_engine.suggest_department(category or detected)
        flag = g.get("flag", "ok")
        severity = g.get("severity", 60)
        confidence = g.get("confidence", 0.7)
        caption = g.get("caption", "")
        hazards = g.get("hazards", []) or []
        photo_match = g.get("photo_match", "unclear")
        matched = []
        source = "gemini"
        language = rule_engine.detect_language(f"{title} {description}")
        urgency, hits, sensitive = rule_engine.text_urgency(title, description)
    else:
        detected = rule_engine.suggest_category(f"{title} {description}")
        urgency, hits, sensitive = rule_engine.text_urgency(title, description)
        # rule severity heuristic
        severity = (
            75
            if hits and any(k in rule_engine.HIGH_PRIORITY_KEYWORDS for k in hits)
            else (55 if hits else 30)
        )
        department = rule_engine.suggest_department(category or detected or "other")
        flag = rule_engine.suggest_flag(title, description)
        confidence = 0.55
        caption, hazards, photo_match = "", [], "unclear"
        matched = hits
        source = "rules"
        language = rule_engine.detect_language(f"{title} {description}")
        priority = None  # computed below from score

    eff_category = category or detected or "other"
    dups = find_possible_duplicates(eff_category, latitude, longitude, title, description, exclude_pk)
    density = len(dups)
    score, label, reasons = rule_engine.priority_score(
        severity=severity,
        urgency=urgency,
        category=eff_category,
        sensitive=sensitive,
        upvotes=upvotes,
        age_days=age_days,
        density=density,
    )
    if source == "gemini" and priority:
        # blend: keep Gemini label unless score strongly disagrees (+/- 2 bands)
        order = ["low", "medium", "high", "critical"]
        try:
            if abs(order.index(priority) - order.index(label)) >= 2:
                priority = label
        except ValueError:
            priority = label
    else:
        priority = label
    latency_ms = int((time.monotonic() - t0) * 1000)
    return {
        "suggested_category": detected,
        "suggested_priority": priority,
        "priority_score": score,
        "priority_reasons": reasons,
        "severity": severity,
        "urgency": urgency,
        "language": language,
        "matched_keywords": matched if source == "rules" else hits,
        "department": department,
        "ai_source": source,
        "flag": flag,
        "confidence": confidence,
        "caption": caption,
        "hazards": hazards,
        "photo_match": photo_match,
        "latency_ms": latency_ms,
        "action_brief": draft_action_brief(eff_category, priority, caption or title),
        "duplicates": [
            {"id": r.pk, "title": r.title, "status": r.get_status_display(), "distance_m": d, "similarity": s}
            for r, d, s in dups
        ],
    }


def analyze_report(
    title="",
    description="",
    category="",
    latitude=None,
    longitude=None,
    exclude_pk=None,
    image_bytes=None,
    image_mime_type=None,
):
    """Backwards-compatible thin dict (used by old views/tests)."""
    full = analyze_report_full(
        title, description, category, latitude, longitude, exclude_pk, image_bytes, image_mime_type
    )
    return {
        "suggested_category": full["suggested_category"],
        "suggested_priority": full["suggested_priority"],
        "matched_keywords": full["matched_keywords"],
        "department": full["department"],
        "ai_source": full["ai_source"],
        "flag": full["flag"],
        "duplicates": [
            {k: d[k] for k in ("id", "title", "status", "distance_m")} for d in full["duplicates"]
        ],
    }


def draft_action_brief(category, priority, summary):
    crew = {
        "road": "2 road crew + roller",
        "water": "plumber team + valves",
        "garbage": "sanitation truck + 3 staff",
        "light": "electrician + ladder van",
        "tree": "arborist + crane",
        "manhole": "PWC team + cover stock",
        "traffic": "traffic police + signal tech",
        "other": "field inspector",
    }.get(category, "field inspector")
    effort = {
        "critical": "4-8 hrs, immediate",
        "high": "1-2 days",
        "medium": "3-5 days",
        "low": "1-2 weeks",
    }.get(priority, "3-5 days")
    return f"{summary or 'Inspect site'}. Dispatch {crew}. Est. effort: {effort}."


def verify_resolution(original_caption, resolution_note=""):
    t = (resolution_note or "").lower()
    if any(w in t for w in ["resolved", "fixed", "cleared", "repaired", "done"]):
        return "resolved", 0.7, "resolution note indicates completion"
    if any(w in t for w in ["partial", "half", "ongoing", "progress"]):
        return "partially", 0.5, "note suggests partial completion"
    return "not resolved", 0.4, "insufficient evidence — flagged for admin review"
