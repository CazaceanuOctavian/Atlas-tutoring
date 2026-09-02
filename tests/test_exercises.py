import uuid

import pytest
from httpx import AsyncClient


@pytest.fixture
async def course(admin_client: AsyncClient):
    resp = await admin_client.post("/api/v1/courses", json={"title": "Exercises Course", "position": 0})
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/courses/{data['id']}")


@pytest.fixture
async def chapter(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/chapters",
        json={"course_id": course["id"], "title": "Chapter", "position": 0},
    )
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/chapters/{data['id']}")


@pytest.fixture
async def lecture(admin_client: AsyncClient, chapter: dict):
    resp = await admin_client.post(
        "/api/v1/lectures",
        json={"chapter_id": chapter["id"], "title": "Lecture", "position": 0},
    )
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/lectures/{data['id']}")


@pytest.fixture
async def exercise(admin_client: AsyncClient, lecture: dict):
    resp = await admin_client.post(
        "/api/v1/exercises",
        json={"lecture_id": lecture["id"], "title": "Exercise 1", "position": 0},
    )
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/exercises/{data['id']}")


async def test_create_exercise(admin_client: AsyncClient, lecture: dict):
    resp = await admin_client.post(
        "/api/v1/exercises",
        json={"lecture_id": lecture["id"], "title": "FizzBuzz", "position": 0, "code_template": "# write code here"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "FizzBuzz"
    assert body["lecture_id"] == lecture["id"]
    assert body["code_template"] == "# write code here"
    await admin_client.delete(f"/api/v1/exercises/{body['id']}")


async def test_create_exercise_invalid_lecture(admin_client: AsyncClient):
    resp = await admin_client.post(
        "/api/v1/exercises",
        json={"lecture_id": str(uuid.uuid4()), "title": "Ghost", "position": 0},
    )
    assert resp.status_code == 404


async def test_list_exercises_contains_created(admin_client: AsyncClient, lecture: dict, exercise: dict):
    resp = await admin_client.get("/api/v1/exercises", params={"lecture_id": lecture["id"]})
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()]
    assert exercise["id"] in ids


async def test_get_exercise(admin_client: AsyncClient, exercise: dict):
    resp = await admin_client.get(f"/api/v1/exercises/{exercise['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == exercise["id"]


async def test_update_exercise(admin_client: AsyncClient, exercise: dict):
    resp = await admin_client.patch(
        f"/api/v1/exercises/{exercise['id']}",
        json={"title": "Updated Exercise", "code_template": "pass"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["title"] == "Updated Exercise"
    assert body["code_template"] == "pass"


async def test_delete_exercise(admin_client: AsyncClient, lecture: dict):
    resp = await admin_client.post(
        "/api/v1/exercises",
        json={"lecture_id": lecture["id"], "title": "Temp Exercise", "position": 9},
    )
    assert resp.status_code == 201
    exercise_id = resp.json()["id"]

    del_resp = await admin_client.delete(f"/api/v1/exercises/{exercise_id}")
    assert del_resp.status_code == 204

    get_resp = await admin_client.get(f"/api/v1/exercises/{exercise_id}")
    assert get_resp.status_code == 404


async def test_list_test_cases_empty(admin_client: AsyncClient, exercise: dict):
    resp = await admin_client.get(f"/api/v1/exercises/{exercise['id']}/test-cases")
    assert resp.status_code == 200
    assert resp.json() == []


async def test_create_and_delete_test_case(admin_client: AsyncClient, exercise: dict):
    resp = await admin_client.post(
        f"/api/v1/exercises/{exercise['id']}/test-cases",
        json={"exercise_id": exercise["id"], "input": "5", "expected_output": "Buzz"},
    )
    assert resp.status_code == 201
    tc = resp.json()
    assert tc["input"] == "5"
    assert tc["expected_output"] == "Buzz"

    del_resp = await admin_client.delete(
        f"/api/v1/exercises/{exercise['id']}/test-cases/{tc['id']}"
    )
    assert del_resp.status_code == 204
