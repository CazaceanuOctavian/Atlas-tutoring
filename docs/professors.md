# Professors  (`/api/v1/courses/.../professors`)

Manages professor↔course assignments. Tagged `professors` but mounted under `/courses`.

See [README.md](README.md) for the shared auth/role model and common error responses.

**CourseAssignment schema**
```json
{ "id": "uuid", "user_id": "uuid", "course_id": "uuid", "assigned_at": "datetime" }
```

---

### `POST /courses/{course_id}/professors`
Assign a professor to a course. **Auth:** `admin_only`.

**Request body** (`CourseAssignmentCreate`)
```json
{ "user_id": "uuid" }
```
**Response `201`:** `CourseAssignment`. **Errors:** `404` course/user not found, `400` user is not a professor, `409` already assigned.

### `DELETE /courses/{course_id}/professors/{user_id}`
Remove a professor from a course. **Auth:** `admin_only`.
**Response `204`.** **Errors:** `404` assignment not found.

### `GET /courses/{course_id}/professors`
List professors assigned to a course. **Auth:** `enrolled_for_course`.
**Response `200`:** `CourseAssignment[]`. **Errors:** `403`, `404`.
