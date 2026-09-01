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
        ("progress", "In Progress"),
        ("resolved", "Resolved"),
    ]
    citizen = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=160)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORIES)
    priority = models.CharField(
        max_length=10,
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
    )
    status = models.CharField(max_length=12, choices=STATUS, default="reported")
    image = models.ImageField(upload_to="reports/", blank=True, null=True)
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, blank=True, null=True
    )
    address = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=30, choices=STATES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    department = models.CharField(max_length=80, blank=True)
    ai_priority_suggested = models.CharField(
        max_length=10,
        choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
        blank=True,
    )
    ai_source = models.CharField(max_length=10, blank=True)
    duplicate_of = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="duplicates",
    )

    def __str__(self):
        return f"#{self.id} {self.title}"


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=12, choices=ROLES, default="citizen")
    state = models.CharField(max_length=30, choices=STATES, blank=True)

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class Comment(models.Model):
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="comments"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comment by {self.user.username} on Report #{self.report.id}"


class Vote(models.Model):
    report = models.ForeignKey(
        Report,
        on_delete=models.CASCADE,
        related_name="votes"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["report", "user"],
                name="unique_report_vote"
            )
        ]

    def __str__(self):
        return f"{self.user.username} voted for Report #{self.report.id}"
