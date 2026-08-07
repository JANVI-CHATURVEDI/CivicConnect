from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("report/new/", views.new, name="new"),
    path("reports/", views.mine, name="mine"),
    path("reports/<int:pk>/", views.detail, name="detail"),
    path("dashboard/", views.dashboard, name="dashboard"),
]
