import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from config import auth_settings
from models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_access_token(user_id: uuid.UUID, email: str, role: UserRole) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=auth_settings.jwt_expire_minutes)
    payload = {
        "sub":   str(user_id),
        "email": email,
        "role":  role.value,
        "exp":   expire,
    }
    return jwt.encode(payload, auth_settings.jwt_secret_key, algorithm=auth_settings.jwt_algorithm)


# ---------------------------------------------------------------------------
# Token decoding
# ---------------------------------------------------------------------------

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            auth_settings.jwt_secret_key,
            algorithms=[auth_settings.jwt_algorithm],
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Base dependency — resolves the current user from the Bearer token.
# Inject your real get_db when wiring this into routes.
# ---------------------------------------------------------------------------

def make_get_current_user(get_db):
    """
    Factory that binds get_current_user to a specific get_db dependency.

    Usage in a router:
        from db.session import get_db
        from jwt import make_get_current_user
        get_current_user = make_get_current_user(get_db)
    """
    async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
                headers={"WWW-Authenticate": "Bearer"},
            )
        payload = decode_access_token(token)
        user = await db.get(User, uuid.UUID(payload["sub"]))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )
        return user

    return get_current_user


# ---------------------------------------------------------------------------
# Role dependencies
# ---------------------------------------------------------------------------

def require_role(*roles: UserRole):
    """
    Returns a FastAPI dependency that enforces one of the given roles.

    Usage:
        from db.session import get_db
        from jwt import require_role
        from models.user import UserRole

        get_current_user = make_get_current_user(get_db)
        require_admin   = require_role(UserRole.admin)

        @router.post("/")
        async def create(..., _: User = Depends(require_admin(get_current_user))):
            ...
    """
    def dependency(get_current_user):
        async def check(current_user: User = Depends(get_current_user)) -> User:
            if current_user.role not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied. Required role: {', '.join(r.value for r in roles)}",
                )
            return current_user
        return check
    return dependency


# Convenience aliases
require_admin   = require_role(UserRole.admin)
require_student = require_role(UserRole.student, UserRole.admin)  # admins can do anything students can