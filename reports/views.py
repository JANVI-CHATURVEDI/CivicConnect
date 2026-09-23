from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.mail import send_mail
from django.http import JsonResponse
from django.conf import settings
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.views.decorators.http import require_GET
from datetime import timedelta
import requests

from .models import Report, Comment, Vote, Profile
from .forms import ReportForm, SignupForm, CreateAdminForm
from .constants import STATES, STATE_NAME_LOOKUP
from .roles import get_profile
from . import ai_utils

ESCALATION_HOURS = 48


def home(r):
    return render(
        r, "home.html", {"latest": Report.objects.filter(status="resolved")[:6]}
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


@login_required
def new(r):
    f = ReportForm(r.POST or None, r.FILES or None)

    if r.method == "POST" and f.is_valid():
        x = f.save(commit=False)
        x.citizen = r.user

        other_issue = f.cleaned_data.get("other_issue", "").strip()
        if other_issue:
            x.description = (x.description + "\n\n" + other_issue).strip() if x.description else other_issue

        image_bytes = None
        image_mime_type = None
        uploaded_image = f.cleaned_data.get("image")
        if uploaded_image:
            uploaded_image.seek(0)
            image_bytes = uploaded_image.read()
            image_mime_type = getattr(uploaded_image, "content_type", None) or "image/jpeg"
            uploaded_image.seek(0)

        analysis = ai_utils.analyze_report(
            title=x.title,
            description=x.description,
            category=x.category,
            latitude=x.latitude,
            longitude=x.longitude,
            image_bytes=image_bytes,
            image_mime_type=image_mime_type,
        )

        x.department = analysis["department"]
        x.ai_priority_suggested = analysis["suggested_priority"]
        x.ai_source = analysis["ai_source"]
        x.needs_review = analysis["flag"] != "ok"
        x.flag_reason = analysis["flag"] if x.needs_review else ""

        if analysis["duplicates"]:
            x.duplicate_of_id = analysis["duplicates"][0]["id"]

        x.save()

        if analysis["duplicates"]:
            messages.warning(
                r,
                f"Heads up: this looks similar to an existing report "
                f"(#{analysis['duplicates'][0]['id']}) nearby. We've linked them "
                f"so authorities don't duplicate work — you can still track yours separately.",
            )

        return redirect("success", x.pk)

    return render(r, "form.html", {"form": f, "states": STATES})


@require_GET
def ai_suggest(r):
    title = r.GET.get("title", "")
    description = r.GET.get("description", "")
    category = r.GET.get("category", "")
    lat = r.GET.get("lat") or None
    lon = r.GET.get("lon") or None

    analysis = ai_utils.analyze_report(
        title=title,
        description=description,
        category=category,
        latitude=lat,
        longitude=lon,
    )

    return JsonResponse({"success": True, **analysis})


def success(r, pk):
    x = get_object_or_404(Report, pk=pk)
    if x.citizen != r.user and not r.user.is_staff:
        return redirect("mine")
    return render(r, "success.html", {"report": x})


@login_required
def mine(r):
    return render(
        r,
        "mine.html",
        {"reports": Report.objects.filter(citizen=r.user).order_by("-created_at")},
    )


@login_required
def detail(r, pk):
    x = get_object_or_404(Report, pk=pk)
    if x.citizen != r.user and not r.user.is_staff:
        return redirect("mine")
    return render(r, "detail.html", {"report": x})


@login_required
def add_comment(r, pk):
    report = get_object_or_404(Report, pk=pk)

    if r.method == "POST":
        text = r.POST.get("text", "").strip()

        if text:
            Comment.objects.create(
                report=report,
                user=r.user,
                text=text
            )

    return redirect("detail", pk=pk)


@login_required
def vote_report(r, pk):
    report = get_object_or_404(Report, pk=pk)

    vote = Vote.objects.filter(
        report=report,
        user=r.user
    ).first()

    if vote:
        vote.delete()
    else:
        Vote.objects.create(
            report=report,
            user=r.user
        )

    return redirect("detail", pk=pk)


def notify_status_change(report):
    if not report.citizen.email:
        return
    try:
        send_mail(
            subject=f"Your report #{report.id} is now {report.get_status_display()}",
            message=(
                f"Hi {report.citizen.username},\n\n"
                f"Your report \"{report.title}\" has been updated to: {report.get_status_display()}.\n\n"
                f"View it at /reports/{report.id}/\n\nCivicConnect AI"
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[report.citizen.email],
            fail_silently=True,
        )
    except Exception:
        pass


@login_required
def update_status(request, pk):
    profile = get_profile(request.user)
    if profile.role == "citizen":
        return redirect("mine")

    report = get_object_or_404(Report, pk=pk)

    if profile.role == "admin" and report.state != profile.state:
        messages.error(request, "You can only update reports from your own state.")
        return redirect("dashboard")

    if request.method == "POST":
        new_status = request.POST.get("status")
        valid_statuses = ["reported", "progress", "resolved"]

        if new_status in valid_statuses and new_status != report.status:
            report.status = new_status
            report.resolved_at = timezone.now() if new_status == "resolved" else None
            report.save()
            notify_status_change(report)
            messages.success(
                request,
                "Report status updated successfully."
            )

    return redirect("dashboard")


def _scoped_reports(profile):
    qs = Report.objects.all()
    if profile.role == "admin":
        qs = qs.filter(state=profile.state)
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
        qs = qs.filter(title__icontains=q)
    if profile.role == "superadmin" and state_filter:
        qs = qs.filter(state=state_filter)

    return qs


@login_required
def dashboard(r):
    profile = get_profile(r.user)
    if profile.role == "citizen":
        return redirect("mine")

    qs = _apply_common_filters(_scoped_reports(profile), r, profile).order_by("-created_at")

    escalation_cutoff = timezone.now() - timedelta(hours=ESCALATION_HOURS)
    escalated_count = qs.filter(priority="high", status="reported", created_at__lt=escalation_cutoff).count()
    needs_review_count = qs.filter(needs_review=True).count()

    return render(
        r,
        "dashboard.html",
        {
            "reports": qs,
            "categories": Report.CATEGORIES,
            "states": STATES,
            "profile": profile,
            "escalation_hours": ESCALATION_HOURS,
            "escalation_cutoff": escalation_cutoff,
            "escalated_count": escalated_count,
            "needs_review_count": needs_review_count,
            "stats": [
                qs.count(),
                qs.filter(status="reported").count(),
                qs.filter(status="progress").count(),
                qs.filter(status="resolved").count(),
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
        for rep in qs.filter(latitude__isnull=False, longitude__isnull=False)
    ]


@login_required
def dashboard_map_data(r):
    profile = get_profile(r.user)
    if profile.role == "citizen":
        return JsonResponse({"reports": []})
    qs = _apply_common_filters(_scoped_reports(profile), r, profile)
    return JsonResponse({"reports": _report_geo_payload(qs)})


def public_reports(r):
    return render(r, "transparency.html", {"states": STATES, "categories": Report.CATEGORIES})


def public_map_data(r):
    qs = Report.objects.all()
    state_filter = r.GET.get("state")
    category_filter = r.GET.get("category")
    if state_filter:
        qs = qs.filter(state=state_filter)
    if category_filter:
        qs = qs.filter(category=category_filter)
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
        if profile.role == "superadmin" else []
    )

    resolved_qs = qs.filter(status="resolved", resolved_at__isnull=False)
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

    return render(r, "analytics.html", {
        "profile": profile,
        "by_category": by_category,
        "by_status": by_status,
        "by_state": by_state,
        "avg_resolution_hours": avg_resolution_hours,
        "trend": trend,
    })


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

            if role == "superadmin":
                user.is_superuser = True

            user.save()
            Profile.objects.update_or_create(
                user=user, defaults={"role": role, "state": state if role == "admin" else ""}
            )
            messages.success(r, f"{user.username} added as {dict(form.fields['role'].choices)[role]}.")
            return redirect("manage_admins")
    else:
        form = CreateAdminForm()

    admins = Profile.objects.filter(role__in=["admin", "superadmin"]).select_related("user").order_by("role", "state")

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
    target_profile.save()

    target.is_staff = False
    target.is_superuser = False
    target.save()

    messages.success(r, f"{target.username} is now a regular citizen.")
    return redirect("manage_admins")


def get_address(request):
    latitude = request.GET.get("lat")
    longitude = request.GET.get("lon")

    if not latitude or not longitude:
        return JsonResponse({
            "success": False,
            "error": "Location coordinates are missing."
        }, status=400)

    api_key = settings.GEOAPIFY_API_KEY

    if not api_key:
        return JsonResponse({
            "success": False,
            "error": "Location service is not configured on the server."
        }, status=200)

    url = "https://api.geoapify.com/v1/geocode/reverse"

    params = {
        "lat": latitude,
        "lon": longitude,
        "apiKey": api_key
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()

        if data.get("features"):
            properties = data["features"][0].get("properties", {})

            address = (
                properties.get("formatted")
                or properties.get("address_line1")
                or "Address not found"
            )

            state_name = (properties.get("state") or "").strip().lower()
            state_code = STATE_NAME_LOOKUP.get(state_name, "")

            return JsonResponse({
                "success": True,
                "address": address,
                "state": state_code,
            })

        return JsonResponse({
            "success": False,
            "error": "Address not found."
        })

    except requests.RequestException:
        return JsonResponse({
            "success": False,
            "error": "Unable to contact location service."
        }, status=500)
