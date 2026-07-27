import secrets
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from config import auth_settings
from db.session import get_db
from jwt import create_access_token
from models.auth_handoff import AuthHandoff
from models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

SCOPES = "openid email profile"
STATE_COOKIE = "oauth_state"
# Must match the PUBLIC path of the callback route. The router is mounted
# under /api/v1, so the browser sees /api/v1/auth/google/callback — a cookie
# scoped to /auth would not be sent on that request.
OAUTH_COOKIE_PATH = "/api/v1/auth"
HANDOFF_TTL = timedelta(seconds=60)


def _frontend(path: str, **params: str) -> str:
    """Build an absolute URL on the frontend origin."""
    url = f"{auth_settings.frontend_url.rstrip('/')}{path}"
    return f"{url}?{urlencode(params)}" if params else url


# ---------------------------------------------------------------------------
# Step 1 — send the browser to Google
# ---------------------------------------------------------------------------

@router.get("/google/login")
async def google_login(next: str = "/"):
    """Redirect the browser to Google's OAuth2 consent screen."""
    state = secrets.token_urlsafe(32)

    params = {
        "client_id": auth_settings.google_client_id,
        "redirect_uri": auth_settings.google_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "prompt": "select_account",
        "state": state,
    }

    response = RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    # First-party to backend.com and only read during a top-level navigation,
    # so SameSite=Lax survives Google's redirect back to us.
    response.set_cookie(
        STATE_COOKIE,
        f"{state}|{next}",
        max_age=600,
        httponly=True,
        secure=True,
        samesite="lax",
        path=OAUTH_COOKIE_PATH,
    )
    return response


# ---------------------------------------------------------------------------
# Step 2 — Google redirects here; we finish the flow and bounce to the frontend
# ---------------------------------------------------------------------------

@router.get("/google/callback")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Exchange the authorisation code, verify the ID token, upsert the user,
    then redirect the browser back to the frontend with a short-lived,
    single-use handoff code. The JWT itself is never put in the URL.
    """
    if error or not code:
        return RedirectResponse(_frontend("/login", error=error or "no_code"))

    # --- Verify state (CSRF protection) ---
    raw_cookie = request.cookies.get(STATE_COOKIE)
    if not raw_cookie or not state:
        return RedirectResponse(_frontend("/login", error="state_missing"))

    expected_state, _, next_path = raw_cookie.partition("|")
    if not secrets.compare_digest(expected_state, state):
        return RedirectResponse(_frontend("/login", error="state_mismatch"))
    next_path = next_path or "/"

    # --- Exchange code for tokens ---
    async with httpx.AsyncClient(timeout=10.0) as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": auth_settings.google_client_id,
                "client_secret": auth_settings.google_client_secret,
                "redirect_uri": auth_settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if token_response.status_code != 200:
        return RedirectResponse(_frontend("/login", error="token_exchange_failed"))

    raw_id_token = token_response.json().get("id_token")
    if not raw_id_token:
        return RedirectResponse(_frontend("/login", error="no_id_token"))

    # --- Verify the ID token (no userinfo round-trip needed) ---
    try:
        claims = await run_in_threadpool(
            google_id_token.verify_oauth2_token,
            raw_id_token,
            google_requests.Request(),
            auth_settings.google_client_id,
        )
    except ValueError:
        return RedirectResponse(_frontend("/login", error="invalid_id_token"))

    if not claims.get("email_verified"):
        return RedirectResponse(_frontend("/login", error="email_unverified"))

    google_sub = claims["sub"]
    email = claims["email"]
    name = claims.get("name") or email

    # --- Upsert user, keyed on the stable Google subject ---
    user = (
        await db.scalars(select(User).where(User.google_sub == google_sub))
    ).first()

    if user is None:
        # Google has verified this address, so linking to an existing
        # account with the same email is safe.
        user = (await db.scalars(select(User).where(User.email == email))).first()
        if user is not None:
            user.google_sub = google_sub
        else:
            user = User(
                name=name,
                email=email,
                google_sub=google_sub,
                password_hash=None,  # OAuth-only account
            )
            db.add(user)

    await db.flush()

    # --- Mint a single-use handoff code ---
    handoff = secrets.token_urlsafe(32)
    db.add(
        AuthHandoff(
            code_hash=sha256(handoff.encode()).hexdigest(),
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + HANDOFF_TTL,
        )
    )
    await db.commit()

    response = RedirectResponse(
        _frontend("/auth/callback", code=handoff, next=next_path)
    )
    response.delete_cookie(STATE_COOKIE, path=OAUTH_COOKIE_PATH)
    return response


# ---------------------------------------------------------------------------
# Step 3 — frontend trades the handoff code for the real JWT
# ---------------------------------------------------------------------------

class ExchangeRequest(BaseModel):
    code: str


@router.post("/exchange")
async def exchange_handoff(
    body: ExchangeRequest,
    db: AsyncSession = Depends(get_db),
):
    """Called by the frontend over CORS with the code from the redirect URL."""
    code_hash = sha256(body.code.encode()).hexdigest()

    handoff = (
        await db.scalars(
            select(AuthHandoff)
            .where(AuthHandoff.code_hash == code_hash)
            .with_for_update()
        )
    ).first()

    now = datetime.now(timezone.utc)
    if handoff is None or handoff.used_at is not None or handoff.expires_at < now:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired handoff code",
        )

    handoff.used_at = now
    user = await db.get(User, handoff.user_id)
    await db.commit()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )

    jwt_token = create_access_token(
        user_id=user.id, email=user.email, role=user.role
    )

    return JSONResponse(
        {
            "access_token": jwt_token,
            "token_type": "bearer",
            "user": {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
                "role": user.role.value,
                "created_at": user.created_at.isoformat(),
            },
        }
    )


@router.post("/logout")
async def logout():
    """
    JWTs are stateless — logout is handled client-side by discarding the
    token. This endpoint exists as a clear signal in the API and can be
    extended to maintain a server-side denylist if needed.
    """
    return JSONResponse({"message": "Successfully logged out. Discard your token."})