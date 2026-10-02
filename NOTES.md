# NOTES — assumptions & decisions

- GEMINI_API_KEY provided by user saved to local `.env` only (gitignored via `.env`). Verified live 2026-10-02: key authenticates, `gemini-2.0-flash` is retired (404) so default model is now `gemini-2.5-flash` (confirmed 200 end-to-end). Tests force `GEMINI_API_KEY=''` via override_settings so the suite stays offline/fast.
- `DATABASE_URL` in `.env` points to remote Neon Postgres with committed credentials. Tests force SQLite via `DATABASE_URL=sqlite:///...` env override (dotenv does not override pre-existing env). Production compose uses Postgres service.
- Orphan apps (`users/`, `notifications/`, `departments/`, `ai_integration/`) exist only as `__pycache__`; not in INSTALLED_APPS. Left untouched; stale tables in db.sqlite3 ignored. Removed pycache not required.
- No django-ratelimit / whitenoise / gunicorn installed. Implemented cache-based rate limiting (no new dep) and optional whitenoise (added to requirements, middleware auto-enabled only if installed).
- DRF is installed (3.18) so mini-API uses DRF + throttles.
- Role `officer` added; existing `admin` = State Admin, `superadmin` unchanged. Officers scoped to state+department.
- Lifecycle extended but backwards-compatible: old statuses `reported/progress/resolved` retained; new `acknowledged/assigned/confirmed/reopened` added as choices (old rows unaffected).
- Priority `critical` added; old rows unaffected.
- CSS: single `design-system.css` tokens + components; old files kept and imported to avoid breaking templates, dark mode covers all pages via `[data-theme]`.
- Google login button removed (no allauth creds); documented in README limitations.
- Seed images: procedural Pillow placeholders (no external assets), deterministic via `--seed`.
