import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def course(admin_client: AsyncClient):
    resp = await admin_client.post("/api/v1/courses", json={"title": "Chapters Course", "position": 0})
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/courses/{data['id']}")


@pytest.fixture
async def chapter(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/chapters",
        json={"course_id": course["id"], "title": "Chapter 1", "position": 0},
    )
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/chapters/{data['id']}")


async def test_create_chapter(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/chapters",
        json={"course_id": course["id"], "title": "Intro Chapter", "position": 0},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Intro Chapter"
    assert body["course_id"] == course["id"]
    await admin_client.delete(f"/api/v1/chapters/{body['id']}")


async def test_create_chapter_invalid_course(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/v1/chapters",
        json={"course_id": str(uuid.uuid4()), "title": "Ghost Chapter", "position": 0},
    )
    assert resp.status_code == 404


async def test_list_chapters_for_course(admin_client: AsyncClient, course: dict, chapter: dict):
    resp = await admin_client.get("/api/v1/chapters", params={"course_id": course["id"]})
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()]
    assert chapter["id"] in ids


async def test_get_chapter(admin_client: AsyncClient, chapter: dict):
    resp = await admin_client.get(f"/api/v1/chapters/{chapter['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == chapter["id"]


async def test_update_chapter(admin_client: AsyncClient, chapter: dict):
    resp = await admin_client.patch(
        f"/api/v1/chapters/{chapter['id']}",
        json={"title": "Updated Chapter"},
    )
    assert resp.status_code == 200
    assert resp.json()["title"] == "Updated Chapter"


async def test_delete_chapter(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/chapters",
        json={"course_id": course["id"], "title": "Temp Chapter", "position": 9},
    )
    assert resp.status_code == 201
    chapter_id = resp.json()["id"]

    del_resp = await admin_client.delete(f"/api/v1/chapters/{chapter_id}")
    assert del_resp.status_code == 204

    get_resp = await admin_client.get(f"/api/v1/chapters/{chapter_id}")
    assert get_resp.status_code == 404
