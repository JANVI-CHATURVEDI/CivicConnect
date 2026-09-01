from django.contrib import admin
from .models import Report, Comment, Vote


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "category",
        "priority",
        "ai_priority_suggested",
        "department",
        "status",
        "duplicate_of",
        "citizen",
        "created_at",
    )
    list_filter = ("category", "priority", "status", "department")
    search_fields = ("title", "description", "address")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "user", "created_at")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("id", "report", "user", "created_at")
