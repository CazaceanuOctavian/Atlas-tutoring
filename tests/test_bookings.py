import pytest
from httpx import AsyncClient

_START = "2030-07-01T14:00:00Z"
_END   = "2030-07-01T15:00:00Z"


@pytest.fixture
async def course(admin_client: AsyncClient):
    resp = await admin_client.post("/api/v1/courses/", json={"title": "Booking Course", "position": 0})
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/courses/{data['id']}")


@pytest.fixture
async def availability(admin_client: AsyncClient, course: dict):
    resp = await admin_client.post(
        "/api/v1/availability/",
        json={"course_id": course["id"], "start_time": _START, "end_time": _END, "max_students": 5},
    )
    assert resp.status_code == 201
    data = resp.json()
    yield data
    await admin_client.delete(f"/api/v1/availability/{data['id']}")


@pytest.fixture
async def booking(student_client: AsyncClient, enrollment, availability: dict):
    """A committed booking owned by student_user."""
    resp = await student_client.post(
        "/api/v1/bookings/",
        json={"availability_id": availability["id"]},
    )
    assert resp.status_code == 201
    yield resp.json()
    # No DELETE endpoint for bookings; the row is cascade-deleted when the
    # availability/course fixtures tear down.


async def test_student_creates_booking(
    student_client: AsyncClient,
    enrollment,
    availability: dict,
):
    resp = await student_client.post(
        "/api/v1/bookings/",
        json={"availability_id": availability["id"]},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["availability_id"] == availability["id"]
    assert body["status"] == "pending"
    assert "student_id" in body
    assert "professor_id" in body


async def test_only_students_can_create_bookings(admin_client: AsyncClient, availability: dict):
    resp = await admin_client.post(
        "/api/v1/bookings/",
        json={"availability_id": availability["id"]},
    )
    assert resp.status_code == 403


async def test_not_enrolled_cannot_book(student_client: AsyncClient, availability: dict):
    # availability exists but student has no enrollment — no `enrollment` fixture used
    resp = await student_client.post(
        "/api/v1/bookings/",
        json={"availability_id": availability["id"]},
    )
    assert resp.status_code == 403


async def test_nonexistent_availability_returns_404(student_client: AsyncClient, enrollment):
    import uuid
    resp = await student_client.post(
        "/api/v1/bookings/",
        json={"availability_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


async def test_fully_booked_returns_409(
    admin_client: AsyncClient,
    student_client: AsyncClient,
    enrollment,
    course: dict,
):
    # Capacity-1 window
    resp = await admin_client.post(
        "/api/v1/availability/",
        json={"course_id": course["id"], "start_time": _START, "end_time": _END, "max_students": 1},
    )
    assert resp.status_code == 201
    slot_id = resp.json()["id"]

    first = await student_client.post("/api/v1/bookings/", json={"availability_id": slot_id})
    assert first.status_code == 201

    second = await student_client.post("/api/v1/bookings/", json={"availability_id": slot_id})
    assert second.status_code == 409

    await admin_client.delete(f"/api/v1/availability/{slot_id}")


async def test_list_bookings_as_student(student_client: AsyncClient, booking: dict):
    resp = await student_client.get("/api/v1/bookings/")
    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()]
    assert booking["id"] in ids


async def test_admin_sees_all_bookings(admin_client: AsyncClient, booking: dict):
    resp = await admin_client.get("/api/v1/bookings/")
    assert resp.status_code == 200
    ids = [b["id"] for b in resp.json()]
    assert booking["id"] in ids


async def test_get_booking(student_client: AsyncClient, booking: dict):
    resp = await student_client.get(f"/api/v1/bookings/{booking['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == booking["id"]


async def test_cancel_booking(student_client: AsyncClient, booking: dict):
    resp = await student_client.patch(
        f"/api/v1/bookings/{booking['id']}",
        json={"status": "cancelled"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"


async def test_student_cannot_confirm_booking(student_client: AsyncClient, booking: dict):
    # Only professors/admins can confirm; students may only cancel
    resp = await student_client.patch(
        f"/api/v1/bookings/{booking['id']}",
        json={"status": "confirmed"},
    )
    assert resp.status_code == 403


async def test_admin_can_confirm_booking(admin_client: AsyncClient, booking: dict):
    resp = await admin_client.patch(
        f"/api/v1/bookings/{booking['id']}",
        json={"status": "confirmed"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"


async def test_student_cannot_double_book_overlapping_interval(
    admin_client: AsyncClient,
    student_client: AsyncClient,
    enrollment,
    course: dict,
):
    # Two separate availability windows that share the same time interval.
    # The student is already enrolled (via the `enrollment` fixture).
    slot_payload = {
        "course_id": course["id"],
        "start_time": _START,
        "end_time": _END,
        "max_students": 5,
    }

    r1 = await admin_client.post("/api/v1/availability/", json=slot_payload)
    assert r1.status_code == 201
    slot1_id = r1.json()["id"]

    r2 = await admin_client.post("/api/v1/availability/", json=slot_payload)
    assert r2.status_code == 201
    slot2_id = r2.json()["id"]

    try:
        first = await student_client.post("/api/v1/bookings/", json={"availability_id": slot1_id})
        assert first.status_code == 201

        second = await student_client.post("/api/v1/bookings/", json={"availability_id": slot2_id})
        assert second.status_code == 409
        assert "overlaps" in second.json()["detail"].lower()
    finally:
        await admin_client.delete(f"/api/v1/availability/{slot1_id}")
        await admin_client.delete(f"/api/v1/availability/{slot2_id}")
