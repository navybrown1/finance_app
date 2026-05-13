from __future__ import annotations

import base64
import hashlib
import hmac
import os


def hash_password(secret: str) -> str:
    if not secret:
        raise ValueError("Secret cannot be empty.")
    salt = os.urandom(16)
    rounds = 210_000
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, rounds)
    return "pbkdf2_sha256${}${}${}".format(
        rounds,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(secret: str, stored_hash: str) -> bool:
    try:
        algo, rounds_s, salt_s, digest_s = stored_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac("sha256", secret.encode(), base64.b64decode(salt_s), int(rounds_s))
        return hmac.compare_digest(actual, base64.b64decode(digest_s))
    except Exception:
        return False
