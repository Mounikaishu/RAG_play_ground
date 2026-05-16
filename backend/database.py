"""
Simple JSON-file-based user database.
Stores student and placement cell accounts in users.json.
No external database dependency needed.
"""

import json
import os
from datetime import datetime
from typing import Optional

USERS_FILE = os.path.join(os.path.dirname(__file__), "users.json")


def _load_users() -> dict:
    """Load users from JSON file."""
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_users(users: dict):
    """Save users to JSON file."""
    with open(USERS_FILE, "w") as f:
        json.dump(users, f, indent=2)


def compute_year_of_study(passing_out_year: int) -> int:
    """
    Calculate current year of study from passing out year.
    Assumes 4-year degree. Academic year starts in June.
    e.g., passing_out_year=2028, current=May 2026 → 2nd year
    """
    now = datetime.now()
    current_year = now.year
    current_month = now.month

    # Academic year: June to May
    academic_year = current_year if current_month >= 6 else current_year - 1

    # Years remaining = passing_out_year - academic_year
    # Year of study = 4 - years_remaining + 1
    years_remaining = passing_out_year - academic_year
    year_of_study = 4 - years_remaining + 1

    return max(1, min(4, year_of_study))


def register_user(name: str, roll_no: str, department: str,
                   password_hash: str, role: str = "student",
                   skills: list = None, college_email: str = "",
                   passing_out_year: int = 0) -> dict:
    """Register a new user. Returns user dict or raises ValueError."""
    users = _load_users()

    if roll_no in users:
        raise ValueError(f"User with roll number '{roll_no}' already exists.")

    year_of_study = compute_year_of_study(passing_out_year) if passing_out_year else 0

    user = {
        "name": name,
        "roll_no": roll_no,
        "department": department,
        "password_hash": password_hash,
        "role": role,
        "skills": skills or [],
        "college_email": college_email,
        "passing_out_year": passing_out_year,
        "year_of_study": year_of_study,
        "password_is_default": True,
        "resume_uploaded": False,
        "conversations": {},
    }

    users[roll_no] = user
    _save_users(users)
    return _safe_user(user)


def get_user(roll_no: str) -> Optional[dict]:
    """Get user by roll number."""
    if roll_no.startswith("dummy_student_") or roll_no == "dummy_student":
        return {
            "name": "Student",
            "roll_no": roll_no,
            "department": "Not Specified",
            "password_hash": "",
            "role": "student",
            "skills": [],
            "college_email": f"{roll_no}@svecw.edu.in",
            "passing_out_year": 2026,
            "year_of_study": 3,
            "password_is_default": False,
            "resume_uploaded": False,
            "conversations": {},
        }
    if roll_no.startswith("dummy_admin_") or roll_no == "dummy_admin":
        return {
            "name": "Placement Cell",
            "roll_no": "dummy_admin",
            "department": "Admin",
            "password_hash": "",
            "role": "placement_cell",
            "skills": [],
            "college_email": "admin@svecw.edu.in",
            "passing_out_year": 0,
            "year_of_study": 0,
            "password_is_default": False,
            "resume_uploaded": False,
            "conversations": {},
        }

    users = _load_users()
    user = users.get(roll_no)
    if user and user.get("passing_out_year"):
        # Recompute year of study dynamically
        user["year_of_study"] = compute_year_of_study(user["passing_out_year"])
    return user


def authenticate_user(roll_no: str) -> Optional[dict]:
    """Get user for authentication (includes password hash)."""
    return get_user(roll_no)


def get_user_profile(roll_no: str) -> Optional[dict]:
    """Get user profile without sensitive fields."""
    user = get_user(roll_no)
    if user:
        return _safe_user(user)
    return None


def update_user_profile(roll_no: str, updates: dict) -> Optional[dict]:
    """Update user profile fields."""
    users = _load_users()
    if roll_no not in users:
        return None

    for key, value in updates.items():
        if key not in ("password_hash", "roll_no"):  # protect sensitive fields
            users[roll_no][key] = value

    _save_users(users)
    return _safe_user(users[roll_no])


def update_password(roll_no: str, new_password_hash: str) -> bool:
    """Update a user's password and mark as non-default."""
    users = _load_users()
    if roll_no not in users:
        return False

    users[roll_no]["password_hash"] = new_password_hash
    users[roll_no]["password_is_default"] = False
    _save_users(users)
    return True


def get_all_students() -> list:
    """Get all student profiles (for placement cell)."""
    users = _load_users()
    students = []
    for u in users.values():
        if u.get("role") == "student":
            # Recompute year of study
            if u.get("passing_out_year"):
                u["year_of_study"] = compute_year_of_study(u["passing_out_year"])
            students.append(_safe_user(u))
    return students


def get_students_by_year(passing_out_year: int) -> list:
    """Get all students with a specific passing out year."""
    users = _load_users()
    students = []
    for u in users.values():
        if u.get("role") == "student" and u.get("passing_out_year") == passing_out_year:
            u["year_of_study"] = compute_year_of_study(passing_out_year)
            students.append(_safe_user(u))
    return students


def get_available_years() -> list:
    """Get all distinct passing out years from registered students."""
    users = _load_users()
    years = set()
    for u in users.values():
        if u.get("role") == "student" and u.get("passing_out_year"):
            years.add(u["passing_out_year"])
    return sorted(years)


def _safe_user(user: dict) -> dict:
    """Return user dict without password hash."""
    return {k: v for k, v in user.items() if k != "password_hash"}
