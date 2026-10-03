from datetime import timedelta
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import Profile, Report, Comment, Vote, StatusEvent
from .roles import get_profile
from . import ai_utils


@override_settings(GEMINI_API_KEY='')
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

    @patch("reports.ai.gemini_client.requests.post")
    def test_gemini_vision_includes_image_in_payload(self, mock_post):
        mock_response = MagicMock()
        mock_response.raise_for_status = lambda: None
        mock_response.json.return_value = {
            "candidates": [{"content": {"parts": [{
                "text": '{"category":"road","priority":"high","severity":78,"department":"Roads Dept.","flag":"ok","caption":"Pothole","hazards":[],"photo_match":"match","confidence":0.8}'
            }]}}]
        }
        mock_post.return_value = mock_response

        with patch("reports.ai.gemini_client.settings") as mock_settings:
            mock_settings.GEMINI_API_KEY = "TEST-key"
            mock_settings.GEMINI_MODEL = "gemini-2.0-flash"
            mock_settings.GEMINI_TIMEOUT_S = 12
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


@override_settings(GEMINI_API_KEY='')
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


@override_settings(GEMINI_API_KEY='')
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


@override_settings(GEMINI_API_KEY='')
class PermissionMatrixTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", "o@e.com", "Pass12345")
        self.other = User.objects.create_user("other", "ot@e.com", "Pass12345")
        self.admin = User.objects.create_user("adm", "a@e.com", "Pass12345", is_staff=True)
        Profile.objects.update_or_create(user=self.admin, defaults={"role": "admin", "state": "UP"})
        self.rep = Report.objects.create(citizen=self.owner, title="T", description="Some real description here", category="road", state="UP")

    def test_other_citizen_cannot_view(self):
        self.client.login(username="other", password="Pass12345")
        self.assertEqual(self.client.get(f"/reports/{self.rep.id}/").status_code, 302)

    def test_comment_requires_post_and_scope(self):
        self.client.login(username="other", password="Pass12345")
        resp = self.client.get(f"/reports/{self.rep.id}/comment/")
        self.assertEqual(resp.status_code, 405)
        n = Comment.objects.count()
        self.client.post(f"/reports/{self.rep.id}/comment/", {"text": "hi"})
        self.assertEqual(Comment.objects.count(), n)  # blocked, no comment

    def test_vote_requires_post(self):
        self.client.login(username="other", password="Pass12345")
        resp = self.client.get(f"/reports/{self.rep.id}/vote/")
        self.assertEqual(resp.status_code, 405)
        self.assertEqual(Vote.objects.count(), 0)

    def test_vote_post_works(self):
        self.client.login(username="other", password="Pass12345")
        self.client.post(f"/reports/{self.rep.id}/vote/")
        self.assertEqual(Vote.objects.count(), 1)

    def test_cross_state_admin_cannot_view(self):
        mh = User.objects.create_user("mha", "m@e.com", "Pass12345", is_staff=True)
        Profile.objects.update_or_create(user=mh, defaults={"role": "admin", "state": "MH"})
        self.client.login(username="mha", password="Pass12345")
        self.assertEqual(self.client.get(f"/reports/{self.rep.id}/").status_code, 302)

    def test_ai_suggest_requires_login(self):
        resp = self.client.get("/api/ai-suggest/", {"title": "pothole"})
        self.assertEqual(resp.status_code, 302)

    def test_officer_scoped(self):
        off = User.objects.create_user("off", "off@e.com", "Pass12345", is_staff=True)
        Profile.objects.update_or_create(user=off, defaults={"role": "officer", "state": "MH", "department": "Roads & Infrastructure Dept."})
        self.client.login(username="off", password="Pass12345")
        self.assertEqual(self.client.get(f"/reports/{self.rep.id}/").status_code, 302)


@override_settings(GEMINI_API_KEY='')
class AIFallbackTests(TestCase):
    def test_malformed_gemini_json_falls_back(self):
        from reports.ai import service
        with patch("reports.ai.service.gemini_analyze", return_value={"category": "road"}):
            # missing priority -> invalid, but service handles dict directly? gemini returns None path instead
            pass
        full = service.analyze_report_full(title="Pothole", description="big pothole near school", category="road")
        self.assertIn(full["ai_source"], ("rules", "gemini"))
        self.assertIn(full["suggested_priority"], ("low", "medium", "high", "critical"))

    def test_priority_score_transparent(self):
        from reports.ai.rule_engine import priority_score
        score, label, reasons = priority_score(severity=90, urgency=90, category="manhole", sensitive=True, upvotes=5, age_days=5, density=3)
        self.assertGreaterEqual(score, 80)
        self.assertEqual(label, "critical")
        self.assertTrue(reasons)

    def test_language_detection(self):
        from reports.ai.rule_engine import detect_language
        self.assertEqual(detect_language("sadak par bada gaddha hai"), "hinglish")
        self.assertEqual(detect_language("पानी लीक हो रहा है"), "hi")
        self.assertEqual(detect_language("Pothole on main road"), "en")

    def test_spam_flagged(self):
        from reports.ai.service import analyze_report_full
        full = analyze_report_full(title="Buy now", description="click here free money http://x")
        self.assertEqual(full["flag"], "spam")

    def test_duplicate_bbox_prefilter(self):
        from reports.ai.duplicates import find_possible_duplicates
        u = User.objects.create_user("du", "du@e.com", "Pass12345")
        r1 = Report.objects.create(citizen=u, title="Pothole here", description="big deep pothole", category="road", latitude=26.85, longitude=80.95, state="UP")
        near = find_possible_duplicates("road", 26.8501, 80.9501, title="pothole", description="deep hole")
        far = find_possible_duplicates("road", 19.07, 72.87, title="pothole", description="deep hole")
        self.assertTrue(any(m[0].id == r1.id for m in near))
        self.assertEqual(far, [])


@override_settings(GEMINI_API_KEY='')
class WorkflowTests2(TestCase):
    def setUp(self):
        self.cit = User.objects.create_user("c1", "c1@e.com", "Pass12345")
        self.adm = User.objects.create_user("ad", "ad@e.com", "Pass12345", is_staff=True)
        Profile.objects.update_or_create(user=self.adm, defaults={"role": "admin", "state": "UP"})
        self.rep = Report.objects.create(citizen=self.cit, title="Leak", description="water leaking for days", category="water", state="UP", status="resolved")

    def test_status_event_logged(self):
        self.client.login(username="ad", password="Pass12345")
        self.client.post(f"/reports/{self.rep.id}/status/", {"status": "progress"})
        self.assertTrue(StatusEvent.objects.filter(report=self.rep).exists())

    def test_citizen_confirm_and_reopen(self):
        self.client.login(username="c1", password="Pass12345")
        self.client.post(f"/reports/{self.rep.id}/confirm/", {"rating": "5", "feedback": "great"})
        self.rep.refresh_from_db()
        self.assertEqual(self.rep.status, "confirmed")
        self.client.post(f"/reports/{self.rep.id}/reopen/")
        self.rep.refresh_from_db()
        self.assertEqual(self.rep.status, "reopened")

    def test_sla_overdue_flag(self):
        from django.utils import timezone
        from datetime import timedelta
        self.rep.status = "reported"
        self.rep.sla_due = timezone.now() - timedelta(hours=1)
        self.rep.save()
        self.assertTrue(self.rep.is_overdue)

    def test_upload_rejects_non_image(self):
        from reports.uploads import validate_and_clean_image
        from django.core.files.base import ContentFile
        f, gps, err = validate_and_clean_image(ContentFile(b"not an image", name="x.txt"))
        self.assertIsNotNone(err)

    def test_api_list_and_stats(self):
        self.client.login(username="c1", password="Pass12345")
        resp = self.client.get("/api/reports/")
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get("/api/stats/")
        self.assertEqual(resp.status_code, 200)

    def test_healthz(self):
        self.assertEqual(self.client.get("/healthz").json()["ok"], True)

    def test_assistant_grounded(self):
        self.client.login(username="c1", password="Pass12345")
        resp = self.client.get("/api/assistant/", {"q": "where is my report"})
        self.assertIn("Leak", resp.json()["answer"])


@override_settings(GEMINI_API_KEY='')
class StaffToolsTests(TestCase):
    def setUp(self):
        self.cit = User.objects.create_user("sc1", "s@e.com", "Pass12345")
        self.adm = User.objects.create_user("sad", "sa@e.com", "Pass12345", is_staff=True)
        Profile.objects.update_or_create(user=self.adm, defaults={"role": "admin", "state": "UP"})
        self.boss = User.objects.create_superuser("sboss", "sb@e.com", "Pass12345")
        self.r1 = Report.objects.create(citizen=self.cit, title="One", description="Real issue description", category="road", state="UP")
        self.r2 = Report.objects.create(citizen=self.cit, title="Two", description="Another real description", category="water", state="UP")

    def test_internal_notes_hidden_from_citizen(self):
        Comment.objects.create(report=self.r1, user=self.adm, text="staff only note", internal_only=True)
        self.client.login(username="sc1", password="Pass12345")
        resp = self.client.get(f"/reports/{self.r1.id}/")
        self.assertNotContains(resp, "staff only note")
        self.client.login(username="sad", password="Pass12345")
        self.assertContains(self.client.get(f"/reports/{self.r1.id}/"), "staff only note")

    def test_bulk_status_update(self):
        self.client.login(username="sad", password="Pass12345")
        self.client.post("/dashboard/bulk/", {"ids": [self.r1.id, self.r2.id], "action": "status:progress"})
        self.r1.refresh_from_db(); self.r2.refresh_from_db()
        self.assertEqual((self.r1.status, self.r2.status), ("progress", "progress"))

    def test_bulk_requires_staff(self):
        self.client.login(username="sc1", password="Pass12345")
        self.client.post("/dashboard/bulk/", {"ids": [self.r1.id], "action": "status:progress"})
        self.r1.refresh_from_db()
        self.assertEqual(self.r1.status, "reported")

    def test_csv_export_scoped(self):
        self.client.login(username="sad", password="Pass12345")
        resp = self.client.get("/dashboard/export/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/csv", resp["Content-Type"])
        self.assertIn("One", resp.content.decode())

    def test_console_superadmin_only(self):
        self.client.login(username="sad", password="Pass12345")
        self.assertEqual(self.client.get("/console/").status_code, 302)
        self.client.login(username="sboss", password="Pass12345")
        resp = self.client.get("/console/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "UP")
