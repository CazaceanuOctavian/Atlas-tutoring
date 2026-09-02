# Exercises  (`/api/v1/exercises`)

See [README.md](README.md) for the shared auth/role model and common error responses.
Code submissions against exercises are documented in [submissions.md](submissions.md).

**Exercise schema**
```json
{ "id": "uuid", "lecture_id": "uuid", "title": "string", "position": 0, "code_template": "string | null" }
```
**ExerciseBlock schema**
```json
{ "id": "uuid", "exercise_id": "uuid", "markdown": "string", "position": 0 }
```
**TestCase schema**
```json
{ "id": "uuid", "exercise_id": "uuid", "expected_output": "string", "input": "string | null", "description": "string | null" }
```

---

### `GET /exercises/`
Flat list, ordered by `position`. **Auth:** any authenticated user (`student_only`).
**Query:** `lecture_id` (uuid, optional), `skip`, `limit`.
**Response `200`:** `Exercise[]`.

### `POST /exercises/`
Create an exercise. **Auth:** `admin_only`.

**Request body** (`ExerciseCreate`)
```json
{ "lecture_id": "uuid", "title": "Sum two numbers", "position": 0, "code_template": "def solve():" }
```
**Response `201`:** `Exercise`. **Errors:** `404` lecture not found.

### `GET /exercises/{exercise_id}`
Fetch one exercise. **Auth:** `enrolled_for_exercise`.
**Response `200`:** `Exercise`. **Errors:** `403`, `404`.

### `PATCH /exercises/{exercise_id}`
Partial update (`title`, `position`, `code_template`). **Auth:** `admin_only`.
**Response `200`:** `Exercise`. **Errors:** `404`.

### `DELETE /exercises/{exercise_id}`
Delete an exercise (cascades to blocks, test cases, submissions). **Auth:** `admin_only`.
**Response `204`.** **Errors:** `404`.

---

## Exercise blocks

### `GET /exercises/{exercise_id}/blocks`
List blocks, ordered by `position`. **Auth:** `enrolled_for_exercise`.
**Response `200`:** `ExerciseBlock[]`. **Errors:** `403`, `404`.

### `POST /exercises/{exercise_id}/blocks`
Create a block. **Auth:** `admin_only`.

**Request body** (`ExerciseBlockCreate`)
```json
{ "exercise_id": "uuid", "markdown": "Problem statement", "position": 0 }
```
**Response `201`:** `ExerciseBlock`. **Errors:** `404`.

### `PATCH /exercises/{exercise_id}/blocks/{block_id}`
Partial update (`markdown`, `position`). **Auth:** `admin_only`.
**Response `200`:** `ExerciseBlock`. **Errors:** `404`.

### `DELETE /exercises/{exercise_id}/blocks/{block_id}`
Delete a block. **Auth:** `admin_only`.
**Response `204`.** **Errors:** `404`.

---

## Test cases

### `GET /exercises/{exercise_id}/test-cases`
List all test cases for an exercise. **Auth:** `enrolled_for_exercise`.
**Response `200`:** `TestCase[]`. **Errors:** `403`, `404`.

> Note: test cases include `expected_output`; access is limited to enrolled/assigned users and admins.

### `POST /exercises/{exercise_id}/test-cases`
Create a test case. **Auth:** `admin_only`.

**Request body** (`TestCaseCreate`)
```json
{ "exercise_id": "uuid", "expected_output": "42", "input": "40\n2", "description": "optional" }
```
**Response `201`:** `TestCase`. **Errors:** `404`.

### `PATCH /exercises/{exercise_id}/test-cases/{test_case_id}`
Partial update (`input`, `expected_output`, `description`). **Auth:** `admin_only`.
**Response `200`:** `TestCase`. **Errors:** `404`.

### `DELETE /exercises/{exercise_id}/test-cases/{test_case_id}`
Delete a test case. **Auth:** `admin_only`.
**Response `204`.** **Errors:** `404`.
