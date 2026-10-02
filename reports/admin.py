from django.contrib import admin
from .models import Report, Comment, Vote, Profile, StatusEvent, AIAnalysis, Notification


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "priority",
        "priority_score",
        "ai_source",
        "department",
        "state",
        "status",
        "assigned_to",
        "citizen",
        "created_at",
    )
    list_filter = ("category", "priority", "status", "department", "state")
    search_fields = ("title", "description", "address")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "user", "internal_only", "created_at")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "user", "created_at")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "role", "state", "department", "points")
    list_filter = ("role", "state")


@admin.register(StatusEvent)
class StatusEventAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "old_status", "new_status", "actor", "created_at")


@admin.register(AIAnalysis)
class AIAnalysisAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "source", "model", "latency_ms", "confidence", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "report", "read", "created_at")
