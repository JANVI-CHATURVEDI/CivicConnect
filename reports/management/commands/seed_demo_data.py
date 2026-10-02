"""Deterministic rich demo seed. Idempotent via demo_ prefix; --seed/--count/--reset."""
import io
import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone
from PIL import Image, ImageDraw

from reports.ai.service import analyze_report_full
from reports.constants import SLA_HOURS
from reports.models import AIAnalysis, Comment, Notification, Profile, Report, StatusEvent, Vote

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
    ("road", "Sadak par bada gaddha hai {loc}", "Bahut bada pothole hai {loc} me, bike wale gir rahe hain. Please jaldi repair karo."),
    ("water", "Paani ki pipe leak {loc}", "Pipeline burst near {loc}, paani sadak par beh raha hai since 3 days."),
    ("garbage", "Kachra overflow at {loc}", "Bins haven't been cleared for a week near {loc}, badboo aa rahi hai."),
    ("light", "Streetlight bandh {loc}", "Street batti not working in {loc}, andhera rehta hai raat me."),
    ("tree", "Ped gir gaya {loc}", "A tree fell across the lane near {loc} after storm."),
    ("manhole", "Khula manhole near school {loc}", "Open manhole near school at {loc}, bachon ke liye khatra! Urgent!"),
    ("traffic", "Signal kharab {loc} crossing", "Traffic signal stuck on red at {loc} crossing, heavy jam."),
    ("other", "Park bench toota {loc}", "Damaged bench near {loc} park entrance."),
    ("road", "test", "bad"),  # vague/spam examples
    ("other", "Buy now lottery", "click here free money http://spam"),
]

DEPTS = ["Roads & Infrastructure Dept.", "Water Supply Dept.", "Sanitation Dept.", "Electrical Dept."]


def placeholder_image(kind, seed_text, after=False):
    rnd = random.Random(hash(seed_text) % 99999)
    img = Image.new("RGB", (640, 420), (30 + rnd.randint(0, 40), 35 + rnd.randint(0, 40), 45 + rnd.randint(0, 40)))
    d = ImageDraw.Draw(img)
    # ground + shape per kind
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
        d.rectangle([300, 60, 320, 300], fill=(120, 120, 130)); d.ellipse([270, 40, 350, 100], fill=(250, 230, 150) if not after else (80, 80, 80))
    elif kind == "tree":
        d.rectangle([300, 180, 330, 320], fill=(110, 70, 40)); d.ellipse([200, 80, 430, 230], fill=(40, 120, 50))
    elif kind == "manhole":
        d.ellipse([250, 290, 390, 370], fill=(5, 5, 8)); d.ellipse([250, 290, 390, 320], outline=(200, 200, 0), width=4)
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

    def handle(self, *args, **options):
        rnd = random.Random(options["seed"])
        if options["reset"]:
            deleted, _ = User.objects.filter(username__startswith="demo_").delete()
            self.stdout.write(f"Removed {deleted} demo objects.")
        sup = self._user("demo_superadmin", is_superuser=True, is_staff=True, role="superadmin")
        states = sorted({c[0] for c in CITIES})
        for st in states:
            self._user(f"demo_admin_{st.lower()}", is_staff=True, role="admin", state=st)
        officers = []
        for st in states[:6]:
            for dept in DEPTS[:2]:
                officers.append(self._user(f"demo_off_{st.lower()}_{len(officers)}", is_staff=True, role="officer", state=st, dept=dept))
        citizens = [self._user(f"demo_citizen{i}", role="citizen", points=rnd.randint(0, 200)) for i in range(1, 41)]
        n = options["count"]
        created = 0
        first_ids = []
        for i in range(n):
            st, city, lat0, lon0, locs = rnd.choice(CITIES)
            loc = rnd.choice(locs)
            cat, t, desc = rnd.choice(TITLES)
            # monsoon spike for water
            days_ago = rnd.randint(0, 90)
            created_at = timezone.now() - timedelta(days=days_ago, hours=rnd.randint(0, 23))
            status = rnd.choices(["reported", "acknowledged", "assigned", "progress", "resolved", "confirmed", "reopened"], weights=[30, 10, 10, 15, 20, 8, 7])[0]
            title = t.format(loc=loc)
            description = desc.format(loc=loc)
            full = analyze_report_full(title=title, description=description, category=cat, latitude=lat0, longitude=lon0)
            rep = Report(
                citizen=rnd.choice(citizens), title=title[:160], description=description, category=cat,
                priority=full["suggested_priority"], priority_score=int(full["priority_score"]), priority_reasons=full["priority_reasons"],
                status=status, latitude=round(lat0 + rnd.uniform(-0.12, 0.12), 7), longitude=round(lon0 + rnd.uniform(-0.12, 0.12), 7),
                address=f"{loc}, {city}", state=st, department=full["department"], ai_priority_suggested=full["suggested_priority"],
                ai_source="rules", needs_review=full["flag"] != "ok", flag_reason=full["flag"] if full["flag"] != "ok" else "",
                action_brief=full.get("action_brief", ""), sla_due=created_at + timedelta(hours=SLA_HOURS.get(full["suggested_priority"], 120)),
            )
            if officers and status in ("assigned", "progress") and rnd.random() < 0.7:
                rep.assigned_to = rnd.choice([o for o in officers if get_state(o) == st] or officers)
            rep.save()
            try:
                img = placeholder_image(cat, f"{options['seed']}-{i}")
                rep.image.save(f"demo_{i}.jpg", img, save=True)
                if status in ("resolved", "confirmed"):
                    after = placeholder_image(cat, f"after-{i}", after=True)
                    rep.resolution_image.save(f"demo_{i}_after.jpg", after, save=True)
            except Exception:
                pass
            Report.objects.filter(pk=rep.pk).update(created_at=created_at, resolved_at=created_at + timedelta(hours=rnd.randint(2, 200)) if status in ("resolved", "confirmed") else None)
            AIAnalysis.objects.create(report=rep, source="rules", model="rule-engine", latency_ms=full.get("latency_ms", 0), confidence=full.get("confidence", 0.5), payload={k: full.get(k) for k in ("suggested_category", "suggested_priority", "priority_score", "flag")})
            StatusEvent.objects.create(report=rep, old_status="", new_status="reported", actor=rep.citizen, note="submitted")
            if status != "reported":
                StatusEvent.objects.create(report=rep, old_status="reported", new_status=status, actor=rnd.choice(officers) if officers else sup, note="workflow")
            if rnd.random() < 0.3:
                Comment.objects.create(report=rep, user=rnd.choice(citizens), text=rnd.choice(["Same issue near me.", "Please fix soon.", "Dhanyavaad for reporting.", "Facing this daily."]))
            if rnd.random() < 0.4:
                for v in rnd.sample(citizens, k=rnd.randint(1, 4)):
                    Vote.objects.get_or_create(report=rep, user=v)
            if status in ("confirmed",) and rnd.random() < 0.8:
                rep.rating = rnd.randint(3, 5); rep.rating_feedback = "Good work"; rep.save(update_fields=["rating", "rating_feedback"])
            first_ids.append(rep.pk)
            created += 1
        # 3 hero reports
        self._hero(citizens[0], officers, sup, rnd)
        self.stdout.write(self.style.SUCCESS(f"Seeded {created} reports + heroes. Password: {DEMO_PASSWORD}"))
        self.stdout.write("  Super Admin : demo_superadmin / DemoPass123!")
        self.stdout.write("  State admins: demo_admin_<state> / DemoPass123!")
        self.stdout.write("  Citizens    : demo_citizen1..40 / DemoPass123!")

    def _user(self, username, is_staff=False, is_superuser=False, role="citizen", state="", dept="", points=0):
        u, c = User.objects.get_or_create(username=username, defaults={"email": f"{username}@demo.local", "is_staff": is_staff, "is_superuser": is_superuser})
        if c:
            u.set_password(DEMO_PASSWORD); u.is_staff = is_staff; u.is_superuser = is_superuser; u.save()
        Profile.objects.update_or_create(user=u, defaults={"role": role, "state": state, "department": dept, "points": points})
        return u

    def _hero(self, citizen, officers, sup, rnd):
        heroes = [
            ("manhole", "CRITICAL: Open manhole near City Montessori School, Gomti Nagar", "Bachche school jaate hain yahan, bahut khatra! Open manhole, urgent cover needed.", "UP", 26.85, 80.95),
            ("water", "Burst pipeline flooding MG Road Kanpur", "Major pipeline burst, paani waste ho raha hai, road flooded.", "UP", 26.45, 80.33),
            ("road", "Deep potholes outside Andheri station", "Multiple deep potholes causing accidents near station.", "MH", 19.11, 72.85),
        ]
        for cat, title, desc, st, la, lo in heroes:
            full = analyze_report_full(title=title, description=desc, category=cat, latitude=la, longitude=lo)
            r = Report.objects.create(citizen=citizen, title=title, description=desc, category=cat, priority="critical",
                                      priority_score=92, priority_reasons=["hero demo"], status="resolved", latitude=la, longitude=lo,
                                      address="Hero location", state=st, department=full["department"], ai_source="rules",
                                      sla_due=timezone.now() - timedelta(hours=5), rating=5, rating_feedback="Excellent, verified fixed!")
            try:
                r.image.save("hero.jpg", placeholder_image(cat, title), save=True)
                r.resolution_image.save("hero_after.jpg", placeholder_image(cat, title, after=True), save=True)
            except Exception:
                pass
            StatusEvent.objects.create(report=r, old_status="", new_status="reported", actor=citizen)
            StatusEvent.objects.create(report=r, old_status="reported", new_status="assigned", actor=sup, note="escalated, assigned")
            StatusEvent.objects.create(report=r, old_status="assigned", new_status="resolved", actor=sup, note="fixed + verified")


def get_state(u):
    try:
        return u.profile.state
    except Exception:
        return ""
