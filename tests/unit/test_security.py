from __future__ import annotations

from shared.taskflow_common import decrypt_text, encrypt_text, sign_token, verify_token


def test_token_roundtrip() -> None:
    token = sign_token({"sub": "USR-1", "role": "admin"}, secret="secret")
    payload = verify_token(token, secret="secret")
    assert payload is not None
    assert payload["sub"] == "USR-1"


def test_encrypt_roundtrip() -> None:
    cipher = encrypt_text("important", key="k")
    plain = decrypt_text(cipher, key="k")
    assert plain == "important"
