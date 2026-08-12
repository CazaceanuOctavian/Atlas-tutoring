# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Start dev server
uvicorn main:app --reload

# Run tests
pytest

# Run a single test file
pytest path/to/test_file.py

# Enter Nix dev shell (sets up Python env and exports DATABASE_URL from env.json)
nix develop ./env
```

The Nix shell automatically exports `DATABASE_URL` from `env.json` (a local secrets file, not committed). Without this file, you must set `DATABASE_URL` manually. The app also requires the following env vars (in `.env` or the environment): `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `APP_BASE_URL`, `FRONTEND_URL`, `JWT_SECRET_KEY`, `JWT_ALGORITHM`, `JWT_EXPIRE_MINUTES`, `RUNNER_URL`.

## Architecture

This is a **FastAPI + SQLAlchemy (async) + PostgreSQL** tutoring platform backend. All routes are under `/api/v1`.

### Data model hierarchy

```
Course → Chapter → Lecture → Exercise → ExerciseBlock / TestCase
                                      → Submission
User → Enrollment (links User ↔ Course)
     → Submission
```

`LectureBlock` and `ExerciseBlock` are ordered content blocks (markdown, code, etc.) within their parent. `TestCase` holds input/expected_output pairs used for grading. `AuthHandoff` is a short-lived single-use record for the OAuth handoff flow.

### Auth flow (Google OAuth + JWT)

The auth flow is a 3-step handoff to avoid putting the JWT in a URL:
1. `GET /auth/google/login` — redirects to Google, sets an `oauth_state` cookie (CSRF protection).
2. `GET /auth/google/callback` — exchanges the auth code, verifies the Google ID token, upserts the user, mints a **single-use `AuthHandoff` code** (SHA-256 hashed in DB), and redirects the frontend to `/auth/callback?code=...`.
3. `POST /auth/exchange` — frontend POSTs the handoff code; backend validates it (expiry + single-use), issues the JWT, and returns user info.

Debug endpoints under `/auth/debug/` use the older userinfo-based flow and return the JWT directly in JSON — for development only.

### Auth dependencies

All auth wiring lives in `dependencies.py`, which imports from `jwt.py`:

- `get_current_user` — resolves the JWT Bearer token to a `User` ORM object.
- `admin_only` / `student_only` — role-enforcement FastAPI dependencies.
- `enrolled_for_course/chapter/lecture/exercise` — walk the model hierarchy to verify the user is enrolled; admins bypass all enrollment checks.

Import from `dependencies.py` in routers — never wire `jwt.py` directly in routers.

### Code submission & grading

`POST /exercises/{exercise_id}/submissions` sends student code to an external **runner service** (`RUNNER_URL`). The runner compiles and executes the code once, then runs it against all test case inputs in a single `/run-batch` request. Results are compared against `TestCase.expected_output`; `Submission.passed_testcases` is stored as a percentage (0–100).

Supported languages: `python`, `cpp` (see `models/submission.py` `Language` enum).

### Schema/model split

- `models/` — SQLAlchemy ORM classes (DB schema). All models must be imported in `models/__init__.py` so `Base.metadata.create_all` registers them.
- `schemas/` — Pydantic schemas for request/response validation. Each domain has `Create`, `Update`, and read schemas.

### No migrations

The app uses `Base.metadata.create_all` on startup (see `main.py` lifespan). There is no Alembic setup — schema changes take effect by recreating tables or altering them manually.
