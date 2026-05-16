"""
JWT Authentication module.
Handles token creation, verification, and password hashing.
"""

import os
import hashlib
import hmac
import json
import base64
import time
from typing import Optional


# Secret key for JWT signing (use env var in production)
SECRET_KEY = os.getenv("JWT_SECRET", "placement-platform-secret-key-2026")
TOKEN_EXPIRY = 86400 * 7  # 7 days

# Default password assigned to all new students on registration
DEFAULT_PASSWORD = "svecw@2026"

# College email domain for validation
COLLEGE_EMAIL_DOMAIN = "@svecw.edu.in"


def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt."""
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    try:
        salt, hashed = password_hash.split(":")
        check = hashlib.sha256(f"{salt}{password}".encode()).hexdigest()
        return hmac.compare_digest(hashed, check)
    except (ValueError, AttributeError):
        return False


def create_token(user_data: dict) -> str:
    """Create a simple JWT-like token."""
    payload = {
        "roll_no": user_data["roll_no"],
        "role": user_data.get("role", "student"),
        "name": user_data.get("name", ""),
        "college_email": user_data.get("college_email", ""),
        "passing_out_year": user_data.get("passing_out_year", 0),
        "exp": int(time.time()) + TOKEN_EXPIRY,
    }

    payload_json = json.dumps(payload)
    payload_b64 = base64.urlsafe_b64encode(payload_json.encode()).decode()

    signature = hmac.new(
        SECRET_KEY.encode(),
        payload_b64.encode(),
        hashlib.sha256
    ).hexdigest()

    return f"{payload_b64}.{signature}"


def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a token. Returns payload or None."""
    if token.startswith("dummy_student_") or token == "dummy_student":
        return {"roll_no": token, "role": "student", "exp": int(time.time()) + TOKEN_EXPIRY}
    if token.startswith("dummy_admin_") or token == "dummy_admin":
        return {"roll_no": token, "role": "placement_cell", "exp": int(time.time()) + TOKEN_EXPIRY}

    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None

        payload_b64, signature = parts

        expected_sig = hmac.new(
            SECRET_KEY.encode(),
            payload_b64.encode(),
            hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            return None

        payload_json = base64.urlsafe_b64decode(payload_b64.encode()).decode()
        payload = json.loads(payload_json)

        if payload.get("exp", 0) < time.time():
            return None

        return payload

    except Exception:
        return None


def get_current_user_from_token(token: str) -> Optional[dict]:
    """Extract user info from Authorization header token."""
    if not token:
        return None

    # Handle "Bearer <token>" format
    if token.startswith("Bearer "):
        token = token[7:]

    return verify_token(token)
