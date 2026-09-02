# Courses  (`/api/v1/courses`)

See [README.md](README.md) for the shared auth/role model and common error responses.

**Course schema**
```json
{
  "id": "uuid",
  "title": "string",
  "description": "string | null",
  "position": 0,
  "created_at": "datetime"
}
```

---

### `GET /courses/`
List the course catalogue, ordered by `position`. **Auth:** any authenticated user (`student_only`).

**Query:** `skip` (int, default `0`), `limit` (int, default `100`).
**Response `200`:** `Course[]`.

### `POST /courses/`
Create a course. **Auth:** `admin_only`.

**Request body** (`CourseCreate`)
```json
{ "title": "Intro to CS", "description": "optional", "position": 0 }
```
**Response `201`:** `Course`.

### `GET /courses/{course_id}`
Fetch one course. **Auth:** `enrolled_for_course`.
**Response `200`:** `Course`. **Errors:** `403` not enrolled/assigned, `404` not found.

### `GET /courses/{course_id}/detail`
Fetch a course with the full nested tree: chapters → lectures → (blocks + exercises). **Auth:** `enrolled_for_course`.
**Response `200`:** `CourseDetail` (a `Course` plus `chapters: ChapterDetail[]`). **Errors:** `403`, `404`.

### `PATCH /courses/{course_id}`
Partial update. **Auth:** `admin_only`.

**Request body** (`CourseUpdate`, all optional)
```json
{ "title": "...", "description": "...", "position": 1 }
```
**Response `200`:** `Course`. **Errors:** `404`.

### `DELETE /courses/{course_id}`
Delete a course (cascades to chapters, enrollments, assignments, availability, bookings). **Auth:** `admin_only`.
**Response `204`.** **Errors:** `404`.

### `GET /courses/{course_id}/chapters`
List chapters of a course, ordered by `position`. **Auth:** `enrolled_for_course`.
**Response `200`:** `Chapter[]` (see [chapters.md](chapters.md)). **Errors:** `403`, `404`.

---

Professor↔course assignment endpoints are also mounted under `/courses/{course_id}/professors` — see [professors.md](professors.md).
