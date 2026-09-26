from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Profile, Report
from .roles import get_profile
from . import ai_utils


class AiUtilsTests(TestCase):
    def test_gemini_analyze_returns_none_without_key(self):
        self.assertIsNone(ai_utils.gemini_analyze("Pothole", "Big pothole"))

    def test_rule_engine_priority_scoring(self):
        priority, hits = ai_utils.suggest_priority("Fire near electric pole", "urgent danger fire")
        self.assertEqual(priority, "high")
        self.assertTrue(hits)

    def test_vague_report_flagged(self):
        analysis = ai_utils.analyze_report(title="x", description="")
        self.assertEqual(analysis["flag"], "vague")

    def test_good_report_not_flagged(self):
        analysis = ai_utils.analyze_report(
            title="Pothole on Main Street",
            description="Deep pothole causing traffic jams every morning",
        )
        self.assertEqual(analysis["flag"], "ok")

    @patch("reports.ai_utils.requests.post")
    def test_gemini_vision_includes_image_in_payload(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{
                "text": '{"category":"road","priority":"high","department":"Roads Dept.","flag":"ok"}'
            }]}}]
        }
        mock_post.return_value = mock_response

        with patch("reports.ai_utils.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "fake-key"
            result = ai_utils.gemini_analyze(
                "Pothole", "desc", image_bytes=b"fakejpeg", image_mime_type="image/jpeg"
            )

        sent_payload = mock_post.call_args.kwargs["json"]
        parts = sent_payload["contents"][0]["parts"]
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[1]["inline_data"]["mime_type"], "image/jpeg")
        self.assertEqual(result["category"], "road")

    def test_haversine_distance_is_small_for_nearby_points(self):
        distance = ai_utils.haversine_distance_m(28.6139, 77.2090, 28.6140, 77.2091)
        self.assertLess(distance, 50)


class RoleHierarchyTests(TestCase):
    def test_superuser_auto_promoted_to_superadmin(self):
        superuser = User.objects.create_superuser("boss", "boss@example.com", "SuperPass123")
        self.assertEqual(get_profile(superuser).role, "superadmin")

    def test_regular_user_defaults_to_citizen(self):
        user = User.objects.create_user("plain", "plain@example.com", "PlainPass123")
        self.assertEqual(get_profile(user).role, "citizen")


class ReportWorkflowTests(TestCase):
    def setUp(self):
        self.citizen = User.objects.create_user("citizen1", "c1@example.com", "CitizenPass123")
        self.up_admin = User.objects.create_user("up_admin", "up@example.com", "AdminPass123", is_staff=True)
        Profile.objects.update_or_create(user=self.up_admin, defaults={"role": "admin", "state": "UP"})
        self.mh_admin = User.objects.create_user("mh_admin", "mh@example.com", "AdminPass123", is_staff=True)
        Profile.objects.update_or_create(user=self.mh_admin, defaults={"role": "admin", "state": "MH"})
        self.superadmin = User.objects.create_superuser("boss", "boss@example.com", "SuperPass123")

    def _submit_report(self, **overrides):
        data = {
            "title": "Pothole on MG Road",
            "description": "Deep pothole causing accidents near the school",
            "category": "road",
            "priority": "medium",
            "other_issue": "",
            "latitude": "26.4515",
            "longitude": "80.3080",
            "address": "MG Road",
            "state": "UP",
        }
        data.update(overrides)
        self.client.login(username="citizen1", password="CitizenPass123")
        return self.client.post("/report/new/", data)

    def test_report_submission_and_ai_enrichment(self):
        resp = self._submit_report()
        self.assertEqual(resp.status_code, 302)
        report = Report.objects.get(title="Pothole on MG Road")
        self.assertEqual(report.state, "UP")
        self.assertTrue(report.department)
        self.assertFalse(report.needs_review)

    def test_vague_report_needs_review(self):
        self._submit_report(title="x", description="", category="other", other_issue="bad")
        report = Report.objects.get(title="x")
        self.assertTrue(report.needs_review)

    def test_state_admin_only_sees_own_state(self):
        self._submit_report()
        self.client.logout()
        self.client.login(username="up_admin", password="AdminPass123")
        self.assertContains(self.client.get("/dashboard/"), "Pothole on MG Road")

        self.client.logout()
        self.client.login(username="mh_admin", password="AdminPass123")
        self.assertNotContains(self.client.get("/dashboard/"), "Pothole on MG Road")

    def test_cross_state_status_update_blocked(self):
        self._submit_report()
        report = Report.objects.get(title="Pothole on MG Road")
        self.client.logout()
        self.client.login(username="mh_admin", password="AdminPass123")
        self.client.post(f"/reports/{report.id}/status/", {"status": "progress"})
        report.refresh_from_db()
        self.assertEqual(report.status, "reported")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_status_change_sends_email_and_sets_resolved_at(self):
        self._submit_report()
        report = Report.objects.get(title="Pothole on MG Road")
        self.client.logout()
        self.client.login(username="up_admin", password="AdminPass123")

        mail.outbox = []
        self.client.post(f"/reports/{report.id}/status/", {"status": "resolved"})
        report.refresh_from_db()
        self.assertIsNotNone(report.resolved_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("c1@example.com", mail.outbox[0].to)

    def test_escalated_report_surfaced_on_dashboard(self):
        self._submit_report(title="Old dangerous manhole", category="manhole", priority="high")
        stale = Report.objects.get(title="Old dangerous manhole")
        Report.objects.filter(pk=stale.pk).update(created_at=timezone.now() - timedelta(hours=72))

        self.client.logout()
        self.client.login(username="up_admin", password="AdminPass123")
        self.assertContains(self.client.get("/dashboard/"), "Escalated")

    def test_citizen_can_edit_own_unactioned_report(self):
        self._submit_report()
        report = Report.objects.get(title="Pothole on MG Road")
        resp = self.client.post(f"/reports/{report.id}/edit/", {
            "title": "Updated pothole title", "description": "Updated description of the same issue",
            "category": "road", "priority": "high", "other_issue": "",
            "latitude": "26.4515", "longitude": "80.3080", "address": "MG Road", "state": "UP",
        })
        self.assertEqual(resp.status_code, 302)
        report.refresh_from_db()
        self.assertEqual(report.title, "Updated pothole title")

    def test_citizen_cannot_edit_actioned_report(self):
        self._submit_report()
        report = Report.objects.get(title="Pothole on MG Road")
        report.status = "progress"
        report.save()
        resp = self.client.get(f"/reports/{report.id}/edit/")
        self.assertRedirects(resp, f"/reports/{report.id}/")

    def test_citizen_can_delete_own_unactioned_report(self):
        self._submit_report()
        report = Report.objects.get(title="Pothole on MG Road")
        resp = self.client.post(f"/reports/{report.id}/delete/")
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Report.objects.filter(pk=report.id).exists())

    def test_other_citizen_cannot_edit_or_delete(self):
        self._submit_report()
        report = Report.objects.get(title="Pothole on MG Road")
        other = User.objects.create_user("other1", "o1@example.com", "OtherPass123")
        self.client.logout()
        self.client.login(username="other1", password="OtherPass123")
        self.client.post(f"/reports/{report.id}/delete/")
        self.assertTrue(Report.objects.filter(pk=report.id).exists())

    def test_manage_admins_create_and_demote(self):
        self.client.login(username="boss", password="SuperPass123")
        resp = self.client.post("/manage-admins/", {
            "username": "newadmin", "email": "na@example.com",
            "password1": "NewPass123", "password2": "NewPass123",
            "role": "admin", "state": "KL",
        })
        self.assertEqual(resp.status_code, 302)
        new_admin = User.objects.get(username="newadmin")
        self.assertEqual(get_profile(new_admin).role, "admin")

        self.client.post(f"/manage-admins/{new_admin.id}/demote/")
        self.assertEqual(get_profile(new_admin).role, "citizen")

    def test_non_superadmin_blocked_from_manage_admins(self):
        self.client.login(username="up_admin", password="AdminPass123")
        resp = self.client.get("/manage-admins/")
        self.assertEqual(resp.status_code, 302)


class PublicPagesTests(TestCase):
    def test_transparency_page_loads_without_login(self):
        resp = self.client.get("/transparency/")
        self.assertEqual(resp.status_code, 200)

    def test_public_map_data_loads_without_login(self):
        user = User.objects.create_user("citizen2", "c2@example.com", "CitizenPass123")
        Report.objects.create(
            citizen=user, title="Public one", description="desc", category="road",
            latitude=26.4, longitude=80.3, state="UP",
        )
        resp = self.client.get("/api/public-map-data/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(len(resp.json()["reports"]), 1)

    def test_analytics_requires_staff(self):
        User.objects.create_user("citizen3", "c3@example.com", "CitizenPass123")
        self.client.login(username="citizen3", password="CitizenPass123")
        resp = self.client.get("/analytics/")
        self.assertEqual(resp.status_code, 302)
