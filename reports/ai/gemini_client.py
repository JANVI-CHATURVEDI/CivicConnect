"""Gemini client: header auth, model from env, retries, timeout, structured JSON."""
import base64
import json
import logging
import time

import requests
from django.conf import settings

from . import rule_engine

log = logging.getLogger(__name__)

VALID_CATEGORIES = set(rule_engine.CATEGORY_KEYWORDS) | {"other"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}
VALID_FLAGS = {"ok", "vague", "spam"}


def _model():
    return getattr(settings, "GEMINI_MODEL", "gemini-2.0-flash")


def _timeout():
    try:
        return float(getattr(settings, "GEMINI_TIMEOUT_S", 12))
    except (TypeError, ValueError):
        return 12


def gemini_analyze(title="", description="", image_bytes=None, image_mime_type=None, vision_detail=False):
    api_key = getattr(settings, "GEMINI_API_KEY", "")
    if not api_key or not (title or description or image_bytes):
        return None
    prompt = (
        "Classify this civic issue report for a city government app. "
        "Respond with ONLY a JSON object (no markdown) with exactly these keys: "
        '"category": one of road, water, garbage, light, tree, manhole, traffic, other; '
        '"priority": one of low, medium, high, critical; '
        '"severity": integer 0-100; '
        '"department": short government department name; '
        '"flag": one of ok, vague, spam; '
        '"caption": one-line human description of the issue; '
        '"hazards": array of visible hazards (may be empty); '
        '"photo_match": one of match, mismatch, unclear; '
        '"confidence": number 0-1. '
        f"Title: {title}\nDescription: {description}"
    )
    if image_bytes:
        prompt += "\nA photo of the issue is attached — use it to inform severity, hazards and photo_match."
    parts = [{"text": prompt}]
    if image_bytes and image_mime_type:
        parts.append({"inline_data": {"mime_type": image_mime_type, "data": base64.b64encode(image_bytes).decode("ascii")}})
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{_model()}:generateContent"
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=_timeout())
            resp.raise_for_status()
            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            if text.startswith("```"):
                text = text.strip("`")
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            result = json.loads(text)
            if result.get("category") in VALID_CATEGORIES and result.get("priority") in VALID_PRIORITIES:
                if result.get("flag") not in VALID_FLAGS:
                    result["flag"] = "ok"
                try:
                    result["severity"] = max(0, min(100, int(result.get("severity", 50))))
                except (TypeError, ValueError):
                    result["severity"] = 50
                try:
                    result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.7))))
                except (TypeError, ValueError):
                    result["confidence"] = 0.7
                return result
            return None
        except Exception as e:  # network, 4xx/5xx, malformed JSON
            last_err = e
            log.warning("gemini attempt %d failed: %s", attempt + 1, e)
            time.sleep(0.5 * (2 ** attempt))
    log.error("gemini failed after retries: %s", last_err)
    return None
