import pytest
from httpx import AsyncClient

_START = "2030-06-01T10:00:00Z"
_END   = "2030-06-01T11:00:00Z"


@pytest.fixture
async def course(admin_client: AsyncClient):
    resp = await admin_client.post("/api/v1/courses/", json={"title": "Availability Course", "position": 0})
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/courses/{data['id']}")


@pytest.fixture
async def availability(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/availability/",
        json={"course_id": course["id"], "start_time": _START, "end_time": _END, "max_students": 2},
    )
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/availability/{data['id']}")


async def test_create_availability(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/availability/",
        json={"course_id": course["id"], "start_time": _START, "end_time": _END, "max_students": 3},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["course_id"] == course["id"]
    assert body["max_students"] == 3
    assert body["booked_count"] == 0
    assert "professor_id" in body
    await admin_client.delete(f"/api/v1/availability/{body['id']}")


async def test_list_availability_contains_created(admin_client: AsyncClient, availability: dict):
    resp = await admin_client.get("/api/v1/availability/")
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert availability["id"] in ids


async def test_list_availability_filter_by_course(admin_client: AsyncClient, availability: dict, course: dict):
    resp = await admin_client.get("/api/v1/availability/", params={"course_id": course["id"]})
    assert resp.status_code == 200
    for item in resp.json():
        assert item["course_id"] == course["id"]


async def test_get_availability(admin_client: AsyncClient, availability: dict):
    resp = await admin_client.get(f"/api/v1/availability/{availability['id']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == availability["id"]
    assert body["max_students"] == 2
    assert body["booked_count"] == 0


async def test_update_availability_capacity(admin_client: AsyncClient, availability: dict):
    resp = await admin_client.patch(
        f"/api/v1/availability/{availability['id']}",
        json={"max_students": 10},
    )
    assert resp.status_code == 200
    assert resp.json()["max_students"] == 10


async def test_update_availability_end_time(admin_client: AsyncClient, availability: dict):
    resp = await admin_client.patch(
        f"/api/v1/availability/{availability['id']}",
        json={"end_time": "2030-06-01T12:00:00Z"},
    )
    assert resp.status_code == 200


async def test_update_invalid_time_returns_422(admin_client: AsyncClient, availability: dict):
    # Setting end_time before start_time should be rejected
    resp = await admin_client.patch(
        f"/api/v1/availability/{availability['id']}",
        json={"end_time": "2025-01-01T09:00:00Z"},  # before existing start_time
    )
    assert resp.status_code == 422


async def test_delete_availability(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/availability/",
        json={"course_id": course["id"], "start_time": _START, "end_time": _END, "max_students": 1},
    )
    assert resp.status_code == 201
    slot_id = resp.json()["id"]

    del_resp = await admin_client.delete(f"/api/v1/availability/{slot_id}")
    assert del_resp.status_code == 204

    get_resp = await admin_client.get(f"/api/v1/availability/{slot_id}")
    assert get_resp.status_code == 404


async def test_create_invalid_time_returns_422(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/availability/",
        json={"course_id": course["id"], "start_time": _END, "end_time": _START, "max_students": 1},
    )
    assert resp.status_code == 422


async def test_booked_count_reflects_booking(
    admin_client: AsyncClient,
    student_client: AsyncClient,
    availability: dict,
    enrollment,  # ensures student is enrolled so the booking is accepted
):
    book_resp = await student_client.post(
        "/api/v1/bookings/",
        json={"availability_id": availability["id"]},
    )
    assert book_resp.status_code == 201

    get_resp = await admin_client.get(f"/api/v1/availability/{availability['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["booked_count"] == 1
