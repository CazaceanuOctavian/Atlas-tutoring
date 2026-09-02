# Bookings  (`/api/v1/bookings`)

Student bookings against a professor's availability window (see [availability.md](availability.md)).

See [README.md](README.md) for the shared auth/role model and common error responses.

**BookingStatus enum:** `pending`, `confirmed`, `cancelled`.

**BookingRead schema**
```json
{
  "id": "uuid",
  "student_id": "uuid",
  "professor_id": "uuid",
  "course_id": "uuid",
  "availability_id": "uuid",
  "start_time": "datetime",
  "end_time": "datetime",
  "status": "pending",
  "created_at": "datetime"
}
```

---

### `POST /bookings/`
Book a session. **Auth:** any authenticated user, but **only students** may create bookings (`403` otherwise). Booking inherits the window's `professor_id`, `course_id`, `start_time`, `end_time` and starts as `pending`.

**Request body** (`BookingCreate`)
```json
{ "availability_id": "uuid" }
```

**Validation**
- Availability window must exist (`404`).
- Student must be enrolled in the window's course (`403`).
- Student must not have another non-cancelled booking overlapping this time (`409`).
- Window must have remaining capacity — active bookings `< max_students` (`409` fully booked).

**Response `201`:** `BookingRead`.

### `GET /bookings/`
List bookings, scoped by role. **Auth:** any authenticated user.
- **Admin:** all bookings.
- **Professor:** bookings on their own availability windows.
- **Student:** their own bookings.

**Query:** `course_id` (uuid, optional), `availability_id` (uuid, optional).
**Response `200`:** `BookingRead[]`.

### `GET /bookings/{booking_id}`
Fetch one booking. **Auth:** any authenticated user, but only the owning student, the owning professor, or an admin may read it (`403` otherwise).
**Response `200`:** `BookingRead`. **Errors:** `403`, `404`.

### `PATCH /bookings/{booking_id}`
Update booking status. **Auth:** any authenticated user, scoped:
- **Admin:** any transition.
- **Professor (owner):** any status (e.g. `confirmed`, `cancelled`); must own the booking (`403`).
- **Student (owner):** may only set `cancelled` (`403` for anything else); must own the booking.

**Request body** (`BookingStatusUpdate`)
```json
{ "status": "confirmed" }
```
**Response `200`:** `BookingRead`. **Errors:** `403`, `404`.
