import jwt
from fastapi import Depends, Header, HTTPException
from jwt import PyJWKClient

from api.deps import get_settings

# Used in local dev / tests when neither Supabase setting is configured. Cloud sets
# supabase_url (modern asymmetric verification) so real auth is enforced there.
DEV_USER_ID = "00000000-0000-0000-0000-000000000000"
_AUDIENCE = "authenticated"
_ASYMMETRIC_ALGS = ["ES256", "RS256"]  # Supabase JWT signing keys (ECC / RSA)

# Cache one JWKS client per project URL — it fetches and caches the public keys.
_jwks_clients: dict[str, PyJWKClient] = {}


def _jwks_client(supabase_url: str) -> PyJWKClient:
    client = _jwks_clients.get(supabase_url)
    if client is None:
        url = f"{supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        client = PyJWKClient(url)
        _jwks_clients[supabase_url] = client
    return client


def _decode(token: str, settings) -> dict:
    """Verify a Supabase access token.

    Modern projects sign with asymmetric keys (ECC/RSA) → verify against the public
    keys at the project's JWKS endpoint. Older projects / tests use a shared HS256
    secret. `supabase_url` takes precedence when both are set.
    """
    if settings.supabase_url:
        key = _jwks_client(settings.supabase_url).get_signing_key_from_jwt(token).key
        return jwt.decode(token, key, algorithms=_ASYMMETRIC_ALGS, audience=_AUDIENCE)
    return jwt.decode(token, settings.supabase_jwt_secret,
                      algorithms=["HS256"], audience=_AUDIENCE)


def get_current_user(authorization: str | None = Header(default=None),
                     settings=Depends(get_settings)) -> str:
    """Verify the Supabase auth JWT and return the user id (the `sub` claim).

    No Supabase config (local dev) → a fixed dev user, so the app runs without
    tokens. Otherwise a valid bearer JWT is required; missing/invalid/expired → 401.
    """
    if not settings.supabase_url and not settings.supabase_jwt_secret:
        return DEV_USER_ID
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        payload = _decode(token, settings)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from None
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject")
    return user_id
