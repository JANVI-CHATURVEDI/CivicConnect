import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from reports import ai_utils
from reports.models import Profile, Report

DEMO_PASSWORD = "DemoPass123!"

STATE_CITIES = {
    "UP": ("Lucknow", 26.8467, 80.9462),
    "MH": ("Mumbai", 19.0760, 72.8777),
    "KA": ("Bengaluru", 12.9716, 77.5946),
    "TN": ("Chennai", 13.0827, 80.2707),
    "DL": ("Delhi", 28.6139, 77.2090),
    "WB": ("Kolkata", 22.5726, 88.3639),
    "GJ": ("Ahmedabad", 23.0225, 72.5714),
    "RJ": ("Jaipur", 26.9124, 75.7873),
}

ADMIN_STATES = ["UP", "MH", "KA", "TN", "DL"]

REPORT_TEMPLATES = [
    ("road", "Deep pothole near {city} market", "A large pothole has formed on the main road, causing traffic to slow down and posing a risk to two-wheelers.", "medium"),
    ("road", "Road caved in after heavy rain in {city}", "Part of the road surface collapsed after last week's rain, exposing loose gravel underneath.", "high"),
    ("water", "Water pipe burst near {city} station", "A major pipeline has burst, flooding the street and wasting a large amount of water.", "high"),
    ("water", "Slow leak from municipal tap in {city}", "A small but constant leak has been running for several days near the public tap.", "low"),
    ("garbage", "Garbage bins overflowing in {city} sector 5", "Bins haven't been cleared in over a week and waste is spilling onto the footpath.", "medium"),
    ("light", "Streetlights out on {city} ring road", "Several streetlights along a 1km stretch are non-functional, making the area unsafe at night.", "medium"),
    ("tree", "Fallen tree blocking lane in {city}", "A large tree fell across one lane after a storm and hasn't been cleared yet.", "high"),
    ("manhole", "Open manhole near {city} school", "An uncovered manhole poses a serious danger to children walking to school nearby.", "high"),
    ("traffic", "Traffic signal malfunctioning at {city} crossing", "The signal has been stuck on red for all directions, causing major congestion.", "medium"),
    ("garbage", "Illegal dumping ground forming in {city}", "Construction waste is being dumped on a vacant plot, attracting pests.", "low"),
    ("other", "Public bench damaged in {city} park", "A damaged bench near the park entrance", "low"),
]


class Command(BaseCommand):
    help = "Seeds demo users and realistic civic reports across multiple states, for a lively dashboard/map/analytics demo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset", action="store_true",
            help="Delete previously seeded demo data (usernames starting with 'demo_') before reseeding.",
        )

    def handle(self, *args, **options):
        if options["reset"]:
            deleted, _ = User.objects.filter(username__startswith="demo_").delete()
            self.stdout.write(f"Removed {deleted} previously seeded demo objects.")

        superadmin = self._get_or_create_user("demo_superadmin", "superadmin@demo.civicconnect", is_superuser=True, is_staff=True)

        admins = {}
        for state in ADMIN_STATES:
            username = f"demo_admin_{state.lower()}"
            user = self._get_or_create_user(username, f"{username}@demo.civicconnect", is_staff=True)
            Profile.objects.update_or_create(user=user, defaults={"role": "admin", "state": state})
            admins[state] = user

        citizens = [
            self._get_or_create_user(f"demo_citizen{i}", f"demo_citizen{i}@demo.civicconnect")
            for i in range(1, 7)
        ]

        created_count = 0
        report_ids_by_state = {}

        for i in range(30):
            state = random.choice(list(STATE_CITIES.keys()))
            city, base_lat, base_lng = STATE_CITIES[state]
            category, title_template, description, priority = random.choice(REPORT_TEMPLATES)
            title = title_template.format(city=city)

            status = random.choices(["reported", "progress", "resolved"], weights=[0.45, 0.25, 0.3])[0]
            days_ago = random.randint(0, 25)
            created_at = timezone.now() - timedelta(days=days_ago, hours=random.randint(0, 23))

            resolved_at = None
            if status == "resolved":
                resolved_at = created_at + timedelta(hours=random.randint(2, 96))

            # Make a couple of high-priority "reported" issues genuinely stale,
            # so the escalation banner has something real to show.
            if i < 3:
                priority = "high"
                status = "reported"
                created_at = timezone.now() - timedelta(hours=random.randint(50, 120))
                resolved_at = None

            needs_review = i in (10, 21)

            report = Report.objects.create(
                citizen=random.choice(citizens),
                title=title,
                description=description if not needs_review else "bad",
                category=category,
                priority=priority,
                status=status,
                latitude=round(base_lat + random.uniform(-0.15, 0.15), 7),
                longitude=round(base_lng + random.uniform(-0.15, 0.15), 7),
                address=f"Near {city} main road",
                state=state,
                department=ai_utils.suggest_department(category),
                ai_priority_suggested=priority,
                ai_source="rules",
                needs_review=needs_review,
                flag_reason="vague" if needs_review else "",
            )
            Report.objects.filter(pk=report.pk).update(created_at=created_at, resolved_at=resolved_at)

            report_ids_by_state.setdefault(state, []).append(report.id)
            created_count += 1

        # Link one pair of reports as duplicates for a realistic example.
        for state, ids in report_ids_by_state.items():
            if len(ids) >= 2:
                Report.objects.filter(pk=ids[0]).update(duplicate_of_id=ids[1])
                break

        self.stdout.write(self.style.SUCCESS(f"\nSeeded {created_count} reports across {len(report_ids_by_state)} states.\n"))
        self.stdout.write("Demo login credentials (password for all): " + DEMO_PASSWORD)
        self.stdout.write(f"  Super Admin : demo_superadmin")
        for state, user in admins.items():
            self.stdout.write(f"  {state} Admin   : {user.username}")
        self.stdout.write(f"  Citizens    : demo_citizen1 .. demo_citizen6")
        self.stdout.write("\nRun with --reset to remove this demo data and reseed fresh.")

    def _get_or_create_user(self, username, email, is_staff=False, is_superuser=False):
        user, created = User.objects.get_or_create(
            username=username, defaults={"email": email, "is_staff": is_staff, "is_superuser": is_superuser}
        )
        if created:
            user.set_password(DEMO_PASSWORD)
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.save()
        return user
