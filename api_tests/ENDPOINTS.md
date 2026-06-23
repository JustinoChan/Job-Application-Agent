# Job Application Agent — API Endpoint Reference

Base URL (live): `https://api.h4s.live`

Path prefixes stack:  router prefix + app prefix `/api`.
e.g. router `/applications` route `/` ->  real path `/api/applications/`

Auth: every route under `/api` is behind `Depends(verify_request)`.
  - Send `Authorization: Bearer <API_TOKEN>` (or `?token=<API_TOKEN>` for GETs).
  - Missing/invalid token -> 401  `{"detail": "Unauthorized"}`.
  - `/health` is the only public (no-auth) route.

Legend:  ✅ read-only & safe to test live | ⚠️ writes data | 🚫 destructive (never test live)

---

## Public (no auth)

| Method | Path      | Returns                | Notes |
|--------|-----------|------------------------|-------|
| GET    | `/health` | `{"status": "ok"}`     | ✅ liveness check |

---

## Dashboard  (`/api/dashboard`)

| Method | Path                  | Notes |
|--------|-----------------------|-------|
| GET    | `/api/dashboard/stats`| ✅ totals, status_counts, response_rate, interview_rate, offer_rate, response_count, average_source_quality |

---

## Applications  (`/api/applications`)

### Reads (safe)

| Method | Path                                              | Notes |
|--------|---------------------------------------------------|-------|
| GET    | `/api/applications/`                              | ✅ list all (query: `status`, `include_archived`) |
| GET    | `/api/applications/{job_id}`                      | ✅ one entry — 404 if missing |
| GET    | `/api/applications/search?q=<>=2 chars>`          | ✅ substring search (q < 2 chars -> 422) |
| GET    | `/api/applications/openclaw-status`               | ✅ is OpenClaw available |
| GET    | `/api/applications/{job_id}/raw`                  | ✅ raw posting text (404 if none) |
| GET    | `/api/applications/{job_id}/analysis`             | ✅ recomputed fit breakdown |
| GET    | `/api/applications/{job_id}/resume/{version}`     | ✅ resume markdown |
| GET    | `/api/applications/{job_id}/resume/{version}/html`| ✅ resume HTML |
| GET    | `/api/applications/{job_id}/resume/{version}/pdf` | ✅ resume PDF |
| GET    | `/api/applications/{job_id}/audit/{version}`      | ✅ audit report JSON |
| GET    | `/api/applications/{job_id}/cover-letters`        | ✅ list cover-letter versions |
| GET    | `/api/applications/{job_id}/cover-letter/{version}`| ✅ cover letter markdown |
| GET    | `/api/applications/{job_id}/cover-letter/{version}/html`  | ✅ cover letter HTML |
| GET    | `/api/applications/{job_id}/cover-letter/{version}/pdf`   | ✅ cover letter PDF |
| GET    | `/api/applications/{job_id}/cover-letter/{version}/audit` | ✅ cover letter audit JSON |

### Writes (⚠️ do NOT run against live)

| Method | Path                                       | Notes |
|--------|--------------------------------------------|-------|
| POST   | `/api/applications/discover`               | ⚠️ ingest posting; idempotent on job_id; returns status exists/skipped/saved |
| POST   | `/api/applications/scrape`                 | ⚠️ fetch + LLM-extract a posting from a URL |
| POST   | `/api/applications/preview`                | ⚠️ full tailor+audit preview (heavy/LLM) |
| POST   | `/api/applications/confirm`                | ⚠️ tailor + persist (422 on audit fail) |
| POST   | `/api/applications/rescore`                | ⚠️ re-score every tracked job |
| POST   | `/api/applications/archive-stale`          | ⚠️ archive old found entries (query: max_age_days) |
| POST   | `/api/applications/bulk-archive`           | ⚠️ archive many by job_ids |
| PUT    | `/api/applications/{job_id}/star`          | ⚠️ toggle starred |
| PUT    | `/api/applications/{job_id}/status`        | ⚠️ update status/notes/etc. |
| POST   | `/api/applications/{job_id}/tailor`        | ⚠️ generate a versioned resume (422 on audit fail) |
| POST   | `/api/applications/{job_id}/browser-apply` | ⚠️ launches a real browser |
| POST   | `/api/applications/{job_id}/cover-letter`  | ⚠️ generate cover letter (503 if OpenClaw down) |
| 🚫 DELETE | `/api/applications/{job_id}`            | 🚫 permanently deletes the job + all artifacts |

---

## Config

| Method | Path                  | Notes |
|--------|-----------------------|-------|
| POST   | `/api/reload-config`  | ⚠️ clears the config cache |

---

## Status codes you'll see

| Code | When |
|------|------|
| 200  | successful GET / update |
| 201  | (jsonplaceholder POST practice — not used by this API's discover) |
| 401  | missing or invalid token |
| 404  | job_id / resource not found |
| 422  | request validation failed (e.g. search `q` too short, audit failure detail) |
| 500  | server error (e.g. AUTH_MODE=token but API_TOKEN unset server-side) |
| 503  | dependency unavailable (OpenClaw for cover letters) |

---

## Quick test targets (safe, read-only)

- `GET /health`                              -> 200
- `GET /api/applications/`  (no token)       -> 401
- `GET /api/applications/`  (with token)     -> 200 (list)
- `GET /api/applications/does-not-exist`     -> 404
- `GET /api/applications/search?q=a`         -> 422 (too short)
- `GET /api/applications/search?q=ab`        -> 200
- `GET /api/dashboard/stats`                 -> 200
</content>
</invoke>
