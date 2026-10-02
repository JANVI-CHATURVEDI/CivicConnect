from django.db import models
from django.contrib.auth.models import User
from .constants import STATES, ROLES


class Report(models.Model):
    CATEGORIES = [
        ("road", "Road Damage"),
        ("water", "Water Leakage"),
        ("garbage", "Garbage Overflow"),
        ("light", "Broken Streetlight"),
        ("tree", "Fallen Tree"),
        ("manhole", "Open Manhole"),
        ("traffic", "Traffic Signal"),
        ("other", "Other Hazard"),
    ]
    STATUS = [
        ("reported", "Reported"),
        ("acknowledged", "Acknowledged"),
        ("assigned", "Assigned"),
        ("progress", "In Progress"),
        ("resolved", "Resolved"),
        ("confirmed", "Citizen Confirmed"),
        ("reopened", "Reopened"),
    ]
    PRIORITY = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    citizen = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORIES)
    priority = models.CharField(max_length=10, choices=PRIORITY, default="medium")
    priority_score = models.PositiveSmallIntegerField(default=50)
    priority_reasons = models.JSONField(default=list, blank=True)
    status = models.CharField(max_length=14, choices=STATUS, default="reported")
    image = models.ImageField(upload_to="reports/", blank=True, null=True)
    image_thumb = models.ImageField(upload_to="reports/thumbs/", blank=True, null=True)
    resolution_image = models.ImageField(upload_to="reports/resolved/", blank=True, null=True)
    latitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=30, choices=STATES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    sla_due = models.DateTimeField(null=True, blank=True)

    department = models.CharField(max_length=80, blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_reports")
    ai_priority_suggested = models.CharField(max_length=10, blank=True)
    ai_source = models.CharField(max_length=10, blank=True)
    needs_review = models.BooleanField(default=False)
    flag_reason = models.CharField(max_length=120, blank=True)
    duplicate_of = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="duplicates")
    action_brief = models.TextField(blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    rating_feedback = models.TextField(blank=True)
    civic_points = models.PositiveIntegerField(default=0)
    display_name_public = models.CharField(max_length=60, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["status"]),
            models.Index(fields=["priority"]),
            models.Index(fields=["state"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["category"]),
            models.Index(fields=["latitude", "longitude"]),
            models.Index(fields=["assigned_to", "status"]),
        ]

    def __str__(self):
        return f"#{self.id} {self.title}"

    @property
    def is_overdue(self):
        from django.utils import timezone
        return bool(self.sla_due and self.status not in ("resolved", "confirmed") and timezone.now() > self.sla_due)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=12, choices=ROLES, default="citizen")
    state = models.CharField(max_length=30, choices=STATES, blank=True)
    department = models.CharField(max_length=80, blank=True)
    points = models.PositiveIntegerField(default=0)
    badges = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Comment(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    internal_only = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on Report #{self.report.id}"


class Vote(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["report", "user"], name="unique_report_vote")]

    def __str__(self):
        return f"{self.user.username} voted for Report #{self.report.id}"


class StatusEvent(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="timeline")
    old_status = models.CharField(max_length=14, blank=True)
    new_status = models.CharField(max_length=14)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"#{self.report_id} {self.old_status}->{self.new_status}"


class AIAnalysis(models.Model):
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="analyses", null=True, blank=True)
    content_hash = models.CharField(max_length=64, blank=True, db_index=True)
    source = models.CharField(max_length=10, default="rules")
    model = models.CharField(max_length=80, blank=True)
    latency_ms = models.PositiveIntegerField(default=0)
    confidence = models.FloatField(default=0.0)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"AIAnalysis {self.id} ({self.source})"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    report = models.ForeignKey(Report, on_delete=models.CASCADE, null=True, blank=True)
    message = models.CharField(max_length=255)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notif for {self.user.username}: {self.message[:40]}"
