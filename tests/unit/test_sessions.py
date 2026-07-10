"""Unit tests for HMAC session tokens."""

import time
import uuid

from backend.auth.sessions import (
    SESSION_PREFIX,
    _sign,
    create_session_token,
    verify_session_token,
)


def test_session_roundtrip():
    """A freshly minted token verifies back to the same user id."""
    user_id = uuid.uuid4()
    token = create_session_token(user_id)
    assert token.startswith(SESSION_PREFIX)
    assert verify_session_token(token) == user_id


def test_tampered_token_rejected():
    """Changing the payload or signature invalidates the token."""
    token = create_session_token(uuid.uuid4())
    assert verify_session_token(token[:-4] + "0000") is None
    other = str(uuid.uuid4())
    parts = token[len(SESSION_PREFIX) :].rsplit(".", 2)
    forged = f"{SESSION_PREFIX}{other}.{parts[1]}.{parts[2]}"
    assert verify_session_token(forged) is None


def test_expired_token_rejected():
    """A token with a past expiry fails verification even with a valid signature."""
    user_id = uuid.uuid4()
    past = int(time.time()) - 10
    payload = f"{user_id}.{past}"
    token = f"{SESSION_PREFIX}{payload}.{_sign(payload)}"
    assert verify_session_token(token) is None


def test_garbage_tokens_rejected():
    """Malformed inputs never verify."""
    assert verify_session_token("") is None
    assert verify_session_token("cryo_sk_notasession") is None
    assert verify_session_token(SESSION_PREFIX + "junk") is None
