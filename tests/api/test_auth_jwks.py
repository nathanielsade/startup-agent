import time

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from api import auth, deps
from api.auth import get_current_user
from startup_agent.config.settings import Settings

SUPABASE_URL = "https://example.supabase.co"

# An EC P-256 key pair, mirroring Supabase's "ECC (P-256)" signing keys.
_priv = ec.generate_private_key(ec.SECP256R1())


class _FakeSigningKey:
    key = _priv.public_key()


class _FakeJWKSClient:
    def get_signing_key_from_jwt(self, token):
        return _FakeSigningKey()


app = FastAPI()


@app.get("/whoami")
def whoami(user: str = Depends(get_current_user)) -> dict:
    return {"user_id": user}


app.dependency_overrides[deps.get_settings] = lambda: Settings(supabase_url=SUPABASE_URL)
client = TestClient(app)


def _es256_token(sub="user-xyz", aud="authenticated", key=_priv, exp_delta=3600):
    payload = {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_delta}
    return jwt.encode(payload, key, algorithm="ES256")


def setup_function(_):
    # avoid real network: hand the verifier our in-memory public key
    auth._jwks_clients[SUPABASE_URL] = _FakeJWKSClient()


def teardown_function(_):
    auth._jwks_clients.clear()


def test_valid_es256_token_returns_user_id():
    r = client.get("/whoami", headers={"Authorization": f"Bearer {_es256_token('abc')}"})
    assert r.status_code == 200 and r.json()["user_id"] == "abc"


def test_token_signed_by_other_key_401():
    other = ec.generate_private_key(ec.SECP256R1())
    bad = _es256_token(key=other)
    assert client.get("/whoami", headers={"Authorization": f"Bearer {bad}"}).status_code == 401


def test_wrong_audience_401():
    wrong = _es256_token(aud="some-other-aud")
    assert client.get("/whoami", headers={"Authorization": f"Bearer {wrong}"}).status_code == 401


def test_missing_header_401():
    assert client.get("/whoami").status_code == 401
