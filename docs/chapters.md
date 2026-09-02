# Chapters  (`/api/v1/chapters`)

See [README.md](README.md) for the shared auth/role model and common error responses.

**Chapter schema**
```json
{ "id": "uuid", "course_id": "uuid", "title": "string", "position": 0 }
```

---

### `GET /chapters/`
Flat list of chapters, ordered by `position`. **Auth:** any authenticated user (`student_only`). No enrollment check because `course_id` is optional.
**Query:** `course_id` (uuid, optional filter), `skip` (default `0`), `limit` (default `100`).
**Response `200`:** `Chapter[]`.

### `POST /chapters/`
Create a chapter. **Auth:** `admin_only`.

**Request body** (`ChapterCreate`)
```json
{ "course_id": "uuid", "title": "Chapter 1", "position": 0 }
```
**Response `201`:** `Chapter`. **Errors:** `404` course not found.

### `GET /chapters/{chapter_id}`
Fetch one chapter. **Auth:** `enrolled_for_chapter`.
**Response `200`:** `Chapter`. **Errors:** `403`, `404`.

### `GET /chapters/{chapter_id}/detail`
Chapter with nested lectures → (blocks + exercises). **Auth:** `enrolled_for_chapter`.
**Response `200`:** `ChapterDetail`. **Errors:** `403`, `404`.

### `PATCH /chapters/{chapter_id}`
Partial update (`title`, `position`). **Auth:** `admin_only`.
**Response `200`:** `Chapter`. **Errors:** `404`.

### `DELETE /chapters/{chapter_id}`
Delete a chapter (cascades to lectures). **Auth:** `admin_only`.
**Response `204`.** **Errors:** `404`.

### `GET /chapters/{chapter_id}/lectures`
List lectures of a chapter, ordered by `position`. **Auth:** `enrolled_for_chapter`.
**Response `200`:** `Lecture[]` (see [lectures.md](lectures.md)). **Errors:** `403`, `404`.
