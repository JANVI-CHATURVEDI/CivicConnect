from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("signup/", views.signup, name="signup"),
    path("report/new/", views.new, name="new"),
    path("reports/", views.mine, name="mine"),
    path("reports/<int:pk>/", views.detail, name="detail"),
    path("dashboard/", views.dashboard, name="dashboard"),
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
