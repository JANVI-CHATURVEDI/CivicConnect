"""Deterministic rich demo seed. Idempotent via demo_ prefix; --seed/--count/--reset.

Bulk-writes users/children (2 queries instead of hundreds) so seeding stays
fast even against a high-latency hosted DB.
"""

import io
import random
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from reports.ai.service import analyze_report_full
from reports.constants import SLA_HOURS
from reports.models import AIAnalysis, Comment, Profile, Report, StatusEvent, Vote

DEMO_PASSWORD = "DemoPass123!"

CITIES = [
    ("UP", "Lucknow", 26.8467, 80.9462, ["Gomti Nagar", "Hazratganj", "Aliganj", "Indira Nagar"]),
    ("UP", "Kanpur", 26.4499, 80.3319, ["Swaroop Nagar", "Tilak Nagar", "Kidwai Nagar"]),
    ("DL", "Delhi", 28.6139, 77.2090, ["Karol Bagh", "Laxmi Nagar", "Rohini", "Saket"]),
    ("MH", "Mumbai", 19.0760, 72.8777, ["Andheri", "Dadar", "Borivali"]),
    ("MH", "Pune", 18.5204, 73.8567, ["Kothrud", "Hadapsar", "Viman Nagar"]),
    ("KA", "Bengaluru", 12.9716, 77.5946, ["Whitefield", "Jayanagar", "Yelahanka"]),
    ("TN", "Chennai", 13.0827, 80.2707, ["T Nagar", "Velachery", "Anna Nagar"]),
    ("WB", "Kolkata", 22.5726, 88.3639, ["Salt Lake", "Howrah", "Park Street"]),
    ("GJ", "Ahmedabad", 23.0225, 72.5714, ["Maninagar", "Bodakdev", "Naroda"]),
    ("RJ", "Jaipur", 26.9124, 75.7873, ["Malviya Nagar", "C-Scheme", "Vaishali"]),
    ("TS", "Hyderabad", 17.3850, 78.4867, ["Kukatpally", "Dilsukhnagar", "Madhapur"]),
    ("PB", "Ludhiana", 30.9010, 75.8573, ["Civil Lines", "Model Town"]),
]

TITLES = [
    (
        "road",
        "Large pothole on {loc} main road",
        "A deep pothole has opened up on the main road near {loc}. Two-wheelers are at risk, especially after dark.",  # noqa: E501
    ),
    (
        "water",
        "Burst water pipeline near {loc}",
        "A pipeline has burst near {loc}. Water is flooding the street and has been flowing for days.",
    ),
    (
        "garbage",
        "Garbage bins overflowing at {loc}",
        "Bins near {loc} have not been cleared for a week. Waste is spilling onto the footpath and smells bad.",  # noqa: E501
    ),
    (
        "light",
        "Streetlights not working in {loc}",
        "The streetlights in {loc} are not working. The whole stretch stays dark at night and feels unsafe.",
    ),
    (
        "tree",
        "Fallen tree blocking lane near {loc}",
        "A tree fell across the lane near {loc} after the storm and is blocking traffic.",
    ),
    (
        "manhole",
        "Open manhole near school at {loc}",
        "An uncovered manhole near the school at {loc} is a serious danger to children. Needs urgent cover!",
    ),
    (
        "traffic",
        "Traffic signal malfunction at {loc} crossing",
        "The traffic signal at {loc} crossing is stuck on red in all directions, causing heavy congestion.",
    ),
    (
        "other",
        "Damaged park bench near {loc}",
        "A bench near the {loc} park entrance is broken and needs repair.",
    ),
    ("road", "test", "bad"),  # vague/spam examples
    ("other", "Buy now lottery", "click here free money http://spam"),
]

COMMENTS = ["Same issue near me.", "Please fix soon.", "Thanks for reporting.", "Facing this daily."]


def placeholder_image(kind, seed_text, after=False):
    rnd = random.Random(hash(seed_text) % 99999)
    img = Image.new(
        "RGB", (640, 420), (30 + rnd.randint(0, 40), 35 + rnd.randint(0, 40), 45 + rnd.randint(0, 40))
    )
    d = ImageDraw.Draw(img)
    d.rectangle([0, 300, 640, 420], fill=(60, 60, 65))
    if kind == "road":
        d.ellipse([220, 300, 420, 380], fill=(15, 15, 18))
    elif kind == "water":
        for i in range(6):
            d.ellipse([100 + i * 70, 310 + rnd.randint(-15, 15), 160 + i * 70, 350], fill=(60, 140, 220))
    elif kind == "garbage":
        for i in range(8):
            d.rectangle([80 + i * 55, 280 + rnd.randint(-20, 20), 120 + i * 55, 330], fill=(90, 120, 60))
    elif kind == "light":
        d.rectangle([300, 60, 320, 300], fill=(120, 120, 130))
        d.ellipse([270, 40, 350, 100], fill=(250, 230, 150) if not after else (80, 80, 80))
    elif kind == "tree":
        d.rectangle([300, 180, 330, 320], fill=(110, 70, 40))
        d.ellipse([200, 80, 430, 230], fill=(40, 120, 50))
    elif kind == "manhole":
        d.ellipse([250, 290, 390, 370], fill=(5, 5, 8))
        d.ellipse([250, 290, 390, 320], outline=(200, 200, 0), width=4)
    else:
        d.rectangle([180, 150, 460, 300], fill=(150, 60, 60))
    if after:
        d.rectangle([0, 0, 640, 40], fill=(30, 150, 70))
        d.text((10, 12), "FIXED", fill=(255, 255, 255))
    else:
        d.text((10, 12), kind.upper(), fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return ContentFile(buf.getvalue(), name=f"{kind}.jpg")


class Command(BaseCommand):
    help = "Rich deterministic demo seed."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true")
        parser.add_argument("--seed", type=int, default=42)
        parser.add_argument("--count", type=int, default=250)
        parser.add_argument(
            "--offline",
            action="store_true",
            help="Skip live Gemini calls (rule engine only). Faster; seed rows are precomputed anyway.",
        )

    def handle(self, *args, **options):
        rnd = random.Random(options["seed"])
        if options.get("offline"):
            from django.conf import settings as _s

            _s.GEMINI_API_KEY = ""
        if options["reset"]:
            deleted, _ = User.objects.filter(username__startswith="demo_").delete()
            self.stdout.write(f"Removed {deleted} demo objects.")
        n = options["count"]
        n_citizens = min(40, max(6, n // 4))

        # ---- bulk users (one shared hash, two queries total) ----
        pwd = make_password(DEMO_PASSWORD)
        states = sorted({c[0] for c in CITIES})
        specs = [("demo_superadmin", True, True, "superadmin", "", "", 0)]
        specs += [(f"demo_admin_{st.lower()}", True, False, "admin", st, "", 0) for st in states]
        officer_names = [f"demo_off_{st.lower()}" for st in states]
        specs += [
            (u, True, False, "officer", u.rsplit("_", 1)[1].upper(), "Roads & Infrastructure Dept.", 0)
            for u in officer_names
        ]
        specs += [
            (f"demo_citizen{i}", False, False, "citizen", "", "", rnd.randint(0, 200))
            for i in range(1, n_citizens + 1)
        ]
        existing = set(User.objects.filter(username__startswith="demo_").values_list("username", flat=True))
        fresh = [s for s in specs if s[0] not in existing]
        if fresh:
            User.objects.bulk_create(
                [
                    User(username=u, email=f"{u}@demo.local", password=pwd, is_staff=st, is_superuser=su)
                    for u, st, su, *_ in fresh
                ]
            )
            users = {u.username: u for u in User.objects.filter(username__in=[f[0] for f in fresh])}
            Profile.objects.bulk_create(
                [
                    Profile(user=users[s[0]], role=s[3], state=s[4], department=s[5], points=s[6])
                    for s in fresh
                ]
            )
        by_name = {u.username: u for u in User.objects.filter(username__startswith="demo_")}
        sup = by_name["demo_superadmin"]
        officers = [by_name[u] for u in officer_names]
        off_state = {u: by_name[u].profile.state for u in officer_names}
        citizens = [by_name[f"demo_citizen{i}"] for i in range(1, n_citizens + 1)]
        self.stdout.write(f"Users ready ({len(by_name)}). Seeding {n} reports...")

        analyses, events, comments, votes = [], [], [], []
        seen_votes = set()
        for i in range(n):
            st, city, lat0, lon0, locs = rnd.choice(CITIES)
            loc = rnd.choice(locs)
            cat, t, desc = rnd.choice(TITLES)
            created_at = timezone.now() - timedelta(days=rnd.randint(0, 90), hours=rnd.randint(0, 23))
            status = rnd.choices(
                ["reported", "acknowledged", "assigned", "progress", "resolved", "confirmed", "reopened"],
                weights=[30, 10, 10, 15, 20, 8, 7],
            )[0]
            title, description = t.format(loc=loc), desc.format(loc=loc)
            full = analyze_report_full(
                title=title, description=description, category=cat, latitude=lat0, longitude=lon0
            )
            rep = Report(
                citizen=rnd.choice(citizens),
                title=title[:160],
                description=description,
                category=cat,
                priority=full["suggested_priority"],
                priority_score=int(full["priority_score"]),
                priority_reasons=full["priority_reasons"],
                status=status,
                latitude=round(lat0 + rnd.uniform(-0.12, 0.12), 7),
                longitude=round(lon0 + rnd.uniform(-0.12, 0.12), 7),
                address=f"{loc}, {city}",
                state=st,
                department=full["department"],
                ai_priority_suggested=full["suggested_priority"],
                ai_source="rules",
                needs_review=full["flag"] != "ok",
                flag_reason=full["flag"] if full["flag"] != "ok" else "",
                action_brief=full.get("action_brief", ""),
                sla_due=created_at + timedelta(hours=SLA_HOURS.get(full["suggested_priority"], 120)),
            )
            if status in ("assigned", "progress") and rnd.random() < 0.7:
                same = [o for o in officers if off_state[o.username] == st] or officers
                rep.assigned_to = rnd.choice(same)
            if status == "confirmed" and rnd.random() < 0.8:
                rep.rating, rep.rating_feedback = rnd.randint(3, 5), "Good work"
            try:
                rep.image.save(
                    f"demo_{options['seed']}_{i}.jpg",
                    placeholder_image(cat, f"{options['seed']}-{i}"),
                    save=False,
                )
                if status in ("resolved", "confirmed"):
                    rep.resolution_image.save(
                        f"demo_{options['seed']}_{i}_after.jpg",
                        placeholder_image(cat, f"after-{i}", after=True),
                        save=False,
                    )
            except Exception:
                pass
            rep.save()  # single INSERT including image paths
            Report.objects.filter(pk=rep.pk).update(
                created_at=created_at,
                resolved_at=created_at + timedelta(hours=rnd.randint(2, 200))
                if status in ("resolved", "confirmed")
                else None,
            )
            analyses.append(
                AIAnalysis(
                    report=rep,
                    source="rules",
                    model="rule-engine",
                    latency_ms=full.get("latency_ms", 0),
                    confidence=full.get("confidence", 0.5),
                    payload={
                        k: full.get(k)
                        for k in ("suggested_category", "suggested_priority", "priority_score", "flag")
                    },
                )
            )
            events.append(
                StatusEvent(
                    report=rep, old_status="", new_status="reported", actor=rep.citizen, note="submitted"
                )
            )
            if status != "reported":
                events.append(
                    StatusEvent(
                        report=rep,
                        old_status="reported",
                        new_status=status,
                        actor=rnd.choice(officers),
                        note="workflow",
                    )
                )
            if rnd.random() < 0.3:
                comments.append(Comment(report=rep, user=rnd.choice(citizens), text=rnd.choice(COMMENTS)))
            if rnd.random() < 0.4:
                for v in rnd.sample(citizens, k=min(rnd.randint(1, 4), len(citizens))):
                    if (rep.pk, v.pk) not in seen_votes:
                        seen_votes.add((rep.pk, v.pk))
                        votes.append(Vote(report=rep, user=v))
            if (i + 1) % 5 == 0 or i + 1 == n:
                self.stdout.write(f"  ...{i + 1}/{n}")
        AIAnalysis.objects.bulk_create(analyses)
        StatusEvent.objects.bulk_create(events)
        Comment.objects.bulk_create(comments)
        Vote.objects.bulk_create(votes, ignore_conflicts=True)
        self._hero(citizens[0], officers[0], sup)
        self.stdout.write(self.style.SUCCESS(f"Seeded {n} reports + 3 heroes. Password: {DEMO_PASSWORD}"))
        self.stdout.write("  Super Admin : demo_superadmin / DemoPass123!")
        self.stdout.write("  State admins: demo_admin_<state> / DemoPass123!")
        self.stdout.write(f"  Citizens    : demo_citizen1..{n_citizens} / DemoPass123!")

    def _hero(self, citizen, officer, sup):
        heroes = [
            (
                "manhole",
                "CRITICAL: Open manhole near City Montessori School, Gomti Nagar",
                "An uncovered manhole on the footpath where schoolchildren walk every day. Urgent cover needed.",  # noqa: E501
                "UP",
                26.85,
                80.95,
            ),
            (
                "water",
                "Burst pipeline flooding MG Road Kanpur",
                "A major pipeline burst is wasting water and flooding the road.",
                "UP",
                26.45,
                80.33,
            ),
            (
                "road",
                "Deep potholes outside Andheri station",
                "Multiple deep potholes near the station are causing accidents.",
                "MH",
                19.11,
                72.85,
            ),
        ]
        for cat, title, desc, st, la, lo in heroes:
            full = analyze_report_full(title=title, description=desc, category=cat, latitude=la, longitude=lo)
            r = Report.objects.create(
                citizen=citizen,
                title=title,
                description=desc,
                category=cat,
                priority="critical",
                priority_score=92,
                priority_reasons=["hero demo"],
                status="resolved",
                latitude=la,
                longitude=lo,
                address="Hero location",
                state=st,
                department=full["department"],
                ai_source="rules",
                sla_due=timezone.now() - timedelta(hours=5),
                rating=5,
                rating_feedback="Excellent, verified fixed!",
            )
            try:
                r.image.save("hero.jpg", placeholder_image(cat, title), save=True)
                r.resolution_image.save(
                    "hero_after.jpg", placeholder_image(cat, title, after=True), save=True
                )
            except Exception:
                pass
            StatusEvent.objects.create(report=r, old_status="", new_status="reported", actor=citizen)
            StatusEvent.objects.create(
                report=r, old_status="reported", new_status="assigned", actor=sup, note="escalated, assigned"
            )
            StatusEvent.objects.create(
                report=r, old_status="assigned", new_status="resolved", actor=sup, note="fixed + verified"
            )
