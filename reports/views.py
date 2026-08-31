
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.urls import reverse

from django.http import JsonResponse
from django.conf import settings

import requests

from .models import Report, UserProfile
from .forms import ReportForm, RegistrationForm


def home(request):
    return render(
        request,
        "home.html",
        {
            "latest": Report.objects.filter(status="resolved")[:6]
        }
    )


@login_required
def new(r):
    f = ReportForm(r.POST or None, r.FILES or None)
    if r.method == "POST" and f.is_valid():
        x = f.save(commit=False)
        x.citizen = r.user
        x.save()
        messages.success(r, "Report submitted successfully.")
        return redirect("detail", x.pk)
    return render(r, "form.html", {"form": f})


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
def dashboard(request):
    try:
        profile = request.user.userprofile
        is_authority = profile.role == "authority"
    except UserProfile.DoesNotExist:
        is_authority = False

    if not request.user.is_staff and not is_authority:
        return redirect("mine")

    qs = Report.objects.all().order_by("-created_at")

    category = request.GET.get("category")
    status = request.GET.get("status")

    if category:
        qs = qs.filter(category=category)

    if status:
        qs = qs.filter(status=status)

    return render(
        request,
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


def register(request):
    #if request.user.is_authenticated:
        #return redirect("home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()

            UserProfile.objects.get_or_create(user=user)

            messages.success(
                request,
                "Registration successful. You can now log in."
            )

            return redirect("login")
    else:
        form = RegistrationForm()

    return render(
        request,
        "register.html",
        {"form": form}
    )

@login_required
def update_status(request, pk):
    try:
        profile = request.user.userprofile
        is_authority = profile.role == "authority"
    except UserProfile.DoesNotExist:
        is_authority = False

    if not request.user.is_staff and not is_authority:
        return redirect("mine")

    report = get_object_or_404(Report, pk=pk)

    if request.method == "POST":
        status = request.POST.get("status")

        if status in ["reported", "progress", "resolved"]:
            report.status = status
            report.save()

        return redirect("dashboard")

    return redirect("dashboard")

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


class CustomLoginView(LoginView):
    template_name = "login.html"

    def get_success_url(self):
        user = self.request.user

        if user.is_staff:
            return reverse("dashboard")

        try:
            profile = user.userprofile

            if profile.role == "authority":
                return reverse("dashboard")

        except UserProfile.DoesNotExist:
            pass

        return reverse("mine")