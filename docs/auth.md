# Auth  (`/api/v1/auth`)

Authentication is **Google OAuth → JWT**. The primary flow is a **3-step handoff** so the JWT is never placed in a URL.

See [README.md](README.md) for the shared auth/role model and common error responses.

---

### `GET /auth/google/login`
Step 1. Redirects the browser to Google's OAuth2 consent screen and sets a short-lived `oauth_state` cookie (CSRF protection, `SameSite=Lax`, scoped to `/api/v1/auth`).

**Query params**
| Name | Type | Default | Description |
|---|---|---|---|
| `next` | string | `/` | Frontend path to return to after login; round-tripped through the state cookie. |

**Response:** `307` redirect to Google. **No auth.**

### `GET /auth/google/callback`
Step 2. Google redirects here. The endpoint verifies `state`, exchanges the `code` for tokens, verifies the Google ID token, upserts the `User` (keyed on the stable Google `sub`, falling back to matching a verified email), mints a **single-use handoff code** (SHA-256 hashed in DB, 60-second TTL), and redirects to the frontend at `/auth/callback?code=<handoff>&next=<next_path>`.

**Query params (supplied by Google)**
| Name | Type | Description |
|---|---|---|
| `code` | string | Google authorization code. |
| `state` | string | Must match the `oauth_state` cookie. |
| `error` | string | Present if the user denied consent. |

**Response:** `307` redirect to the frontend. On any failure it redirects to `<frontend>/login?error=<reason>` (e.g. `no_code`, `state_missing`, `state_mismatch`, `token_exchange_failed`, `no_id_token`, `invalid_id_token`, `email_unverified`). **No auth.**

### `POST /auth/exchange`
Step 3. The frontend trades the handoff code for the real JWT. The handoff is validated for expiry and single use (`with_for_update` row lock, marks `used_at`).

**Request body**
```json
{ "code": "<handoff-code-from-redirect>" }
```

**Response `200`**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "role": "student",
    "created_at": "2026-09-02T10:00:00+00:00"
  }
}
```
**Errors:** `401` invalid/expired/already-used handoff code, or user no longer exists. **No auth (the handoff code is the credential).**

### `POST /auth/logout`
Stateless. JWTs are discarded client-side; this endpoint is a semantic marker. **No auth.**

**Response `200`**
```json
{ "message": "Successfully logged out. Discard your token." }
```

---

## Legacy debug endpoints — development only
These use the older `userinfo` flow and return the JWT directly in JSON. Do **not** use in production.

- `GET /auth/debug/google/login` — redirect to Google, callback points at the debug callback.
- `GET /auth/debug/google/callback` — exchange code, fetch userinfo, upsert user, return `{ access_token, token_type, user }` as JSON.
- `POST /auth/debug/logout` — identical to `/auth/logout`.
