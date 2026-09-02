# Availability  (`/api/v1/availability`)

Professor availability windows that students can book against. Bookings are documented in [bookings.md](bookings.md).

See [README.md](README.md) for the shared auth/role model and common error responses.

**AvailabilityRead schema**
```json
{
  "id": "uuid",
  "professor_id": "uuid",
  "course_id": "uuid",
  "start_time": "datetime",
  "end_time": "datetime",
  "max_students": 1,
  "booked_count": 0,
  "created_at": "datetime"
}
```
`booked_count` = number of non-cancelled bookings on the window.

---

### `POST /availability/`
Create an availability window. **Auth:** `professor_only` (professor or admin). A professor must be assigned to `course_id` (`403` otherwise); admins bypass the assignment check and create on behalf of themselves as `professor_id`.

**Request body** (`AvailabilityCreate`)
```json
{ "course_id": "uuid", "start_time": "datetime", "end_time": "datetime", "max_students": 1 }
```
Validation: `max_students >= 1`; `end_time` must be after `start_time` (`422` otherwise).
**Response `201`:** `AvailabilityRead` (`booked_count = 0`).

### `GET /availability/`
List availability windows, scoped by role. **Auth:** any authenticated user.
- **Admin:** all windows, filterable by `course_id` and/or `professor_id`.
- **Professor:** only their own windows, filterable by `course_id`.
- **Student:** windows for courses they are enrolled in, filterable by `course_id`/`professor_id`.

**Query:** `course_id` (uuid, optional), `professor_id` (uuid, optional).
**Response `200`:** `AvailabilityRead[]`.

### `GET /availability/{availability_id}`
Fetch one window (with live `booked_count`). **Auth:** any authenticated user.
**Response `200`:** `AvailabilityRead`. **Errors:** `404`.

### `PATCH /availability/{availability_id}`
Update a window. **Auth:** `professor_only`. Professors may only edit their own (`403` otherwise); admins may edit any.

**Request body** (`AvailabilityUpdate`, all optional)
```json
{ "start_time": "datetime", "end_time": "datetime", "max_students": 2 }
```
Validation: merged `end_time` must be after merged `start_time` (`422`); `max_students >= 1`.
**Response `200`:** `AvailabilityRead`. **Errors:** `403`, `404`, `422`.

### `DELETE /availability/{availability_id}`
Delete a window (cascades to its bookings). **Auth:** `professor_only`; professors only their own, admins any.
**Response `204`.** **Errors:** `403`, `404`.
