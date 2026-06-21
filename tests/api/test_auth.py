import time

import jwt
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api import deps
from api.auth import get_current_user
from startup_agent.config.settings import Settings

SECRET = "test-jwt-secret"

app = FastAPI()


@app.get("/whoami")
def whoami(user: str = Depends(get_current_user)) -> dict:
    return {"user_id": user}


app.dependency_overrides[deps.get_settings] = lambda: Settings(supabase_jwt_secret=SECRET)
client = TestClient(app)


def _token(sub="user-123", aud="authenticated", secret=SECRET, exp_delta=3600):
    payload = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_delta}
    return jwt.encode(payload, secret, algorithm="HS256")


def test_valid_token_returns_user_id():
    r = client.get("/whoami", headers={"Authorization": f"Bearer {_token('abc')}"})
    assert r.status_code == 200 and r.json()["user_id"] == "abc"


def test_missing_header_401():
    assert client.get("/whoami").status_code == 401


def test_garbage_token_401():
    assert client.get("/whoami", headers={"Authorization": "Bearer not.a.jwt"}).status_code == 401


def test_wrong_secret_401():
    bad = _token(secret="someone-elses-secret")
    assert client.get("/whoami", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_expired_token_401():
    expired = _token(exp_delta=-10)
    assert client.get("/whoami", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_wrong_audience_401():
    wrong = _token(aud="some-other-aud")
    assert client.get("/whoami", headers={"Authorization": f"Bearer {wrong}"}).status_code == 401
