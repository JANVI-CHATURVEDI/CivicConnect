from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Report
from .forms import ReportForm, RegistrationForm


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
def dashboard(r):
    if not r.user.is_staff:
        return redirect("mine")
    qs = Report.objects.all().order_by("-created_at")
    c = r.GET.get("category")
    s = r.GET.get("status")
    if c:
        qs = qs.filter(category=c)
    if s:
        qs = qs.filter(status=s)
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

def register(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()

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
def update_status(r, pk):
    if not r.user.is_staff:
        return redirect("mine")

    x = get_object_or_404(Report, pk=pk)

    if r.method == "POST":
        status = r.POST.get("status")

        if status in ["reported", "progress", "resolved"]:
            x.status = status
            x.save()

        return redirect("dashboard")

    return redirect("dashboard")