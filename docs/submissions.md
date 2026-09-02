# Submissions  (`/api/v1/exercises/{exercise_id}/submissions`)

Student code is sent to the external **runner service** (`RUNNER_URL`). The submission is graded synchronously against the exercise's test cases.

See [README.md](README.md) for the shared auth/role model and common error responses.

**Language enum:** `python`, `cpp`.
**SubmissionStatus enum:** `queued`, `running`, `passed`, `failed`, `error`, `timeout`.

**Submission schema**
```json
{
  "id": "uuid",
  "exercise_id": "uuid",
  "student_id": "uuid",
  "code": "string",
  "language": "python",
  "status": "passed",
  "created_at": "datetime",
  "stdout": "string | null",
  "stderr": "string | null",
  "timed_out": "bool | null",
  "exit_code": "string | null",
  "passed_count": "int | null",
  "total_count": "int | null",
  "test_results": [
    {
      "test_case_id": "uuid",
      "order_index": 0,
      "passed": true,
      "actual_output": "string | null",
      "stderr": "string | null",
      "exit_code": "string | null",
      "timed_out": false
    }
  ]
}
```

---

### `POST /exercises/{exercise_id}/submissions`
Submit code for grading. **Auth:** `enrolled_for_exercise`.

**Request body** (`SubmissionCreate`)
```json
{ "code": "print(42)", "language": "python" }
```

**Grading behavior**
- The submission is persisted (`queued` → `running`), then each test case is executed in `order_index` order via the runner's `/run-batch`.
- A test passes when: not timed out **and** exit code `0` **and** `stdout.strip() == expected_output.strip()`.
- Execution **stops at the first failing test case** (remaining tests are not run).
- Final `status`: `passed` if all pass; otherwise `failed` (wrong output), `error` (non-zero exit), or `timeout`.
- `passed_count`/`total_count` reflect the grading tally. If the exercise has **no test cases**, the code is run once with empty stdin and status is derived from exit code / timeout (grading counts stay null).
- If the runner times out or errors, the submission is saved with status `timeout`/`error` and a message in `stderr`.

**Response `201`:** `Submission` (with `test_results`). **Errors:** `403`, `404` exercise not found.

### `GET /exercises/{exercise_id}/submissions`
List submissions for an exercise, newest first. **Auth:** `enrolled_for_exercise`. Students see only their own; professors/admins see all.
**Response `200`:** `Submission[]`. **Errors:** `403`, `404`.

### `GET /exercises/{exercise_id}/submissions/{submission_id}`
Fetch one submission. **Auth:** `enrolled_for_exercise`. Students may only read their own (`403` otherwise).
**Response `200`:** `Submission`. **Errors:** `403`, `404`.
