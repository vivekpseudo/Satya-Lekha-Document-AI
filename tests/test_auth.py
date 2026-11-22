import time

from app.auth import (
    TOKEN_TTL_SECONDS, create_token, hash_password, is_valid_email, normalize_email, read_token, verify_password,
)


def test_password_round_trip_and_salting():
    stored = hash_password("correct horse")
    assert verify_password("correct horse", stored)
    assert not verify_password("wrong", stored)
    assert stored != hash_password("correct horse")  # fresh salt each time
    assert not verify_password("x", "garbage")


def test_token_round_trip_expiry_and_tampering():
    token = create_token(42)
    assert read_token(token) == 42
    assert read_token(token, now=time.time() + TOKEN_TTL_SECONDS + 5) is None
    body, sig = token.split(".")
    assert read_token(f"{body}.{sig[:-2]}xx") is None
    assert read_token("not-a-token") is None
    assert read_token("") is None


def test_email_checks():
    assert normalize_email("  A@B.com ") == "a@b.com"
    assert is_valid_email("a@b.co")
    assert not is_valid_email("a@b")
    assert not is_valid_email("a b@c.com")
