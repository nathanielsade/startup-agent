import jwt
from fastapi import Depends, Header, HTTPException

from api.deps import get_settings

# Used in local dev / tests when no Supabase JWT secret is configured. Cloud always
# sets supabase_jwt_secret, so real auth is enforced there.
DEV_USER_ID = "00000000-0000-0000-0000-000000000000"


def get_current_user(authorization: str | None = Header(default=None),
                     settings=Depends(get_settings)) -> str:
    """Verify the Supabase auth JWT (HS256) and return the user id (the `sub` claim).

    When no `supabase_jwt_secret` is configured (local dev), returns a fixed dev user
    so the app runs without tokens. With a secret set (cloud), a valid bearer JWT is
    required; missing/invalid/expired → 401.
    """
    if not settings.supabase_jwt_secret:
        return DEV_USER_ID
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, settings.supabase_jwt_secret,
                             algorithms=["HS256"], audience="authenticated")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return user_id
