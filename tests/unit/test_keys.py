"""Unit tests for API key generation, hashing, and header extraction."""

from backend.auth.keys import (
    KEY_PREFIX,
    extract_key_from_request,
    generate_api_key,
    hash_key,
)


class FakeRequest:
    """Minimal stand-in exposing .headers like a Starlette Request."""

    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


def test_generate_api_key_format():
    """Keys start with cryo_sk_, are long, and the prefix matches the key start."""
    full_key, key_hash, prefix = generate_api_key()
    assert full_key.startswith(KEY_PREFIX)
    assert len(full_key) > 40
    assert prefix == full_key[:12]
    assert len(key_hash) == 64


def test_generate_api_key_unique():
    """Two generated keys never collide."""
    k1, h1, _ = generate_api_key()
    k2, h2, _ = generate_api_key()
    assert k1 != k2
    assert h1 != h2


def test_hash_key_deterministic():
    """Hashing the same key twice yields the same digest."""
    assert hash_key("cryo_sk_abc") == hash_key("cryo_sk_abc")
    assert hash_key("cryo_sk_abc") != hash_key("cryo_sk_abd")


def test_extract_key_bearer():
    """Authorization: Bearer takes priority."""
    req = FakeRequest({"authorization": "Bearer cryo_sk_test123"})
    assert extract_key_from_request(req) == "cryo_sk_test123"


def test_extract_key_x_api_key():
    """Falls back to x-api-key header."""
    req = FakeRequest({"x-api-key": "cryo_sk_test456"})
    assert extract_key_from_request(req) == "cryo_sk_test456"


def test_extract_key_missing():
    """No credentials → None."""
    assert extract_key_from_request(FakeRequest({})) is None
    assert extract_key_from_request(FakeRequest({"authorization": "Bearer "})) is None
