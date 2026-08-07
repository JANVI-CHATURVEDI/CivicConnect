from django.contrib import admin
from django.contrib.auth import views as av
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", av.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", av.LogoutView.as_view(), name="logout"),
    path("", include("reports.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
