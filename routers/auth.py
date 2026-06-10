import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db

from config import auth_settings
from jwt import create_access_token
from models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_AUTH_URL    = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL   = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"

SCOPES = "openid email profile"

@router.get("/google/login")
async def google_login():
    """Redirect the browser to Google's OAuth2 consent screen."""
    params = {
        "client_id":     auth_settings.google_client_id,
        "redirect_uri":  auth_settings.google_redirect_uri,
        "response_type": "code",
        "scope":         SCOPES,
        "access_type":   "offline",   # request a refresh token
        "prompt":        "select_account",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url=f"{GOOGLE_AUTH_URL}?{query}")

@router.get("/google/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    """
    Exchange the authorisation code for tokens, fetch the user's Google
    profile, upsert the user in the database, and return a JWT alongside
    the user details.
    """
    # --- Exchange code for tokens ---
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     auth_settings.google_client_id,
                "client_secret": auth_settings.google_client_secret,
                "redirect_uri":  auth_settings.google_redirect_uri,
                "grant_type":    "authorization_code",
            },
        )

    if token_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to exchange authorisation code with Google",
        )

    token_data    = token_response.json()
    access_token  = token_data.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No access token returned by Google",
        )

    # --- Fetch user profile from Google ---
    async with httpx.AsyncClient() as client:
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to fetch user info from Google",
        )

    google_user = userinfo_response.json()
    email       = google_user.get("email")
    name        = google_user.get("name") or email

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google account did not return an email address",
        )

    # --- Upsert user ---
    result = await db.scalars(select(User).where(User.email == email))
    user   = result.first()

    if not user:
        user = User(
            name=name,
            email=email,
            password_hash="",   # no password for OAuth users
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    # --- Issue JWT ---
    jwt_token = create_access_token(user_id=user.id, email=user.email, role=user.role)

    return JSONResponse({
        "access_token": jwt_token,
        "token_type":   "bearer",
        "user": {
            "id":         str(user.id),
            "name":       user.name,
            "email":      user.email,
            "role":       user.role.value,   
            "created_at": user.created_at.isoformat(),
        },
    })


# ---------------------------------------------------------------------------
# Logout — client-side: just advise discarding the token
# ---------------------------------------------------------------------------

@router.post("/logout")
async def logout():
    """
    JWTs are stateless — logout is handled client-side by discarding the
    token. This endpoint exists as a clear signal in the API and can be
    extended to maintain a server-side denylist if needed.
    """
    return JSONResponse({"message": "Successfully logged out. Discard your token."})