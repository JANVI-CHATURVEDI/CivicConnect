from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .api import ReportViewSet, StatsView

router = DefaultRouter()
router.register(r"reports", ReportViewSet, basename="api-reports")

urlpatterns = [
    path("", views.home, name="home"),
    path("healthz", views.healthz, name="healthz"),
    path("health", views.healthz, name="health"),
    path("signup/", views.signup, name="signup"),
    path("report/new/", views.new, name="new"),
    path("reports/", views.mine, name="mine"),
    path("reports/<int:pk>/", views.detail, name="detail"),
    path("reports/<int:pk>/edit/", views.edit_report, name="edit_report"),
    path("reports/<int:pk>/delete/", views.delete_report, name="delete_report"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/export/", views.export_csv, name="export_csv"),
    path("dashboard/bulk/", views.bulk_update, name="bulk_update"),
    path("console/", views.console, name="console"),
    path("dashboard/map-data/", views.dashboard_map_data, name="dashboard_map_data"),
    path("analytics/", views.analytics, name="analytics"),
    path("transparency/", views.public_reports, name="public_reports"),
    path("api/public-map-data/", views.public_map_data, name="public_map_data"),
    path("manage-admins/", views.manage_admins, name="manage_admins"),
    path("manage-admins/<int:user_id>/demote/", views.demote_admin, name="demote_admin"),
    path("api/get-address/", views.get_address, name="get_address"),
    path("api/ai-suggest/", views.ai_suggest, name="ai_suggest"),
    path("api/assistant/", views.assistant_api, name="assistant_api"),
    path("api/briefing/", views.briefing_api, name="briefing_api"),
    path("api/ai-status/<int:pk>/", views.ai_status_api, name="ai_status_api"),
    path("api/notifications/", views.notifications_api, name="notifications_api"),
    path("api/stats/", StatsView.as_view(), name="api_stats"),
    path("api/", include(router.urls)),
    path("success/<int:pk>/", views.success, name="success"),
    path("reports/<int:pk>/comment/", views.add_comment, name="add_comment"),
    path("reports/<int:pk>/vote/", views.vote_report, name="vote_report"),
    path("reports/<int:pk>/status/", views.update_status, name="update_status"),
    path("reports/<int:pk>/assign/", views.assign_report, name="assign_report"),
    path("reports/<int:pk>/suggest-assignee/", views.suggest_assignee, name="suggest_assignee"),
    path("reports/<int:pk>/confirm/", views.confirm_report, name="confirm_report"),
    path("reports/<int:pk>/reopen/", views.reopen_report, name="reopen_report"),
    path("my-tasks/", views.my_tasks, name="my_tasks"),
    path("notifications/", views.notifications, name="notifications"),
]
