import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session

from models.submission import Language, Submission, SubmissionStatus


# ---------------------------------------------------------------------------
# Fixture: a course -> chapter -> lecture -> exercise tree (via the API) plus
# one submission for `student_user`, inserted directly (the runner service is
# external and unavailable in tests).
# ---------------------------------------------------------------------------

@pytest.fixture
async def submission(admin_client: AsyncClient, student_user, _sync_engine):
    course = (await admin_client.post(
        "/api/v1/courses/", json={"title": "Feed Course", "position": 0}
    )).json()
    chapter = (await admin_client.post(
        "/api/v1/chapters/", json={"course_id": course["id"], "title": "Basics", "position": 0}
    )).json()
    lecture = (await admin_client.post(
        "/api/v1/lectures/", json={"chapter_id": chapter["id"], "title": "Loops", "position": 0}
    )).json()
    exercise = (await admin_client.post(
        "/api/v1/exercises/", json={"lecture_id": lecture["id"], "title": "Sum of N", "position": 0}
    )).json()

    sub_id = uuid.uuid4()
    with Session(_sync_engine) as s:
        s.add(Submission(
            id=sub_id,
            exercise_id=uuid.UUID(exercise["id"]),
            student_id=student_user.id,
            code="print(6)",
            language=Language.python,
            status=SubmissionStatus.failed,
            passed_count=1,
            total_count=3,
            stdout="6\n",
        ))
        s.commit()

    data = {
        "submission_id": str(sub_id),
        "course": course,
        "chapter": chapter,
        "lecture": lecture,
        "exercise": exercise,
    }
    yield data

    # Deleting the course cascades to the submission.
    await admin_client.delete(f"/api/v1/courses/{course['id']}")


# ---------------------------------------------------------------------------
# GET /submissions  (feed)
# ---------------------------------------------------------------------------

async def test_feed_contains_submission_with_context(admin_client: AsyncClient, submission, student_user):
    resp = await admin_client.get("/api/v1/submissions/?limit=200")
    assert resp.status_code == 200
    mine = [s for s in resp.json() if s["id"] == submission["submission_id"]]
    assert mine, "submission should appear in the admin feed"
    row = mine[0]
    # summary mode: no heavy fields
    assert "code" not in row
    assert "test_results" not in row
    # embedded context
    assert row["exercise"]["title"] == "Sum of N"
    assert row["course"]["title"] == "Feed Course"
    assert row["student"]["id"] == str(student_user.id)
    assert row["passed_count"] == 1
    assert row["total_count"] == 3


async def test_feed_filter_by_exercise(admin_client: AsyncClient, submission):
    resp = await admin_client.get(
        f"/api/v1/submissions/?exercise_id={submission['exercise']['id']}"
    )
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert submission["submission_id"] in ids


async def test_feed_filter_by_status(admin_client: AsyncClient, submission):
    passed = await admin_client.get(
        f"/api/v1/submissions/?exercise_id={submission['exercise']['id']}&status=passed"
    )
    assert passed.status_code == 200
    assert submission["submission_id"] not in [s["id"] for s in passed.json()]

    failed = await admin_client.get(
        f"/api/v1/submissions/?exercise_id={submission['exercise']['id']}&status=failed"
    )
    assert submission["submission_id"] in [s["id"] for s in failed.json()]


async def test_feed_envelope(admin_client: AsyncClient, submission):
    resp = await admin_client.get("/api/v1/submissions/?envelope=1&limit=1")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"items", "total", "skip", "limit"}
    assert body["total"] >= 1


async def test_feed_student_scoped_to_own(student_client: AsyncClient, submission, student_user):
    resp = await student_client.get("/api/v1/submissions/?limit=200")
    assert resp.status_code == 200
    rows = resp.json()
    assert all(s["student_id"] == str(student_user.id) for s in rows)
    assert submission["submission_id"] in [s["id"] for s in rows]


# ---------------------------------------------------------------------------
# GET /submissions/{id}  (full record)
# ---------------------------------------------------------------------------

async def test_get_submission_full_record(admin_client: AsyncClient, submission):
    resp = await admin_client.get(f"/api/v1/submissions/{submission['submission_id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == submission["submission_id"]
    assert body["code"] == "print(6)"
    assert "test_results" in body


async def test_get_submission_404(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/v1/submissions/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /students/{id}/submissions  (alias)
# ---------------------------------------------------------------------------

async def test_student_submissions_alias(admin_client: AsyncClient, submission, student_user):
    resp = await admin_client.get(f"/api/v1/students/{student_user.id}/submissions")
    assert resp.status_code == 200
    ids = [s["id"] for s in resp.json()]
    assert submission["submission_id"] in ids
