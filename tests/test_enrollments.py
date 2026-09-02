import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def course(admin_client: AsyncClient):
    resp = await admin_client.post("/api/v1/courses/", json={"title": "Enrollment Course", "position": 0})
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/courses/{data['id']}")


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------

async def test_admin_enroll_user(admin_client: AsyncClient, course: dict, student_user):
    resp = await admin_client.post(
        "/api/v1/enrollments/",
        json={"user_id": str(student_user.id), "course_id": course["id"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["user_id"] == str(student_user.id)
    assert body["course_id"] == course["id"]
    await admin_client.delete(f"/api/v1/enrollments/{body['id']}")


async def test_duplicate_enrollment_returns_409(admin_client: AsyncClient, course: dict, student_user):
    payload = {"user_id": str(student_user.id), "course_id": course["id"]}
    first = await admin_client.post("/api/v1/enrollments/", json=payload)
    assert first.status_code == 201

    second = await admin_client.post("/api/v1/enrollments/", json=payload)
    assert second.status_code == 409

    await admin_client.delete(f"/api/v1/enrollments/{first.json()['id']}")


async def test_list_enrollments(admin_client: AsyncClient, course: dict, student_user):
    resp = await admin_client.post(
        "/api/v1/enrollments/",
        json={"user_id": str(student_user.id), "course_id": course["id"]},
    )
    assert resp.status_code == 201
    enrollment_id = resp.json()["id"]

    list_resp = await admin_client.get("/api/v1/enrollments/")
    assert list_resp.status_code == 200
    ids = [e["id"] for e in list_resp.json()]
    assert enrollment_id in ids

    await admin_client.delete(f"/api/v1/enrollments/{enrollment_id}")


async def test_unenroll(admin_client: AsyncClient, course: dict, student_user):
    resp = await admin_client.post(
        "/api/v1/enrollments/",
        json={"user_id": str(student_user.id), "course_id": course["id"]},
    )
    assert resp.status_code == 201
    enrollment_id = resp.json()["id"]

    del_resp = await admin_client.delete(f"/api/v1/enrollments/{enrollment_id}")
    assert del_resp.status_code == 204


async def test_student_can_enroll_themselves(student_client: AsyncClient, course: dict, student_user):
    resp = await student_client.post(
        "/api/v1/enrollments/",
        json={"user_id": str(student_user.id), "course_id": course["id"]},
    )
    assert resp.status_code == 201
    await student_client.delete(f"/api/v1/enrollments/{resp.json()['id']}")


# ---------------------------------------------------------------------------
# Additional tests
# ---------------------------------------------------------------------------

async def test_my_enrollments_endpoint(student_client: AsyncClient, enrollment: dict):
    """GET /enrollments/me returns only the current student's enrollments."""
    resp = await student_client.get("/api/v1/enrollments/me")
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()]
    assert enrollment["id"] in ids


async def test_student_cannot_enroll_others(student_client: AsyncClient):
    """A student trying to enroll a different user_id gets 403."""
    resp = await student_client.post(
        "/api/v1/enrollments/",
        json={"user_id": str(uuid.uuid4()), "course_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 403


async def test_enroll_nonexistent_course_returns_404(admin_client: AsyncClient, student_user):
    resp = await admin_client.post(
        "/api/v1/enrollments/",
        json={"user_id": str(student_user.id), "course_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


async def test_enroll_nonexistent_user_returns_404(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/enrollments/",
        json={"user_id": str(uuid.uuid4()), "course_id": course["id"]},
    )
    assert resp.status_code == 404


async def test_unenroll_nonexistent_returns_404(admin_client: AsyncClient):
    resp = await admin_client.delete(f"/api/v1/enrollments/{uuid.uuid4()}")
    assert resp.status_code == 404
