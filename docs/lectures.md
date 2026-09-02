# Lectures  (`/api/v1/lectures`)

See [README.md](README.md) for the shared auth/role model and common error responses.

**Lecture schema**
```json
{ "id": "uuid", "chapter_id": "uuid", "title": "string", "position": 0 }
```
**LectureBlock schema**
```json
{ "id": "uuid", "lecture_id": "uuid", "markdown": "string", "position": 0 }
```

---

### `GET /lectures/`
Flat list, ordered by `position`. **Auth:** any authenticated user (`student_only`).
**Query:** `chapter_id` (uuid, optional), `skip`, `limit`.
**Response `200`:** `Lecture[]`.

### `POST /lectures/`
Create a lecture. **Auth:** `admin_only`.

**Request body** (`LectureCreate`)
```json
{ "chapter_id": "uuid", "title": "Lecture 1", "position": 0 }
```
**Response `201`:** `Lecture`. **Errors:** `404` chapter not found.

### `GET /lectures/{lecture_id}`
Fetch one lecture. **Auth:** `enrolled_for_lecture`.
**Response `200`:** `Lecture`. **Errors:** `403`, `404`.

### `GET /lectures/{lecture_id}/detail`
Lecture with `blocks` and `exercises` pre-loaded. **Auth:** `enrolled_for_lecture`.
**Response `200`:** `LectureDetail`. **Errors:** `403`, `404`.

### `PATCH /lectures/{lecture_id}`
Partial update (`title`, `position`). **Auth:** `admin_only`.
**Response `200`:** `Lecture`. **Errors:** `404`.

### `DELETE /lectures/{lecture_id}`
Delete a lecture. **Auth:** `admin_only`.
**Response `204`.** **Errors:** `404`.

---

## Lecture blocks

### `GET /lectures/{lecture_id}/blocks`
List blocks, ordered by `position`. **Auth:** `enrolled_for_lecture`.
**Response `200`:** `LectureBlock[]`. **Errors:** `403`, `404`.

### `POST /lectures/{lecture_id}/blocks`
Create a block. **Auth:** `admin_only`.

**Request body** (`LectureBlockCreate`)
```json
{ "lecture_id": "uuid", "markdown": "# Heading", "position": 0 }
```
**Response `201`:** `LectureBlock`. **Errors:** `404` lecture not found.

### `PATCH /lectures/{lecture_id}/blocks/{block_id}`
Partial update (`markdown`, `position`). **Auth:** `admin_only`.
**Response `200`:** `LectureBlock`. **Errors:** `404` if block missing or not part of the lecture.

### `DELETE /lectures/{lecture_id}/blocks/{block_id}`
Delete a block. **Auth:** `admin_only`.
**Response `204`.** **Errors:** `404`.

---

### `GET /lectures/{lecture_id}/exercises`
List exercises of a lecture, ordered by `position`. **Auth:** `enrolled_for_lecture`.
**Response `200`:** `Exercise[]` (see [exercises.md](exercises.md)). **Errors:** `403`, `404`.
