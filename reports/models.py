from django.db import models
from django.contrib.auth.models import User


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
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"#{self.id} {self.title}"

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