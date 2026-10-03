"""Duplicate detection: DB bbox prefilter + Haversine + text similarity."""

import math
from datetime import timedelta

from django.utils import timezone

from .rule_engine import text_similarity

EARTH_RADIUS_M = 6371000
DUPLICATE_RADIUS_M = 150
DUPLICATE_WINDOW_DAYS = 14


def haversine_distance_m(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(float, (lat1, lon1, lat2, lon2))
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2) ** 2
    return EARTH_RADIUS_M * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def find_possible_duplicates(
    category, latitude, longitude, title="", description="", exclude_pk=None, limit=5
):
    from reports.models import Report

    if latitude is None or longitude is None:
        return []
    try:
        lat, lon = float(latitude), float(longitude)
    except (TypeError, ValueError):
        return []
    since = timezone.now() - timedelta(days=DUPLICATE_WINDOW_DAYS)
    # ~150m in degrees (lat ~111km, lon scaled by cos)
    d_lat = DUPLICATE_RADIUS_M / 111320.0
    d_lon = DUPLICATE_RADIUS_M / max(30000.0, 111320.0 * max(0.2, math.cos(math.radians(lat))))
    candidates = Report.objects.filter(
        category=category,
        created_at__gte=since,
        latitude__range=(lat - d_lat, lat + d_lat),
        longitude__range=(lon - d_lon, lon + d_lon),
    ).only("id", "title", "description", "status", "latitude", "longitude")
    if exclude_pk:
        candidates = candidates.exclude(pk=exclude_pk)
    query_text = f"{title} {description}"
    matches = []
    for rep in candidates:
        try:
            dist = haversine_distance_m(lat, lon, rep.latitude, rep.longitude)
        except (TypeError, ValueError):
            continue
        if dist <= DUPLICATE_RADIUS_M:
            sim = text_similarity(query_text, f"{rep.title} {rep.description}") if query_text.strip() else 0.5
            matches.append((rep, round(dist, 1), round(sim, 2)))
    matches.sort(key=lambda m: (m[1], -m[2]))
    return matches[:limit]
