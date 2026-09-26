# CivicConnect AI

A Django-based civic issue reporting platform with a lightweight, rule-based
"AI" layer for issue triage.

## What's new / fixed in this build

**Bugs fixed:**
- Report form's priority radio buttons had duplicated/malformed `<input>` tags — rebuilt cleanly.
- Text typed into the "Other Issue" box was being silently discarded — now saved to the report properly (with a real, validated form field).
- Global Django messages were rendered twice in `base.html` — deduplicated.
- Duplicate `/api/get-address/` URL entry removed.
- Missing `dashboard_extra.css` (referenced but never created) — added.
- Cleaned up duplicated paragraphs/SVGs left over from copy-paste in `home.html`.

**New features:**
- **User registration** (`/signup/`) — previously just a JS `alert()`.
- **Real password reset** (`/password-reset/`) using Django's built-in views — emails print to the console in dev (see `EMAIL_BACKEND` in settings). Previously just a JS `alert()`.
- **AI features** — see below.
- **SQLite fallback** — the app now runs immediately with `python manage.py migrate` and no Postgres setup. Set `POSTGRES_DB` etc. in `.env` to use Postgres instead (original behavior).
- Dashboard search box (`?q=`) alongside the existing category/status/priority filters.

## Role hierarchy

Three roles now exist, driven by a `Profile` model (`role` + `state`):

| Role | Scope | How it's granted |
|---|---|---|
| **Citizen** | Own reports only | Default for anyone who signs up |
| **State Admin** | Reports from their assigned state only | Created by a Super Admin via `/manage-admins/` |
| **Super Admin** | Every report, every state | `python manage.py createsuperuser` auto-grants this; can also be granted via `/manage-admins/` |

Citizens pick their state when submitting a report (auto-filled from
reverse geocoding when available, editable otherwise). State Admins only
see and can update reports tagged with their own state; Super Admins see
everything and can filter by state, plus manage who has admin access at
`/manage-admins/`.

## Gemini AI integration

Set `GEMINI_API_KEY` in `.env` (get one free at
https://aistudio.google.com/apikey) and report triage — category,
priority, and department — is handled by Gemini instead of the rule
engine. If the key is missing, the request fails, or Gemini's response
doesn't parse cleanly, `analyze_report()` automatically falls back to the
rule-based engine described below — the app never breaks either way. The
live suggestion panel on the report form shows which one produced the
result ("via Gemini AI" vs "via rule engine").

## Hackathon-grade additions

- **Interactive map** — every dashboard and the public transparency page shows reports as color-coded pins on a Leaflet/OpenStreetMap map (no API key needed, free tile server).
- **Gemini Vision** — when a citizen uploads a photo, it's sent to Gemini alongside the text so category/priority/department can be informed by the image itself, not just the description. Falls back to text-only Gemini or the rule engine if no photo, no key, or the call fails.
- **AI quality flagging** — Gemini (or a length-based rule fallback) marks vague/spam-looking reports with a `needs_review` flag, surfaced as a badge on the dashboard rather than silently rejecting anything.
- **Public transparency page** (`/transparency/`) — an unauthenticated map of all reports nationwide, filterable by state/category, with no citizen-identifying information exposed.
- **Analytics** (`/analytics/`) — Chart.js dashboards: reports by category/status/state, a 30-day trend line, and average resolution time (using a new `resolved_at` timestamp set automatically when a report moves to "Resolved" and cleared if it's reopened).
- **Status-change email notifications** — citizens get emailed (via the same console/SMTP backend already configured) whenever their report's status changes.
- **Stale high-priority escalation** — a high-priority report still sitting in "Reported" after 48 hours is automatically flagged and surfaced at the top of the admin's attention (computed live on each dashboard load, not a background job — see caveat below).

## The "AI" features — how they actually work

This project advertises AI-powered issue detection, severity analysis,
duplicate detection, and department routing. All of it is implemented in
`reports/ai_utils.py` as **transparent, rule-based logic** rather than a
black-box ML model:

| Feature | How it works |
|---|---|
| **Issue detection** | Keyword matching against the report's title/description suggests a category (e.g. "pothole", "leak", "manhole"). |
| **Severity analysis** | A curated list of urgency keywords ("danger", "fire", "injury", "blocking road", etc.) plus category risk-weighting produces a low/medium/high priority suggestion. |
| **Duplicate detection** | The Haversine formula computes real distance between reports; two reports of the same category within 150m and 14 days are automatically linked. |
| **Department routing** | A category → department lookup table auto-assigns every report to a responsible department. |
| **Live AI panel** | While filling the report form, `/api/ai-suggest/` is called (debounced) as the citizen types, showing suggestions *before* submission. |

This design was a deliberate choice for a college project: it runs
instantly and offline with zero extra dependencies or API keys (important
if your demo doesn't have reliable internet), and every decision is fully
explainable in a viva — you can point to the exact keyword or distance
threshold that triggered it. `analyze_report()` in `ai_utils.py` is the
single entry point; swap its internals for a real model (e.g. an image
classifier, or a call to an LLM API) later without touching any other file.

## Setup

```bash
python -m venv venv
source venv/bin/activate        # venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env            # optional: add a Geoapify key for reverse geocoding
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then visit `http://127.0.0.1:8000/`.

- Sign up as a normal citizen at `/signup/`.
- Log in as the superuser you created to access `/dashboard/` (staff-only).

## UI overhaul

- **Dark mode** — a toggle in the nav (and on the homepage) switches the whole site between light/dark, persisted in `localStorage`. Applied consistently across every page, including login/signup.
- Refined buttons with a subtle animated sheen on hover, consistent card hover-lift on dashboard/analytics/admin cards, a sticky blurred navbar, and a redesigned "AI Suggestion" panel on the report form with an animated gradient border.
- Nicer empty states (icon in a soft circle instead of a bare outline icon).

## Report editing and deletion

Citizens can edit or delete their own report from its detail page, but only while it's still in the "Reported" state (once staff start working on it, it's locked to preserve the audit trail). Editing re-runs the full AI analysis in case the new title/description/photo changes the right category, priority, or department.

## Escalation, for real this time

`python manage.py escalate_stale_reports` finds every high-priority report still "Reported" after 48 hours and emails a digest to the relevant state admin(s) and all superadmins. It's not a background job — run it on a schedule yourself (cron on Linux/Mac, Task Scheduler on Windows) since this project has no Celery/job-runner setup. Example cron line to run it hourly:
```
0 * * * * cd /path/to/project && /path/to/venv/bin/python manage.py escalate_stale_reports
```

## Tests

`python manage.py test` now runs a real, committed suite (`reports/tests.py`, 23 tests) covering the AI utilities, role hierarchy, the full report workflow, edit/delete permissions, and the public pages. This replaces the old manual `smoke_test.py` script from earlier iterations.

## Still not implemented (documented honestly for your report)

- Google OAuth login (button shows a clear "not enabled" message instead of pretending to work).
- True background-job escalation: `escalate_stale_reports` must be scheduled externally (cron/Task Scheduler) — nothing runs it automatically on its own.
- Gemini Vision has been tested end-to-end with a mocked API response (confirmed the image is correctly attached to the request), but not against Gemini's real servers, since this environment can't reach `generativelanguage.googleapis.com` — verify with a real `GEMINI_API_KEY` locally.

## Project structure

```
civicconnect/       - Django project settings/urls
reports/            - main app: models, views, forms, urls, admin, ai_utils.py
templates/          - all HTML templates
static/             - CSS/JS/images
smoke_test.py       - manual end-to-end script exercising signup, report
                      creation, AI enrichment, and duplicate detection
```
