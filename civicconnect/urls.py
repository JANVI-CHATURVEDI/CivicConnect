from django.contrib import admin
from django.contrib.auth import views as av
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from reports import views


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "login/",
        views.CustomLoginView.as_view(),
        name="login",
    ),

    path(
        "logout/",
        av.LogoutView.as_view(),
        name="logout",
    ),

    path(
        "password-reset/",
        av.PasswordResetView.as_view(
            template_name="registration/password_reset_form.html"
        ),
        name="password_reset",
    ),

    path(
        "password-reset/done/",
        av.PasswordResetDoneView.as_view(
            template_name="registration/password_reset_done.html"
        ),
        name="password_reset_done",
    ),

    path(
        "password-reset/confirm/<uidb64>/<token>/",
        av.PasswordResetConfirmView.as_view(
            template_name="registration/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),

    path(
        "password-reset/complete/",
        av.PasswordResetCompleteView.as_view(
            template_name="registration/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    path("", include("reports.urls")),
]


urlpatterns += static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)