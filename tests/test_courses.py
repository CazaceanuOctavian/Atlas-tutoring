import pytest
from httpx import AsyncClient


@pytest.fixture
async def course(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/v1/courses",
        json={"title": "Intro to Python", "description": "Beginner Python.", "position": 0},
    )
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/courses/{data['id']}")


async def test_create_course(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/v1/courses",
        json={"title": "Algorithms", "position": 1},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Algorithms"
    assert body["position"] == 1
    assert "id" in body
    await admin_client.delete(f"/api/v1/courses/{body['id']}")


async def test_list_courses_contains_created(admin_client: AsyncClient, course: dict):
    resp = await admin_client.get("/api/v1/courses")
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()]
    assert course["id"] in ids


async def test_get_course(admin_client: AsyncClient, course: dict):
    resp = await admin_client.get(f"/api/v1/courses/{course['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == course["id"]
    assert resp.json()["title"] == course["title"]


async def test_update_course(admin_client: AsyncClient, course: dict):
    resp = await admin_client.patch(
        f"/api/v1/courses/{course['id']}",
        json={"title": "Advanced Python"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Advanced Python"


async def test_delete_course(admin_client: AsyncClient):
    resp = await admin_client.post("/api/v1/courses", json={"title": "To Be Deleted", "position": 99})
    assert resp.status_code == 201
    course_id = resp.json()["id"]

    del_resp = await admin_client.delete(f"/api/v1/courses/{course_id}")
    assert del_resp.status_code == 204

    get_resp = await admin_client.get(f"/api/v1/courses/{course_id}")
    assert get_resp.status_code == 404


async def test_get_nonexistent_course_returns_404(admin_client: AsyncClient):
    import uuid
    resp = await admin_client.get(f"/api/v1/courses/{uuid.uuid4()}")
    assert resp.status_code == 404
