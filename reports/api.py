"""Mini REST API (DRF) with throttling."""

from rest_framework import permissions, serializers, viewsets
from rest_framework import views as drf_views
from rest_framework.response import Response

from .models import Report
from .roles import get_profile


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = [
            "id",
            "title",
            "description",
            "category",
            "priority",
            "priority_score",
            "status",
            "department",
            "state",
            "latitude",
            "longitude",
            "created_at",
        ]
        read_only_fields = ["priority", "priority_score", "status", "department"]


class ReportViewSet(viewsets.ModelViewSet):
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        u = self.request.user
        try:
            role = get_profile(u).role
        except Exception:
            role = "citizen"
        if role in ("admin", "superadmin", "officer"):
            qs = Report.objects.all()
            if role in ("admin", "officer"):
                qs = qs.filter(state=get_profile(u).state)
            return qs.order_by("-created_at")[:500]
        return Report.objects.filter(citizen=u).order_by("-created_at")[:500]

    def perform_create(self, serializer):
        from datetime import timedelta

        from django.utils import timezone

        from .ai.service import analyze_report_full
        from .constants import SLA_HOURS

        rep = serializer.save(citizen=self.request.user)
        try:
            full = analyze_report_full(rep.title, rep.description, rep.category, rep.latitude, rep.longitude)
            rep.department = full["department"]
            rep.priority = full["suggested_priority"]
            rep.priority_score = int(full["priority_score"])
            rep.priority_reasons = full["priority_reasons"]
            rep.sla_due = timezone.now() + timedelta(hours=SLA_HOURS.get(rep.priority, 120))
            rep.save()
        except Exception:
            pass


class StatsView(drf_views.APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        total = Report.objects.count()
        resolved = Report.objects.filter(status__in=("resolved", "confirmed")).count()
        return Response({"total": total, "resolved": resolved})
