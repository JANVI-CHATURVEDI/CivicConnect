from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.views.decorators.http import require_GET
import requests

from .models import Report, Comment, Vote
from .forms import ReportForm, SignupForm
from . import ai_utils


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

        # Fold the free-text "other issue" box into the description so the
        # citizen's words are never silently dropped.
        other_issue = f.cleaned_data.get("other_issue", "").strip()
        if other_issue:
            x.description = (x.description + "\n\n" + other_issue).strip() if x.description else other_issue

        # ---- AI ASSIST: run before saving so every report is enriched ----
        analysis = ai_utils.analyze_report(
            title=x.title,
            description=x.description,
            category=x.category,
            latitude=x.latitude,
            longitude=x.longitude,
        )

        x.department = analysis["department"]
        x.ai_priority_suggested = analysis["suggested_priority"]

        if analysis["duplicates"]:
            # Link to the closest existing match; staff can still see the
            # report and override this from the dashboard.
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

    return render(r, "form.html", {"form": f})


@require_GET
def ai_suggest(r):
    """Live AI preview used by the report form: as the citizen types, this
    returns a suggested category/priority/department and flags nearby
    possible duplicates — before the report is ever submitted."""

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


@login_required
def update_status(request, pk):
    if not request.user.is_staff:
        return redirect("mine")

    report = get_object_or_404(Report, pk=pk)

    if request.method == "POST":
        new_status = request.POST.get("status")
        valid_statuses = ["reported", "progress", "resolved"]

        if new_status in valid_statuses:
            report.status = new_status
            report.save()
            messages.success(
                request,
                "Report status updated successfully."
            )

    return redirect("dashboard")


@login_required
def dashboard(r):
    if not r.user.is_staff:
        return redirect("mine")

    qs = Report.objects.all().order_by("-created_at")

    c = r.GET.get("category")
    s = r.GET.get("status")
    p = r.GET.get("priority")
    q = r.GET.get("q")

    if c:
        qs = qs.filter(category=c)

    if s:
        qs = qs.filter(status=s)

    if p:
        qs = qs.filter(priority=p)

    if q:
        qs = qs.filter(title__icontains=q)

    return render(
        r,
        "dashboard.html",
        {
            "reports": qs,
            "categories": Report.CATEGORIES,
            "stats": [
                Report.objects.count(),
                Report.objects.filter(status="reported").count(),
                Report.objects.filter(status="progress").count(),
                Report.objects.filter(status="resolved").count(),
            ],
        },
    )


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

            return JsonResponse({
                "success": True,
                "address": address
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
