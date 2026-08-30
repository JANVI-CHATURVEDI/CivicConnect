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

## Still not implemented (documented honestly for your report)

- Real image-based AI (the "photo → auto description/category" features are
  text-based only; no computer vision model is used).
- Google OAuth login (button shows a clear "not enabled" message instead of pretending to work).
- Editing/deleting a report after submission.
- Automated test suite beyond `smoke_test.py` (a manual end-to-end script — not wired into `manage.py test`).

## Project structure

```
civicconnect/       - Django project settings/urls
reports/            - main app: models, views, forms, urls, admin, ai_utils.py
templates/          - all HTML templates
static/             - CSS/JS/images
smoke_test.py       - manual end-to-end script exercising signup, report
                      creation, AI enrichment, and duplicate detection
```
