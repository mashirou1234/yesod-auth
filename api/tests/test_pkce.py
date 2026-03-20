"""Tests for PKCE helpers."""

import pytest

from app.auth.pkce import (
    generate_code_challenge,
    verify_code_challenge,
)


def test_generate_code_challenge_accepts_min_length_verifier():
    verifier = "a" * 43

    challenge = generate_code_challenge(verifier)

    assert challenge
    assert verify_code_challenge(verifier, challenge) is True


def test_generate_code_challenge_accepts_max_length_verifier():
    verifier = "a" * 128

    challenge = generate_code_challenge(verifier)

    assert challenge
    assert verify_code_challenge(verifier, challenge) is True


@pytest.mark.parametrize(
    ("verifier", "expected_message"),
    [
        ("a" * 42, "code_verifier must be between 43 and 128 characters"),
        ("a" * 129, "code_verifier must be between 43 and 128 characters"),
    ],
)
def test_generate_code_challenge_rejects_out_of_range_length(
    verifier: str, expected_message: str
):
    with pytest.raises(ValueError, match=expected_message):
        generate_code_challenge(verifier)
