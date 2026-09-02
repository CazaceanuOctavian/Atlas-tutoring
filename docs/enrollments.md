# Enrollments  (`/api/v1/enrollments`)

Links a `User` to a `Course`.

See [README.md](README.md) for the shared auth/role model and common error responses.

**Enrollment schema**
```json
{ "id": "uuid", "user_id": "uuid", "course_id": "uuid", "enrolled_at": "datetime" }
```

---

### `POST /enrollments/`
Enroll a user in a course. **Auth:** any authenticated user. Admins may enroll anyone; students may only enroll themselves (`user_id` must equal their own id, else `403`).

**Request body** (`EnrollmentCreate`)
```json
{ "user_id": "uuid", "course_id": "uuid" }
```
**Response `201`:** `Enrollment`. **Errors:** `403`, `404` course/user not found, `409` already enrolled.

### `DELETE /enrollments/{enrollment_id}`
Unenroll. **Auth:** any authenticated user. Admins can unenroll anyone; students only themselves.
**Response `204`.** **Errors:** `403`, `404`.

### `GET /enrollments/`
List enrollments. **Auth:** any authenticated user. Admins see all; students see only their own.
**Response `200`:** `Enrollment[]`.

### `GET /enrollments/me`
List the current student's enrollments. **Auth:** `student_only` (any authenticated user).
**Response `200`:** `Enrollment[]`.
