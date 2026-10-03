import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def course(admin_client: AsyncClient):
    resp = await admin_client.post("/api/v1/courses/", json={"title": "Misc Course", "position": 0})
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/courses/{data['id']}")


# ---------------------------------------------------------------------------
# GET /admin/stats  (item #8)
# ---------------------------------------------------------------------------

async def test_admin_stats_shape(admin_client: AsyncClient):
    resp = await admin_client.get("/api/v1/admin/stats")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("users", "courses", "chapters", "lectures", "exercises",
                "enrollments", "submissions", "active_students_7d", "generated_at"):
        assert key in body
    assert set(body["users"].keys()) >= {"admin", "professor", "student"}
    assert set(body["submissions"].keys()) == {"total", "last_7_days", "by_status"}
    assert isinstance(body["courses"], int)


# ---------------------------------------------------------------------------
# Pagination envelope (item #4)
# ---------------------------------------------------------------------------

async def test_courses_default_is_bare_list(admin_client: AsyncClient, course: dict):
    resp = await admin_client.get("/api/v1/courses/")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


async def test_courses_envelope(admin_client: AsyncClient, course: dict):
    resp = await admin_client.get("/api/v1/courses/?envelope=1&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"items", "total", "skip", "limit"}
    assert body["total"] >= 1
    assert isinstance(body["items"], list)


# ---------------------------------------------------------------------------
# Filters / search (item #5)
# ---------------------------------------------------------------------------

async def test_courses_search_by_title(admin_client: AsyncClient, course: dict):
    resp = await admin_client.get("/api/v1/courses/?q=Misc")
    assert resp.status_code == 200
    assert course["id"] in [c["id"] for c in resp.json()]


async def test_exercises_filter_by_course(admin_client: AsyncClient, course: dict):
    chapter = (await admin_client.post(
        "/api/v1/chapters/", json={"course_id": course["id"], "title": "C", "position": 0}
    )).json()
    lecture = (await admin_client.post(
        "/api/v1/lectures/", json={"chapter_id": chapter["id"], "title": "L", "position": 0}
    )).json()
    exercise = (await admin_client.post(
        "/api/v1/exercises/", json={"lecture_id": lecture["id"], "title": "E", "position": 0}
    )).json()

    resp = await admin_client.get(f"/api/v1/exercises/?course_id={course['id']}")
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()]
    assert exercise["id"] in ids


# ---------------------------------------------------------------------------
# Embedded expand (item #6)
# ---------------------------------------------------------------------------

async def test_enrollments_expand(admin_client: AsyncClient, enrollment: dict, student_user):
    resp = await admin_client.get("/api/v1/enrollments/?expand=course,user&limit=200")
    assert resp.status_code == 200
    mine = [e for e in resp.json() if e["id"] == enrollment["id"]]
    assert mine
    row = mine[0]
    assert row["course"] is not None and "title" in row["course"]
    assert row["user"] is not None and row["user"]["id"] == str(student_user.id)


async def test_enrollments_filter_by_course(admin_client: AsyncClient, enrollment: dict, course: dict):
    resp = await admin_client.get(f"/api/v1/enrollments/?course_id={enrollment['course_id']}")
    assert resp.status_code == 200
    assert enrollment["id"] in [e["id"] for e in resp.json()]


# ---------------------------------------------------------------------------
# Bulk reorder (item #10)
# ---------------------------------------------------------------------------

async def test_reorder_chapters(admin_client: AsyncClient, course: dict):
    a = (await admin_client.post(
        "/api/v1/chapters/", json={"course_id": course["id"], "title": "A", "position": 0}
    )).json()
    b = (await admin_client.post(
        "/api/v1/chapters/", json={"course_id": course["id"], "title": "B", "position": 1}
    )).json()

    resp = await admin_client.put(
        f"/api/v1/courses/{course['id']}/chapters/order",
        json={"ids": [b["id"], a["id"]]},
    )
    assert resp.status_code == 204

    listing = await admin_client.get(f"/api/v1/courses/{course['id']}/chapters")
    ordered = [c["id"] for c in listing.json()]
    assert ordered == [b["id"], a["id"]]


async def test_reorder_rejects_incomplete_set(admin_client: AsyncClient, course: dict):
    await admin_client.post(
        "/api/v1/chapters/", json={"course_id": course["id"], "title": "Only", "position": 0}
    )
    resp = await admin_client.put(
        f"/api/v1/courses/{course['id']}/chapters/order",
        json={"ids": [str(uuid.uuid4())]},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Dry-run execution (item #11) — 404 path (runner is external)
# ---------------------------------------------------------------------------

async def test_dry_run_nonexistent_exercise_404(admin_client: AsyncClient):
    resp = await admin_client.post(
        f"/api/v1/exercises/{uuid.uuid4()}/run",
        json={"code": "print(1)", "language": "python"},
    )
    assert resp.status_code == 404
