import uuid

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# GET /users  (directory, admin)
# ---------------------------------------------------------------------------

async def test_list_users_contains_seeded(admin_client: AsyncClient, admin_user, student_user):
    resp = await admin_client.get("/api/v1/users/?limit=200")
    assert resp.status_code == 200
    ids = [u["id"] for u in resp.json()]
    assert str(admin_user.id) in ids
    assert str(student_user.id) in ids


async def test_list_users_role_filter(admin_client: AsyncClient, student_user, admin_user):
    resp = await admin_client.get("/api/v1/users/?role=student&limit=200")
    assert resp.status_code == 200
    body = resp.json()
    assert all(u["role"] == "student" for u in body)
    ids = [u["id"] for u in body]
    assert str(student_user.id) in ids
    assert str(admin_user.id) not in ids


async def test_list_users_role_comma_separated(admin_client: AsyncClient, admin_user, student_user):
    resp = await admin_client.get("/api/v1/users/?role=student,admin&limit=200")
    assert resp.status_code == 200
    roles = {u["role"] for u in resp.json()}
    assert roles <= {"student", "admin"}


async def test_list_users_unknown_role_422(admin_client: AsyncClient):
    resp = await admin_client.get("/api/v1/users/?role=wizard")
    assert resp.status_code == 422


async def test_list_users_search_by_email(admin_client: AsyncClient, student_user):
    resp = await admin_client.get(f"/api/v1/users/?q={student_user.email}&limit=200")
    assert resp.status_code == 200
    ids = [u["id"] for u in resp.json()]
    assert str(student_user.id) in ids


async def test_list_users_envelope(admin_client: AsyncClient, student_user):
    resp = await admin_client.get("/api/v1/users/?envelope=1&limit=5")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"items", "total", "skip", "limit"}
    assert body["limit"] == 5
    assert body["total"] >= 1
    assert isinstance(body["items"], list)


# ---------------------------------------------------------------------------
# GET /users/{id}
# ---------------------------------------------------------------------------

async def test_get_user(admin_client: AsyncClient, student_user):
    resp = await admin_client.get(f"/api/v1/users/{student_user.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(student_user.id)
    assert body["email"] == student_user.email


async def test_get_user_404(admin_client: AsyncClient):
    resp = await admin_client.get(f"/api/v1/users/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /users/{id}  (promote role)
# ---------------------------------------------------------------------------

async def test_promote_user_to_professor(admin_client: AsyncClient, student_user):
    resp = await admin_client.patch(
        f"/api/v1/users/{student_user.id}", json={"role": "professor"}
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "professor"


async def test_patch_user_password_rejected(admin_client: AsyncClient, student_user):
    resp = await admin_client.patch(
        f"/api/v1/users/{student_user.id}", json={"password": "secret"}
    )
    assert resp.status_code == 400


async def test_patch_user_404(admin_client: AsyncClient):
    resp = await admin_client.patch(f"/api/v1/users/{uuid.uuid4()}", json={"role": "admin"})
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Per-student stats + progress  (item #9)
# ---------------------------------------------------------------------------

async def test_students_include_stats(admin_client: AsyncClient, student_user):
    resp = await admin_client.get("/api/v1/students/?include=stats&limit=200")
    assert resp.status_code == 200
    mine = [u for u in resp.json() if u["id"] == str(student_user.id)]
    assert mine, "seeded student should appear"
    user = mine[0]
    # with ?include=stats these are populated (ints), not null
    assert isinstance(user["enrolled_course_count"], int)
    assert isinstance(user["submission_count"], int)


async def test_students_without_stats_are_null(admin_client: AsyncClient, student_user):
    resp = await admin_client.get("/api/v1/students/?limit=200")
    assert resp.status_code == 200
    mine = [u for u in resp.json() if u["id"] == str(student_user.id)]
    assert mine
    assert mine[0]["enrolled_course_count"] is None


async def test_student_progress_empty(admin_client: AsyncClient, student_user):
    resp = await admin_client.get(f"/api/v1/students/{student_user.id}/progress")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Professor profiles embedded on /courses/{id}/professors  (item #7)
# ---------------------------------------------------------------------------

@pytest.fixture
async def course(admin_client: AsyncClient):
    resp = await admin_client.post("/api/v1/courses/", json={"title": "Prof Course", "position": 0})
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/courses/{data['id']}")


async def test_list_professors_embeds_user(admin_client: AsyncClient, course: dict, student_user):
    # promote the seeded student to professor, then assign to the course
    promote = await admin_client.patch(
        f"/api/v1/users/{student_user.id}", json={"role": "professor"}
    )
    assert promote.status_code == 200

    assign = await admin_client.post(
        f"/api/v1/courses/{course['id']}/professors",
        json={"user_id": str(student_user.id)},
    )
    assert assign.status_code == 201

    resp = await admin_client.get(f"/api/v1/courses/{course['id']}/professors")
    assert resp.status_code == 200
    rows = resp.json()
    mine = [r for r in rows if r["user_id"] == str(student_user.id)]
    assert mine
    assert mine[0]["user"] is not None
    assert mine[0]["user"]["email"] == student_user.email

    await admin_client.delete(
        f"/api/v1/courses/{course['id']}/professors/{student_user.id}"
    )
