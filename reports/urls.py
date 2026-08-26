from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("report/new/", views.new, name="new"),
    path("reports/", views.mine, name="mine"),
    path("reports/<int:pk>/", views.detail, name="detail"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("reports/<int:pk>/status/", views.update_status, name="update_status"),
]