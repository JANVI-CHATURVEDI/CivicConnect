from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="home"),
<<<<<<< HEAD
    path("register/", views.register, name="register"),
=======
    path("signup/", views.signup, name="signup"),
>>>>>>> origin/main
    path("report/new/", views.new, name="new"),
    path("reports/", views.mine, name="mine"),
    path("reports/<int:pk>/", views.detail, name="detail"),
    path("dashboard/", views.dashboard, name="dashboard"),

<<<<<<< HEAD
    path("reports/<int:pk>/status/", views.update_status, name="update_status"),
    path("api/get-address/", views.get_address, name="get_address"),
  ]
=======
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
>>>>>>> origin/main
