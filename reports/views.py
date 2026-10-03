from datetime import timedelta

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Avg, Count, DurationField, ExpressionWrapper, F, Q
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from . import permissions as perm
from .ai.service import analyze_report_full, content_hash
from .constants import SLA_HOURS, STATE_NAME_LOOKUP, STATES
from .forms import CreateAdminForm, ReportForm, SignupForm
from .models import AIAnalysis, Comment, Notification, Profile, Report, StatusEvent, Vote
from .roles import get_profile
from .uploads import make_thumbnail, validate_and_clean_image

ESCALATION_HOURS = 48


def _sla_due(priority, base=None):
    base = base or timezone.now()
    return base + timedelta(hours=SLA_HOURS.get(priority, 120))


def home(r):
    total = Report.objects.count()
    resolved = Report.objects.filter(status__in=("resolved", "confirmed")).count()
    in_progress = Report.objects.filter(status__in=("progress", "assigned", "acknowledged")).count()
    agg = Report.objects.filter(resolved_at__isnull=False).aggregate(
        avg=Avg(F("resolved_at") - F("created_at"))
    )
    avg_h = round(agg["avg"].total_seconds() / 3600, 1) if agg["avg"] else None
    cities = Report.objects.exclude(address="").values("state").distinct().count()
    latest = Report.objects.filter(status__in=("resolved", "confirmed")).order_by(
        "-resolved_at", "-created_at"
    )[:6]
    live_qs = (
        Report.objects.exclude(status__in=("resolved", "confirmed"))
        .exclude(needs_review=True)
        .order_by("-created_at")[:25]
    )
    live_issues = [x for x in live_qs if len((x.title or "").strip()) > 8][:8]
    return render(
        r,
        "home.html",
        {
            "latest": latest,
            "live_issues": live_issues,
            "stats": {
                "total": total,
                "resolved": resolved,
                "in_progress": in_progress,
                "avg_h": avg_h,
                "states": cities,
            },
        },
    )


def signup(r):
    if r.user.is_authenticated:
        return redirect("home")
    if r.method == "POST":
        form = SignupForm(r.POST)
        if form.is_valid():
            user = form.save()
            auth_login(r, user)
            messages.success(r, "Welcome to CivicConnect AI! Your account is ready.")
            return redirect("home")
    else:
        form = SignupForm()
    return render(r, "signup.html", {"form": form})


def _run_analysis_and_apply(x, form_image, title, description, category, lat, lon, exclude_pk=None):
    image_bytes, mime = None, None
    if form_image and hasattr(form_image, "read"):
        try:
            form_image.seek(0)
            image_bytes = form_image.read()
            mime = getattr(form_image, "content_type", "image/jpeg")
            form_image.seek(0)
        except Exception:
            pass
    full = analyze_report_full(
        title=title,
        description=description,
        category=category,
        latitude=lat,
        longitude=lon,
        exclude_pk=exclude_pk,
        image_bytes=image_bytes,
        image_mime_type=mime,
    )
    x.department = full["department"]
    x.ai_priority_suggested = full["suggested_priority"]
    x.ai_source = full["ai_source"]
    x.priority = full["suggested_priority"]
    x.priority_score = int(full["priority_score"])
    x.priority_reasons = full["priority_reasons"]
    x.action_brief = full.get("action_brief", "")
    x.needs_review = full["flag"] != "ok"
    x.flag_reason = full["flag"] if x.needs_review else ""
    if full["duplicates"]:
        x.duplicate_of_id = full["duplicates"][0]["id"]
    else:
        x.duplicate_of = None
    x.sla_due = _sla_due(x.priority)
    return full


def _record_analysis(report, full):
    try:
        AIAnalysis.objects.create(
            report=report,
            content_hash=content_hash(
                report.title, report.description, report.category, report.latitude, report.longitude
            ),
            source=full["ai_source"],
            model=getattr(settings, "GEMINI_MODEL", ""),
            latency_ms=full.get("latency_ms", 0),
            confidence=full.get("confidence", 0.0),
            payload=full,
        )
    except Exception:
        pass


@login_required
def new(r):
    f = ReportForm(r.POST or None, r.FILES or None)
    if r.method == "POST" and f.is_valid():
        x = f.save(commit=False)
        x.citizen = r.user
        other_issue = f.cleaned_data.get("other_issue", "").strip()
        if other_issue:
            x.description = (x.description + "\n\n" + other_issue).strip() if x.description else other_issue
        # upload validation
        raw_image = f.cleaned_data.get("image")
        gps_hint = None
        if raw_image:
            cleaned, gps_hint, err = validate_and_clean_image(raw_image)
            if err:
                f.add_error("image", err)
                return render(r, "form.html", {"form": f, "states": STATES})
            if gps_hint and not x.latitude:
                try:
                    x.latitude, x.longitude = gps_hint
                except Exception:
                    pass
            # replace with cleaned (EXIF stripped)
            x.image.save(cleaned.name, cleaned, save=False)
        if not x.description:
            f.add_error("description", "Please describe the issue.")
            return render(r, "form.html", {"form": f, "states": STATES})
        full = _run_analysis_and_apply(
            x, raw_image, x.title, x.description, x.category, x.latitude, x.longitude
        )
        x.save()
        if x.image:
            try:
                thumb = make_thumbnail(x.image)
                if thumb:
                    x.image_thumb.save(f"thumb_{x.pk}.jpg", thumb, save=True)
            except Exception:
                pass
        _record_analysis(x, full)
        StatusEvent.objects.create(
            report=x, old_status="", new_status="reported", actor=r.user, note="Report submitted"
        )
        # civic points
        try:
            p = get_profile(r.user)
            p.points = (p.points or 0) + 10
            p.save(update_fields=["points"])
        except Exception:
            pass
        if full["duplicates"]:
            messages.warning(
                r,
                f"Heads up: this looks similar to report #{full['duplicates'][0]['id']} nearby. Linked to avoid duplicate work.",  # noqa: E501
            )
        return redirect("success", x.pk)
    return render(r, "form.html", {"form": f, "states": STATES})


def _ai_rate_ok(key):
    # 30 requests / hour per key (user or IP)
    count = cache.get(key, 0)
    if count >= 30:
        return False
    cache.set(key, count + 1, 3600)
    return True


@login_required
@require_GET
def ai_suggest(r):
    ident = f"ai:{r.user.id}"
    if not _ai_rate_ok(ident):
        return JsonResponse({"success": False, "error": "Rate limit exceeded. Slow down."}, status=429)
    title = r.GET.get("title", "")
    description = r.GET.get("description", "")
    category = r.GET.get("category", "")
    lat = r.GET.get("lat") or None
    lon = r.GET.get("lon") or None
    if not (title.strip() or description.strip()):
        return JsonResponse({"success": True, "empty": True})
    ch = content_hash(title, description, category, lat, lon)
    cached = cache.get(f"ai_suggest:{ch}")
    if cached:
        return JsonResponse({"success": True, "cached": True, **cached})
    from .ai.service import analyze_report as thin

    analysis = thin(title=title, description=description, category=category, latitude=lat, longitude=lon)
    cache.set(f"ai_suggest:{ch}", analysis, 600)
    return JsonResponse({"success": True, **analysis})


def success(r, pk):
    x = get_object_or_404(Report, pk=pk)
    if not r.user.is_authenticated or (x.citizen != r.user and not perm.can_view_report(r.user, x)):
        return redirect("mine")
    return render(r, "success.html", {"report": x})


@login_required
def mine(r):
    reports = (
        Report.objects.filter(citizen=r.user).order_by("-created_at").prefetch_related("votes", "comments")
    )
    return render(r, "mine.html", {"reports": reports})


@login_required
def detail(r, pk):
    x = get_object_or_404(
        Report.objects.select_related("citizen", "assigned_to").prefetch_related(
            "comments__user", "timeline__actor", "votes"
        ),
        pk=pk,
    )
    if not perm.can_view_report(r.user, x):
        messages.error(r, "You don't have access to that report.")
        return redirect("mine")
    analysis = x.analyses.order_by("-created_at").first()
    comments = x.comments.select_related("user").order_by("created_at")
    if not perm.is_staff_role(r.user):
        comments = comments.filter(internal_only=False)
    return render(r, "detail.html", {"report": x, "analysis": analysis, "comments": comments})


@login_required
@require_POST
def add_comment(r, pk):
    report = get_object_or_404(Report, pk=pk)
    if not perm.can_comment(r.user, report):
        messages.error(r, "You can't comment on that report.")
        return redirect("mine")
    text = r.POST.get("text", "").strip()
    internal = r.POST.get("internal_only") == "1" and perm.is_staff_role(r.user)
    if text:
        Comment.objects.create(report=report, user=r.user, text=text[:2000], internal_only=internal)
    return redirect("detail", pk=pk)


@login_required
@require_POST
def vote_report(r, pk):
    report = get_object_or_404(Report, pk=pk)
    if not perm.can_vote(r.user, report):
        return redirect("detail", pk=pk)
    vote = Vote.objects.filter(report=report, user=r.user).first()
    if vote:
        vote.delete()
    else:
        Vote.objects.create(report=report, user=r.user)
    return redirect("detail", pk=pk)


def notify_status_change(report):
    try:
        Notification.objects.create(
            user=report.citizen,
            report=report,
            message=f"Report #{report.id} is now {report.get_status_display()}",
        )
    except Exception:
        pass
    if not report.citizen.email:
        return
    try:
        send_mail(
            subject=f"Your report #{report.id} is now {report.get_status_display()}",
            message=(
                f'Hi {report.citizen.username},\n\nYour report "{report.title}" is now: {report.get_status_display()}.\n\nView it at /reports/{report.id}/\n\nCivicConnect AI'  # noqa: E501
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[report.citizen.email],
            fail_silently=True,
        )
    except Exception:
        pass


@login_required
def update_status(request, pk):
    report = get_object_or_404(Report, pk=pk)
    if not perm.can_change_status(request.user, report):
        messages.error(request, "You can't update that report.")
        return redirect("dashboard")
    if request.method == "POST":
        new_status = request.POST.get("status")
        valid = [c for c, _ in Report.STATUS]
        if new_status in valid and new_status != report.status:
            old = report.status
            report.status = new_status
            report.resolved_at = timezone.now() if new_status in ("resolved", "confirmed") else None
            if new_status in ("reopened", "reported"):
                report.sla_due = _sla_due(report.priority)
            report.save()
            StatusEvent.objects.create(
                report=report,
                old_status=old,
                new_status=new_status,
                actor=request.user,
                note=request.POST.get("note", "")[:255],
            )
            notify_status_change(report)
            messages.success(request, "Report status updated successfully.")
    # staff stay on dashboard, citizens go to detail
    if perm.is_staff_role(request.user):
        return redirect("dashboard")
    return redirect("detail", pk=pk)


def _scoped_reports(profile):
    qs = Report.objects.all()
    if profile.role == "admin":
        qs = qs.filter(state=profile.state)
    elif profile.role == "officer":
        qs = qs.filter(state=profile.state)
        if profile.department:
            qs = qs.filter(
                Q(assigned_to__isnull=True)
                | Q(assigned_to__profile__user__isnull=True)
                | Q(department=profile.department)
                | Q(assigned_to__isnull=False)
            )
    return qs


def _apply_common_filters(qs, r, profile):
    c = r.GET.get("category")
    s = r.GET.get("status")
    p = r.GET.get("priority")
    q = r.GET.get("q")
    state_filter = r.GET.get("state")
    if c:
        qs = qs.filter(category=c)
    if s:
        qs = qs.filter(status=s)
    if p:
        qs = qs.filter(priority=p)
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if profile.role == "superadmin" and state_filter:
        qs = qs.filter(state=state_filter)
    return qs


@login_required
def dashboard(r):
    profile = get_profile(r.user)
    if profile.role == "citizen":
        return redirect("mine")
    qs = (
        _apply_common_filters(_scoped_reports(profile), r, profile)
        .select_related("citizen", "assigned_to")
        .prefetch_related("votes")
        .annotate(vote_count=Count("votes"))
        .order_by("-created_at")
    )
    escalation_cutoff = timezone.now() - timedelta(hours=ESCALATION_HOURS)
    escalated_count = qs.filter(
        priority__in=("high", "critical"),
        status__in=("reported", "acknowledged"),
        created_at__lt=escalation_cutoff,
    ).count()
    needs_review_count = qs.filter(needs_review=True).count()
    overdue_count = (
        qs.filter(sla_due__lt=timezone.now()).exclude(status__in=("resolved", "confirmed")).count()
    )
    paginator = Paginator(qs, 25)
    page = paginator.get_page(r.GET.get("page"))
    briefing = _daily_briefing(qs)
    return render(
        r,
        "dashboard.html",
        {
            "reports": page,
            "page_obj": page,
            "categories": Report.CATEGORIES,
            "states": STATES,
            "profile": profile,
            "escalation_hours": ESCALATION_HOURS,
            "escalation_cutoff": escalation_cutoff,
            "escalated_count": escalated_count,
            "needs_review_count": needs_review_count,
            "overdue_count": overdue_count,
            "briefing": briefing,
            "stats": [
                qs.count(),
                qs.filter(status="reported").count(),
                qs.filter(status="progress").count(),
                qs.filter(status__in=("resolved", "confirmed")).count(),
            ],
        },
    )


def _report_geo_payload(qs):
    return [
        {
            "id": rep.id,
            "title": rep.title,
            "category": rep.get_category_display(),
            "status": rep.status,
            "status_display": rep.get_status_display(),
            "priority": rep.priority,
            "state": rep.get_state_display(),
            "lat": float(rep.latitude),
            "lng": float(rep.longitude),
        }
        for rep in qs.filter(latitude__isnull=False, longitude__isnull=False)[:2000]
    ]


@login_required
def dashboard_map_data(r):
    profile = get_profile(r.user)
    if profile.role == "citizen":
        return JsonResponse({"reports": []})
    qs = _apply_common_filters(_scoped_reports(profile), r, profile)
    return JsonResponse({"reports": _report_geo_payload(qs)})


def public_reports(r):
    qs = Report.objects.all()
    if r.GET.get("state"):
        qs = qs.filter(state=r.GET.get("state"))
    if r.GET.get("category"):
        qs = qs.filter(category=r.GET.get("category"))
    total = qs.count()
    resolved = qs.filter(status__in=("resolved", "confirmed")).count()
    by_state = list(qs.exclude(state="").values("state").annotate(count=Count("id")).order_by("-count")[:10])
    trending = list(qs.values("category").annotate(count=Count("id")).order_by("-count")[:5])
    improved = list(
        qs.filter(status__in=("resolved", "confirmed"))
        .exclude(state="")
        .values("state")
        .annotate(count=Count("id"))
        .order_by("-count")[:3]
    )
    return render(
        r,
        "transparency.html",
        {
            "states": STATES,
            "categories": Report.CATEGORIES,
            "total": total,
            "resolved": resolved,
            "by_state": by_state,
            "trending": trending,
            "improved": improved,
        },
    )


def public_map_data(r):
    qs = Report.objects.all()
    if r.GET.get("state"):
        qs = qs.filter(state=r.GET.get("state"))
    if r.GET.get("category"):
        qs = qs.filter(category=r.GET.get("category"))
    # never expose PII: payload has no citizen info
    return JsonResponse({"reports": _report_geo_payload(qs)})


@login_required
def analytics(r):
    profile = get_profile(r.user)
    if profile.role == "citizen":
        return redirect("mine")
    qs = _scoped_reports(profile)
    by_category = list(qs.values("category").annotate(count=Count("id")).order_by("-count"))
    by_status = list(qs.values("status").annotate(count=Count("id")).order_by("status"))
    by_state = (
        list(qs.exclude(state="").values("state").annotate(count=Count("id")).order_by("-count"))
        if profile.role == "superadmin"
        else []
    )
    resolved_qs = qs.filter(status__in=("resolved", "confirmed"), resolved_at__isnull=False)
    avg_resolution = resolved_qs.annotate(
        duration=ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField())
    ).aggregate(avg=Avg("duration"))["avg"]
    avg_resolution_hours = round(avg_resolution.total_seconds() / 3600, 1) if avg_resolution else None
    since = timezone.now() - timedelta(days=30)
    trend = list(
        qs.filter(created_at__gte=since)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(count=Count("id"))
        .order_by("day")
    )
    return render(
        r,
        "analytics.html",
        {
            "profile": profile,
            "by_category": by_category,
            "by_status": by_status,
            "by_state": by_state,
            "avg_resolution_hours": avg_resolution_hours,
            "trend": trend,
        },
    )


@login_required
def manage_admins(r):
    profile = get_profile(r.user)
    if profile.role != "superadmin":
        return redirect("dashboard")
    if r.method == "POST":
        form = CreateAdminForm(r.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_staff = True
            role = form.cleaned_data["role"]
            state = form.cleaned_data.get("state", "")
            dept = form.cleaned_data.get("department", "") if hasattr(form, "cleaned_data") else ""
            if role == "superadmin":
                user.is_superuser = True
            user.save()
            Profile.objects.update_or_create(
                user=user,
                defaults={
                    "role": role,
                    "state": state if role in ("admin", "officer") else "",
                    "department": dept if role == "officer" else "",
                },
            )
            messages.success(r, f"{user.username} added.")
            return redirect("manage_admins")
    else:
        form = CreateAdminForm()
    admins = (
        Profile.objects.filter(role__in=["admin", "officer", "superadmin"])
        .select_related("user")
        .order_by("role", "state")
    )
    return render(r, "manage_admins.html", {"form": form, "admins": admins, "profile": profile})


@login_required
def demote_admin(r, user_id):
    profile = get_profile(r.user)
    if profile.role != "superadmin":
        return redirect("dashboard")
    target = get_object_or_404(User, pk=user_id)
    if target == r.user:
        messages.error(r, "You can't remove your own admin access.")
        return redirect("manage_admins")
    target_profile = get_profile(target)
    target_profile.role = "citizen"
    target_profile.state = ""
    target_profile.department = ""
    target_profile.save()
    target.is_staff = False
    target.is_superuser = False
    target.save()
    messages.success(r, f"{target.username} is now a regular citizen.")
    return redirect("manage_admins")


@login_required
def edit_report(r, pk):
    report = get_object_or_404(Report, pk=pk)
    if report.citizen != r.user:
        return redirect("mine")
    if report.status != "reported":
        messages.error(r, "This report can no longer be edited since it's already being worked on.")
        return redirect("detail", pk=pk)
    f = ReportForm(r.POST or None, r.FILES or None, instance=report)
    if r.method == "POST" and f.is_valid():
        x = f.save(commit=False)
        other_issue = f.cleaned_data.get("other_issue", "").strip()
        if other_issue:
            x.description = (x.description + "\n\n" + other_issue).strip() if x.description else other_issue
        raw_image = f.cleaned_data.get("image") if hasattr(f.cleaned_data.get("image"), "read") else None
        full = _run_analysis_and_apply(
            x, raw_image, x.title, x.description, x.category, x.latitude, x.longitude, exclude_pk=x.pk
        )
        x.save()
        _record_analysis(x, full)
        messages.success(r, "Report updated successfully.")
        return redirect("detail", pk=pk)
    return render(r, "form.html", {"form": f, "states": STATES, "editing": True, "report": report})


@login_required
def delete_report(r, pk):
    report = get_object_or_404(Report, pk=pk)
    if report.citizen != r.user:
        return redirect("mine")
    if report.status != "reported":
        messages.error(r, "This report can no longer be deleted since it's already being worked on.")
        return redirect("detail", pk=pk)
    if r.method == "POST":
        report.delete()
        messages.success(r, "Report deleted.")
        return redirect("mine")
    return render(r, "confirm_delete.html", {"report": report})


def get_address(request):
    latitude = request.GET.get("lat")
    longitude = request.GET.get("lon")
    if not latitude or not longitude:
        return JsonResponse({"success": False, "error": "Location coordinates are missing."}, status=400)
    # cache reverse-geocode by rounded coords (also respects Nominatim's 1 req/s policy)
    try:
        key = f"geo:{round(float(latitude), 3)}:{round(float(longitude), 3)}"
        hit = cache.get(key)
        if hit:
            return JsonResponse({"success": True, **hit})
    except (TypeError, ValueError):
        pass
    try:
        resp = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"format": "jsonv2", "lat": latitude, "lon": longitude},
            headers={"User-Agent": "CivicConnectAI/1.0 (contact: noreply@civicconnect.local)"},
            timeout=10,
        )
        resp.raise_for_status()
        d = resp.json()
        a = d.get("address") or {}
        pretty = ", ".join(
            p
            for p in [
                " ".join(p for p in [a.get("house_number"), a.get("road")] if p).strip(),
                a.get("suburb") or a.get("neighbourhood"),
                a.get("city") or a.get("town") or a.get("village") or a.get("county"),
            ]
            if p and p.strip()
        )
        payload = {
            "address": pretty or d.get("display_name") or "Address not found",
            "state": STATE_NAME_LOOKUP.get((a.get("state") or "").strip().lower(), ""),
        }
        cache.set(key, payload, 86400)
        return JsonResponse({"success": True, **payload})
    except requests.RequestException:
        # optional Geoapify fallback if a key is configured
        api_key = settings.GEOAPIFY_API_KEY
        if not api_key:
            return JsonResponse(
                {"success": False, "error": "Unable to contact location service."}, status=500
            )
        try:
            response = requests.get(
                "https://api.geoapify.com/v1/geocode/reverse",
                params={"lat": latitude, "lon": longitude, "apiKey": api_key},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("features"):
                props = data["features"][0].get("properties", {})
                payload = {
                    "address": props.get("formatted") or "Address not found",
                    "state": STATE_NAME_LOOKUP.get((props.get("state") or "").strip().lower(), ""),
                }
                cache.set(key, payload, 86400)
                return JsonResponse({"success": True, **payload})
            return JsonResponse({"success": False, "error": "Address not found."})
        except requests.RequestException:
            return JsonResponse(
                {"success": False, "error": "Unable to contact location service."}, status=500
            )


# ---- new workflows ----


@login_required
@require_POST
def assign_report(r, pk):
    report = get_object_or_404(Report, pk=pk)
    if not perm.can_assign(r.user, report):
        messages.error(r, "You can't assign that report.")
        return redirect("dashboard")
    user_id = r.POST.get("officer")
    try:
        officer = User.objects.get(pk=user_id)
        oprof = get_profile(officer)
        if oprof.role != "officer":
            raise User.DoesNotExist
    except (User.DoesNotExist, TypeError, ValueError):
        messages.error(r, "Select a valid field officer.")
        return redirect("detail", pk=pk)
    report.assigned_to = officer
    if report.status == "reported":
        report.status = "assigned"
    report.save()
    StatusEvent.objects.create(
        report=report,
        old_status="reported",
        new_status="assigned",
        actor=r.user,
        note=f"Assigned to {officer.username}",
    )
    Notification.objects.create(
        user=officer, report=report, message=f"Assigned report #{report.id}: {report.title[:60]}"
    )
    messages.success(r, f"Assigned to {officer.username}.")
    return redirect("detail", pk=pk)


@login_required
def suggest_assignee(r, pk):
    report = get_object_or_404(Report, pk=pk)
    if not perm.can_assign(r.user, report):
        return JsonResponse({"success": False}, status=403)
    officers = User.objects.filter(profile__role="officer", profile__state=report.state)
    if report.department:
        officers = officers.filter(profile__department=report.department) | User.objects.filter(
            profile__role="officer", profile__state=report.state, profile__department=""
        )
    data = []
    for o in officers.select_related("profile")[:20]:
        load = Report.objects.filter(
            assigned_to=o, status__in=("assigned", "progress", "acknowledged")
        ).count()
        data.append({"id": o.id, "username": o.username, "load": load})
    data.sort(key=lambda d: d["load"])
    return JsonResponse({"success": True, "officers": data[:5]})


@login_required
def my_tasks(r):
    profile = get_profile(r.user)
    if profile.role != "officer":
        return redirect("dashboard" if perm.is_staff_role(r.user) else "mine")
    qs = Report.objects.filter(assigned_to=r.user).order_by("sla_due", "-priority_score")
    return render(r, "my_tasks.html", {"reports": qs, "profile": profile})


@login_required
def notifications(r):
    notifs = r.user.notifications.order_by("-created_at")[:50]
    unread = r.user.notifications.filter(read=False).count()
    if r.GET.get("mark") == "read":
        r.user.notifications.filter(read=False).update(read=True)
        return redirect("notifications")
    return render(r, "notifications.html", {"notifications": notifs, "unread": unread})


@login_required
def notifications_api(r):
    items = list(
        r.user.notifications.order_by("-created_at").values(
            "id", "message", "read", "report_id", "created_at"
        )[:20]
    )
    return JsonResponse(
        {"unread": r.user.notifications.filter(read=False).count(), "items": items},
    )


@login_required
@require_POST
def confirm_report(r, pk):
    report = get_object_or_404(Report, pk=pk)
    if report.citizen != r.user or report.status != "resolved":
        return redirect("detail", pk=pk)
    report.status = "confirmed"
    report.rating = int(r.POST.get("rating", "5")[:1]) if r.POST.get("rating") else None
    report.rating_feedback = r.POST.get("feedback", "")[:1000]
    report.save()
    StatusEvent.objects.create(
        report=report, old_status="resolved", new_status="confirmed", actor=r.user, note="Citizen confirmed"
    )
    return redirect("detail", pk=pk)


@login_required
@require_POST
def reopen_report(r, pk):
    report = get_object_or_404(Report, pk=pk)
    if report.citizen != r.user or report.status not in ("resolved", "confirmed"):
        return redirect("detail", pk=pk)
    old = report.status
    report.status = "reopened"
    report.sla_due = _sla_due(report.priority)
    report.save()
    StatusEvent.objects.create(
        report=report, old_status=old, new_status="reopened", actor=r.user, note="Citizen reopened"
    )
    return redirect("detail", pk=pk)


@login_required
@require_GET
def assistant_api(r):
    """CivicBot: DB-grounded answers, never invented."""
    q = (r.GET.get("q", "") or "").lower()
    profile = get_profile(r.user)
    scope = _scoped_reports(profile) if perm.is_staff_role(r.user) else Report.objects.filter(citizen=r.user)
    if "critical" in q:
        n = scope.filter(priority="critical").exclude(status__in=("resolved", "confirmed")).count()
        return JsonResponse({"answer": f"There are {n} unresolved critical reports in your scope."})
    if "my report" in q or ("where" in q and "report" in q):
        mine = Report.objects.filter(citizen=r.user).order_by("-created_at")[:3]
        if not mine:
            return JsonResponse({"answer": "You have no reports yet. Tap Report to file one."})
        return JsonResponse(
            {
                "answer": "Your latest: "
                + "; ".join(f"#{x.id} {x.title} ({x.get_status_display()})" for x in mine)
            }
        )
    if "how" in q and "report" in q:
        return JsonResponse(
            {
                "answer": "Go to Report, add a photo, describe the issue, pin the location, review and submit. AI triage runs automatically."  # noqa: E501
            }
        )
    if "sla" in q or "overdue" in q or "breach" in q:
        n = scope.filter(sla_due__lt=timezone.now()).exclude(status__in=("resolved", "confirmed")).count()
        return JsonResponse({"answer": f"{n} reports are past SLA in your scope."})
    total = scope.count()
    return JsonResponse(
        {
            "answer": f"I can see {total} reports in your scope. Ask about critical reports, your reports, SLA breaches, or how to report."  # noqa: E501
        }
    )


def _daily_briefing(qs):
    since = timezone.now() - timedelta(days=1)
    new = qs.filter(created_at__gte=since).count()
    crit = qs.filter(priority="critical").exclude(status__in=("resolved", "confirmed")).count()
    overdue = qs.filter(sla_due__lt=timezone.now()).exclude(status__in=("resolved", "confirmed")).count()
    hot = list(
        qs.filter(created_at__gte=timezone.now() - timedelta(days=7))
        .exclude(state="")
        .values("state")
        .annotate(c=Count("id"))
        .order_by("-c")[:3]
    )
    return {"new_24h": new, "critical_open": crit, "overdue": overdue, "hotspots": hot}


@login_required
@require_GET
def briefing_api(r):
    profile = get_profile(r.user)
    if not perm.is_staff_role(r.user):
        return JsonResponse({"success": False}, status=403)
    qs = _scoped_reports(profile)
    return JsonResponse({"success": True, "briefing": _daily_briefing(qs)})


@login_required
@require_GET
def ai_status_api(r, pk):
    report = get_object_or_404(Report, pk=pk)
    if not perm.can_view_report(r.user, report):
        return JsonResponse({"success": False}, status=403)
    a = report.analyses.order_by("-created_at").first()
    if not a:
        return JsonResponse({"success": True, "pending": True})
    return JsonResponse({"success": True, "pending": False, "source": a.source, "payload": a.payload})


@login_required
@require_GET
def console(r):
    profile = get_profile(r.user)
    if profile.role != "superadmin":
        return redirect("dashboard" if perm.is_staff_role(r.user) else "mine")
    from django.db.models import Q

    states = (
        Report.objects.exclude(state="")
        .values("state")
        .annotate(
            total=Count("id"),
            resolved=Count("id", filter=Q(status__in=("resolved", "confirmed"))),
            avg_rating=Avg("rating"),
            breached=Count(
                "id", filter=Q(sla_due__lt=timezone.now()) & ~Q(status__in=("resolved", "confirmed"))
            ),
        )
        .order_by("-total")
    )
    rows = []
    for s in states:
        qs = Report.objects.filter(state=s["state"])
        res = qs.filter(status__in=("resolved", "confirmed"), resolved_at__isnull=False).annotate(
            duration=ExpressionWrapper(F("resolved_at") - F("created_at"), output_field=DurationField())
        )
        avg = res.aggregate(a=Avg("duration"))["a"]
        open_n = qs.exclude(status__in=("resolved", "confirmed")).count()
        rows.append(
            {
                "state": s["state"],
                "total": s["total"],
                "resolved": s["resolved"],
                "avg_h": round(avg.total_seconds() / 3600, 1) if avg else None,
                "sla_ok": round(100 * (s["total"] - s["breached"]) / s["total"], 1) if s["total"] else 100,
                "avg_rating": round(s["avg_rating"], 1) if s["avg_rating"] else None,
                "open": open_n,
            }
        )
    rows.sort(key=lambda x: (x["sla_ok"], x["resolved"]), reverse=True)
    ai = AIAnalysis.objects.aggregate(
        total=Count("id"),
        gemini=Count("id", filter=Q(source="gemini")),
        avg_ms=Avg("latency_ms"),
        low_conf=Count("id", filter=Q(confidence__lt=0.5)),
    )
    queue = {
        "reported": Report.objects.filter(status="reported").count(),
        "active": Report.objects.filter(status__in=("acknowledged", "assigned", "progress")).count(),
        "reopened": Report.objects.filter(status="reopened").count(),
        "needs_review": Report.objects.filter(needs_review=True).count(),
    }
    audit = StatusEvent.objects.select_related("report", "actor").order_by("-created_at")[:30]
    return render(
        r, "console.html", {"profile": profile, "rows": rows, "ai": ai, "queue": queue, "audit": audit}
    )


def healthz(r):
    return JsonResponse({"ok": True})


@login_required
@require_POST
def bulk_update(r):
    if not perm.is_staff_role(r.user):
        return redirect("mine")
    ids = [int(x) for x in r.POST.getlist("ids") if str(x).isdigit()]
    action = r.POST.get("action", "")
    updated = 0
    for rep in Report.objects.filter(pk__in=ids):
        if action.startswith("status:"):
            new_status = action.split(":", 1)[1]
            if (
                new_status in [c for c, _ in Report.STATUS]
                and perm.can_change_status(r.user, rep)
                and new_status != rep.status
            ):
                old = rep.status
                rep.status = new_status
                rep.resolved_at = timezone.now() if new_status in ("resolved", "confirmed") else None
                rep.save()
                StatusEvent.objects.create(
                    report=rep, old_status=old, new_status=new_status, actor=r.user, note="bulk"
                )
                notify_status_change(rep)
                updated += 1
        elif action.startswith("priority:") and perm.can_assign(r.user, rep):
            new_p = action.split(":", 1)[1]
            if new_p in [c for c, _ in Report.PRIORITY]:
                rep.priority = new_p
                rep.sla_due = _sla_due(new_p)
                rep.save()
                updated += 1
    messages.success(r, f"Bulk action applied to {updated} report(s).")
    return redirect("dashboard")


@login_required
@require_GET
def export_csv(r):
    profile = get_profile(r.user)
    if not perm.is_staff_role(r.user):
        return redirect("mine")
    import csv

    from django.http import HttpResponse

    qs = (
        _apply_common_filters(_scoped_reports(profile), r, profile)
        .select_related("citizen", "assigned_to")
        .order_by("-created_at")[:5000]
    )
    resp = HttpResponse(content_type="text/csv")
    resp["Content-Disposition"] = "attachment; filename=civicconnect_reports.csv"
    w = csv.writer(resp)
    w.writerow(
        [
            "id",
            "title",
            "category",
            "priority",
            "priority_score",
            "status",
            "state",
            "department",
            "assigned_to",
            "citizen",
            "created_at",
            "resolved_at",
            "sla_due",
            "address",
        ]
    )
    for x in qs:
        w.writerow(
            [
                x.id,
                x.title,
                x.category,
                x.priority,
                x.priority_score,
                x.status,
                x.state,
                x.department,
                x.assigned_to.username if x.assigned_to else "",
                x.citizen.username,
                x.created_at.isoformat(),
                x.resolved_at.isoformat() if x.resolved_at else "",
                x.sla_due.isoformat() if x.sla_due else "",
                x.address,
            ]
        )
    return resp
