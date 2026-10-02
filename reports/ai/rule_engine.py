"""Rule engine: categories, urgency, language, spam, departments, scoring."""

import math
import re

CATEGORY_KEYWORDS = {
    "road": ["pothole", "road", "crack", "asphalt", "highway", "footpath", "pavement", "sinkhole", "gaddha"],
    "water": ["leak", "pipe", "water", "burst", "sewage", "drain", "tap", "pipeline", "paani", "nal"],
    "garbage": ["garbage", "trash", "waste", "bin", "dump", "litter", "rubbish", "kachra", "kooda"],
    "light": ["streetlight", "street light", "lamp", "bulb", "dark street", "electric pole", "batti", "light"],
    "tree": ["tree", "branch", "fallen tree", "uprooted", "ped"],
    "manhole": ["manhole", "open drain", "open hole", "sewer cover", "gutter"],
    "traffic": ["signal", "traffic light", "traffic signal", "junction light"],
}

HIGH_PRIORITY_KEYWORDS = [
    "urgent", "danger", "dangerous", "emergency", "accident", "injury", "injured",
    "fire", "aag", "collapsed", "collapse", "flood", "flooding", "electrocution",
    "live wire", "exposed wire", "blocking road", "child", "school", "hospital",
    "death", "died", "life threat", "leaking gas", "gas leak", "khatra",
]

MEDIUM_PRIORITY_KEYWORDS = [
    "large", "big", "bada", "heavy traffic", "overflowing", "broken", "toota",
    "cracked", "several days", "weeks", "repeated", "worsening", "smell", "badboo", "stagnant",
]

SENSITIVE_KEYWORDS = ["school", "hospital", "playground", "market", "station", "mandir", "masjid"]

CATEGORY_RISK = {"manhole": 25, "traffic": 20, "water": 12, "road": 10, "light": 8, "garbage": 5, "tree": 7, "other": 3}

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

HINDI_RE = re.compile(r"[\u0900-\u097F]")


def detect_language(text):
    t = (text or "").lower()
    if HINDI_RE.search(text or ""):
        return "hi"
    hinglish = ["paani", "kachra", "gaddha", "batti", "nal", "sadak", "kooda", "hai", "nahi", "bahut", "bada"]
    if any(w in t for w in hinglish):
        return "hinglish"
    return "en"


def suggest_category(text):
    if not text:
        return None
    t = text.lower()
    best, score = None, 0
    for cat, kws in CATEGORY_KEYWORDS.items():
        s = sum(1 for kw in kws if kw in t)
        if s > score:
            best, score = cat, s
    return best


def text_urgency(title, description):
    t = f"{title or ''} {description or ''}".lower()
    high = [kw for kw in HIGH_PRIORITY_KEYWORDS if kw in t]
    med = [kw for kw in MEDIUM_PRIORITY_KEYWORDS if kw in t]
    sensitive = [kw for kw in SENSITIVE_KEYWORDS if kw in t]
    urgency = min(100, 55 * len(high) + 18 * len(med) + 10 * len(sensitive))
    return urgency, high + med, bool(sensitive)


def suggest_flag(title, description):
    text = f"{title or ''} {description or ''}".strip()
    if len(text) < 12:
        return "vague"
    low = text.lower()
    spam_hints = ["buy now", "click here", "lottery", "free money", "http://", "https://", "test test test"]
    if any(h in low for h in spam_hints):
        return "spam"
    if len(set(low.split())) <= 2 and len(text) < 30:
        return "vague"
    return "ok"


def suggest_department(category):
    return DEPARTMENT_MAP.get(category, "General Grievance Cell")


def token_set(text):
    return set(re.findall(r"[a-z\u0900-\u097F]{3,}", (text or "").lower()))


def text_similarity(a, b):
    sa, sb = token_set(a), token_set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / max(1, len(sa | sb))


def priority_score(severity=50, urgency=0, category="other", sensitive=False, upvotes=0, age_days=0, density=0):
    parts = {}
    parts["ai_severity"] = round(max(0, min(100, severity)) * 0.35, 1)
    parts["text_urgency"] = round(max(0, min(100, urgency)) * 0.25, 1)
    parts["category_risk"] = round(CATEGORY_RISK.get(category, 3) * 0.4, 1)
    parts["sensitive_place"] = 8.0 if sensitive else 0.0
    parts["upvotes"] = round(min(10.0, upvotes * 1.5), 1)
    parts["age"] = round(min(6.0, age_days * 0.5), 1)
    parts["density"] = round(min(8.0, density * 2.0), 1)
    total = round(min(100, sum(parts.values()) + 20), 1)  # base offset so typical reports land Medium
    if total >= 80:
        label = "critical"
    elif total >= 60:
        label = "high"
    elif total >= 35:
        label = "medium"
    else:
        label = "low"
    reasons = [
        f"AI severity contributes {parts['ai_severity']}",
        f"text urgency contributes {parts['text_urgency']}",
        f"category risk ({category}) contributes {parts['category_risk']}",
    ]
    if sensitive:
        reasons.append("near sensitive place (+8)")
    if upvotes:
        reasons.append(f"{upvotes} upvotes (+{parts['upvotes']})")
    if age_days >= 2:
        reasons.append(f"open {age_days:.0f}d (+{parts['age']})")
    if density:
        reasons.append(f"{density} nearby similar (+{parts['density']})")
    return total, label, reasons
