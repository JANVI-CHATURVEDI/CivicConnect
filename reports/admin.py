from django.contrib import admin
from .models import Report, Comment, Vote, Profile


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "priority",
        "ai_priority_suggested",
        "ai_source",
        "department",
        "state",
        "status",
        "duplicate_of",
        "citizen",
        "created_at",
    )
    list_filter = ("category", "priority", "status", "department", "state")
    search_fields = ("title", "description", "address")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "user", "created_at")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "user", "created_at")


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "role", "state")
    list_filter = ("role", "state")
