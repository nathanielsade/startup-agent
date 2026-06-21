import jwt
from fastapi import Depends, Header, HTTPException

from api.deps import get_settings


def get_current_user(authorization: str | None = Header(default=None),
                     settings=Depends(get_settings)) -> str:
    """Verify the Supabase auth JWT (HS256) and return the user id (the `sub` claim).

    Raises 401 on a missing/malformed/invalid/expired token.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    if not settings.supabase_jwt_secret:
        raise HTTPException(status_code=503, detail="Auth not configured")
    try:
        payload = jwt.decode(token, settings.supabase_jwt_secret,
                             algorithms=["HS256"], audience="authenticated")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return user_id
