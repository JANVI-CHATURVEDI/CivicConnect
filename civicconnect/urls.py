from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as av
from django.contrib.sitemaps import GenericSitemap
from django.contrib.sitemaps.views import sitemap as sitemap_view
from django.http import HttpResponse
from django.urls import include, path

from reports.models import Report

sitemaps = {"reports": GenericSitemap({"queryset": Report.objects.none()}, priority=0.5)}


def robots(_r):
    return HttpResponse(
        "User-agent: *\nAllow: /transparency/\nDisallow: /dashboard/\nDisallow: /reports/\n",
        content_type="text/plain",
    )


urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", av.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", av.LogoutView.as_view(), name="logout"),
    path(
        "password-reset/",
        av.PasswordResetView.as_view(template_name="registration/password_reset_form.html"),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        av.PasswordResetDoneView.as_view(template_name="registration/password_reset_done.html"),
        name="password_reset_done",
    ),
    path(
        "password-reset/confirm/<uidb64>/<token>/",
        av.PasswordResetConfirmView.as_view(template_name="registration/password_reset_confirm.html"),
        name="password_reset_confirm",
    ),
    path(
        "password-reset/complete/",
        av.PasswordResetCompleteView.as_view(template_name="registration/password_reset_complete.html"),
        name="password_reset_complete",
    ),
    path("robots.txt", robots, name="robots"),
    path("sitemap.xml", sitemap_view, {"sitemaps": sitemaps}),
    path("", include("reports.urls")),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
