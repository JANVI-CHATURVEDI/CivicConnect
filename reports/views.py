from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings

from .models import Report, Comment, Vote
from .forms import ReportForm

import requests


def home(r):
    return render(
        r, "home.html", {"latest": Report.objects.filter(status="resolved")[:6]}
    )


@login_required
def new(r):
    f = ReportForm(r.POST or None, r.FILES or None)
    if r.method == "POST" and f.is_valid():
        x = f.save(commit=False)
        x.citizen = r.user
        x.save()
        return redirect("success", x.pk)
    return render(r, "form.html", {"form": f})


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

    if c:
        qs = qs.filter(category=c)

    if s:
        qs = qs.filter(status=s)

    if p:
        qs = qs.filter(priority=p)

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