from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("report/new/", views.new, name="new"),
    path("reports/", views.mine, name="mine"),
    path("reports/<int:pk>/", views.detail, name="detail"),
    path("reports/<int:pk>/edit/", views.edit_report, name="edit_report"),
    path("reports/<int:pk>/delete/", views.delete_report, name="delete_report"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/map-data/", views.dashboard_map_data, name="dashboard_map_data"),
    path("analytics/", views.analytics, name="analytics"),
    path("transparency/", views.public_reports, name="public_reports"),
    path("api/public-map-data/", views.public_map_data, name="public_map_data"),
    path("manage-admins/", views.manage_admins, name="manage_admins"),
    path("manage-admins/<int:user_id>/demote/", views.demote_admin, name="demote_admin"),

    path("api/get-address/", views.get_address, name="get_address"),
    path("api/ai-suggest/", views.ai_suggest, name="ai_suggest"),
    path("success/<int:pk>/", views.success, name="success"),

    path(
        "reports/<int:pk>/comment/",
        views.add_comment,
        name="add_comment"
    ),

    path(
        "reports/<int:pk>/vote/",
        views.vote_report,
        name="vote_report"
    ),

    path(
        "reports/<int:pk>/status/",
        views.update_status,
        name="update_status"
    ),
]
