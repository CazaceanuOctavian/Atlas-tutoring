import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def course(admin_client: AsyncClient):
    resp = await admin_client.post("/api/v1/courses", json={"title": "Lectures Course", "position": 0})
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/courses/{data['id']}")


@pytest.fixture
async def chapter(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/chapters",
        json={"course_id": course["id"], "title": "Chapter A", "position": 0},
    )
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/chapters/{data['id']}")


@pytest.fixture
async def lecture(admin_client: AsyncClient, chapter: dict):
    resp = await admin_client.post(
        "/api/v1/lectures",
        json={"chapter_id": chapter["id"], "title": "Lecture 1", "position": 0},
    )
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/lectures/{data['id']}")


async def test_create_lecture(admin_client: AsyncClient, chapter: dict):
    resp = await admin_client.post(
        "/api/v1/lectures",
        json={"chapter_id": chapter["id"], "title": "New Lecture", "position": 0},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "New Lecture"
    assert body["chapter_id"] == chapter["id"]
    await admin_client.delete(f"/api/v1/lectures/{body['id']}")


async def test_create_lecture_invalid_chapter(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/v1/lectures",
        json={"chapter_id": str(uuid.uuid4()), "title": "Ghost Lecture", "position": 0},
    )
    assert resp.status_code == 404


async def test_list_lectures_for_chapter(admin_client: AsyncClient, chapter: dict, lecture: dict):
    resp = await admin_client.get("/api/v1/lectures", params={"chapter_id": chapter["id"]})
    assert resp.status_code == 200
    ids = [l["id"] for l in resp.json()]
    assert lecture["id"] in ids


async def test_get_lecture(admin_client: AsyncClient, lecture: dict):
    resp = await admin_client.get(f"/api/v1/lectures/{lecture['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == lecture["id"]


async def test_update_lecture(admin_client: AsyncClient, lecture: dict):
    resp = await admin_client.patch(
        f"/api/v1/lectures/{lecture['id']}",
        json={"title": "Updated Lecture"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Lecture"


async def test_delete_lecture(admin_client: AsyncClient, chapter: dict):
    resp = await admin_client.post(
        "/api/v1/lectures",
        json={"chapter_id": chapter["id"], "title": "Temp Lecture", "position": 9},
    )
    assert resp.status_code == 201
    lecture_id = resp.json()["id"]

    del_resp = await admin_client.delete(f"/api/v1/lectures/{lecture_id}")
    assert del_resp.status_code == 204

    get_resp = await admin_client.get(f"/api/v1/lectures/{lecture_id}")
    assert get_resp.status_code == 404


async def test_list_lecture_blocks_empty(admin_client: AsyncClient, lecture: dict):
    resp = await admin_client.get(f"/api/v1/lectures/{lecture['id']}/blocks")
    assert resp.status_code == 200
    assert resp.json() == []
