from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.utils import timezone

from reports.models import Profile, Report

STALE_HOURS = 48


class Command(BaseCommand):
    help = (
        "Emails a digest of high-priority reports still 'Reported' after "
        f"{STALE_HOURS} hours to the relevant state admin(s) and all "
        "superadmins. Intended to be run on a schedule (cron / Windows "
        "Task Scheduler) since this project has no background job runner."
    )

    def handle(self, *args, **options):
        cutoff = timezone.now() - timedelta(hours=STALE_HOURS)
        stale = Report.objects.filter(priority="high", status="reported", created_at__lt=cutoff)

        if not stale.exists():
            self.stdout.write("No escalations to send.")
            return

        superadmin_emails = list(
            Profile.objects.filter(role="superadmin").exclude(user__email="").values_list("user__email", flat=True)
        )

        by_state = {}
        for report in stale:
            by_state.setdefault(report.state, []).append(report)

        for state, reports in by_state.items():
            admin_emails = list(
                Profile.objects.filter(role="admin", state=state)
                .exclude(user__email="")
                .values_list("user__email", flat=True)
            )
            recipients = sorted(set(admin_emails) | set(superadmin_emails))
            if not recipients:
                continue

            lines = [f"#{r.id} {r.title} — reported {r.created_at:%d %b %Y %H:%M}" for r in reports]
            send_mail(
                subject=f"[CivicConnect] {len(reports)} escalated report(s) need attention",
                message="\n".join(lines),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=True,
            )
            self.stdout.write(f"Sent digest for '{state or 'unspecified state'}' to {recipients}")
