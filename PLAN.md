# PLAN — CivicConnect AI Production MVP

## Phase 0 — Security & correctness (KNOWN PROBLEMS 1-13)
Files: `civicconnect/settings.py`, `reports/views.py`, `reports/urls.py`, `reports/ai_utils.py` → `reports/ai/`, `reports/models.py`, `reports/forms.py`, `reports/roles.py`, `reports/context_processors.py`, `templates/home.html`, `templates/*.html`, `static/*.css`
- POST-only vote/comment with visibility checks; central `permissions.py`
- State-admin scoping on detail/success; officer scope
- ai-suggest: login + cache + rate-limit (cache-based, no new dep) + content-hash cache
- Gemini: header key, GEMINI_MODEL env, structured JSON, retry/backoff, timeout
- settings hardening, logging, CSRF, secure cookies, STATIC_ROOT, fail-loud SECRET
- Upload validation: size, Pillow verify, EXIF strip + GPS hint, thumbnail, reject non-image
- Profile: post_save signal + request cache, remove per-request get_or_create
- Duplicates: bbox prefilter + indexes
- Dashboard: pagination, select_related/prefetch, annotated votes
- Typography: min 14px, contrast, single design system `design-system.css`
- Home stats: real DB aggregates
- Google button: remove (documented, no creds) — hidden behind env flag
- CSS consolidation

## Phase 1 — AI Core (`reports/ai/` package)
- `reports/ai/{__init__,base,rule_engine,gemini_client,scoring,duplicates,service}.py`
- `AIAnalysis` model: report FK, source, model, latency_ms, confidence, payload JSON, created_at
- Vision: extend gemini prompt for hazards/severity/caption/match; rule fallback (no vision)
- Text: lang detect (heuristic hi/hinglish/en), urgency, spam/vague
- Priority Score 0-100 → Low/Med/High/Critical; explanation list; store on Report + AIAnalysis
- Semantic duplicates: TF-IDF-ish token overlap + location + category; Gemini embeddings stub if key
- Draft-for-officer brief, before/after verify stub, async via ThreadPool + `AI_PENDING` + polling endpoint
- CivicBot widget: DB-grounded Q&A endpoint `/api/assistant/`
- Voice: Web Speech button in form (progressive enhancement)
- Daily briefing: `/api/briefing/` + dashboard card (rule-generated, Gemini-polished if key)
- Keep `reports/ai_utils.py` as thin shim for backwards-compat + tests

## Phase 2 — Roles & workflows
- New role `officer` (dept + state); `StatusEvent`, `Notification`, `Department`, extended Report (assigned_to, sla_due, priority_score, critical, rating, anon display, resolution photo)
- Lifecycle: reported→acknowledged→assigned→progress→resolved→confirmed/reopened
- Permissions helper `reports/permissions.py` + mixins; tests for matrix
- State admin: assign, SLA per priority, bulk, internal notes, CSV, escalate
- Officer My Tasks, SuperAdmin console/leaderboard/health, Citizen profile/ratings/points/bell
- SLA countdown/overdue, extend escalate command

## Phase 3 — UI/UX
- `static/css/design-system.css` tokens, components, dark mode; remove inline styles gradually
- Landing: real stats, live ticker, how-AI, resolved stories w/ before-after
- Form: 4-step wizard + draft localStorage + vision feedback stub + duplicate card + map picker
- Dashboards: KPI+sparklines, kanban+table toggle, heatmap/cluster, Ctrl+K palette, briefing card
- Detail: overlay chips, before/after slider, timeline, gauge, share/QR
- Transparency: no PII, stats
- PWA manifest+SW, bottom tab bar, i18n stub, a11y, Lighthouse perf (lazy imgs, preload fonts)

## Phase 4 — Prod readiness
- whitenoise, gunicorn, Dockerfile, compose, /healthz, logging, Sentry opt, security headers
- DRF mini-API + throttles + OpenAPI doc page
- 400/403/404/500, sitemap, robots, OG tags
- ruff + GH Actions + Makefile + pinned requirements + .env.example + run scripts
- 40+ tests

## Phase 5 — Seed
- Deterministic `--seed/--count/--reset`, 12 cities, officers, citizens w/ points, 90-day spread, Hindi/Hinglish, timelines, ratings, AIAnalysis precomputed, Pillow placeholder + after images, 3 hero reports
