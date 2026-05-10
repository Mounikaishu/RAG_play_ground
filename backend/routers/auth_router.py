"""
Auth Router — Registration, Login, Password Change, Bulk Registration endpoints.
"""

from fastapi import APIRouter, Header, HTTPException
from typing import Optional

from models import RegisterRequest, LoginRequest, ChangePasswordRequest, BulkRegisterRequest
from auth import (
    hash_password, verify_password, create_token,
    get_current_user_from_token, DEFAULT_PASSWORD,
)
from database import (
    register_user, authenticate_user, get_user_profile,
    update_password,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register")
async def register(
    req: RegisterRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Register a new student or placement cell account.
    RESTRICTED: Only placement cell / exam cell can register students.
    Password is auto-assigned as the default password.
    Username = registration number (roll_no).
    """
    # Only placement_cell can register new users
    if not authorization:
        raise HTTPException(
            status_code=403,
            detail="Only the exam cell / placement cell can register students. Please contact your placement cell.",
        )
    user_data = get_current_user_from_token(authorization)
    if not user_data or user_data.get("role") != "placement_cell":
        raise HTTPException(
            status_code=403,
            detail="Only the exam cell / placement cell can register students.",
        )

    try:
        pw_hash = hash_password(DEFAULT_PASSWORD)
        user = register_user(
            name=req.name,
            roll_no=req.roll_no,
            department=req.department,
            password_hash=pw_hash,
            role=req.role,
            skills=req.skills,
            college_email=req.college_email,
            passing_out_year=req.passing_out_year,
        )
        return {
            "user": user,
            "message": f"✅ Student '{req.name}' registered. Username: '{req.roll_no}', Default password: '{DEFAULT_PASSWORD}'.",
            "default_password": DEFAULT_PASSWORD,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login")
async def login(req: LoginRequest):
    """Login with roll number (registration number) and password."""
    user = authenticate_user(req.roll_no)

    if not user:
        raise HTTPException(status_code=401, detail="Invalid roll number or password.")

    if not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid roll number or password.")

    # Create safe user (without password) for token
    safe_user = {k: v for k, v in user.items() if k != "password_hash"}
    token = create_token(safe_user)

    response = {"token": token, "user": safe_user, "message": "✅ Login successful."}

    # Nudge user to change default password
    if user.get("password_is_default", True):
        response["warning"] = "⚠️ You are using the default password. Please change it for security."

    return response


@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Change password for the authenticated user.
    Requires the old password and a new password (min 6 chars).
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required.")

    user_data = get_current_user_from_token(authorization)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    roll_no = user_data["roll_no"]

    # Verify old password
    user = authenticate_user(roll_no)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    if not verify_password(req.old_password, user.get("password_hash", "")):
        raise HTTPException(status_code=400, detail="Old password is incorrect.")

    # Hash and save new password
    new_hash = hash_password(req.new_password)
    success = update_password(roll_no, new_hash)

    if not success:
        raise HTTPException(status_code=500, detail="Failed to update password.")

    return {"message": "✅ Password changed successfully."}


@router.post("/bulk-register")
async def bulk_register(
    req: BulkRegisterRequest,
    authorization: Optional[str] = Header(None),
):
    """
    Bulk register students (placement cell only).
    All students get the same default password.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization required.")

    user_data = get_current_user_from_token(authorization)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    if user_data.get("role") != "placement_cell":
        raise HTTPException(status_code=403, detail="Only placement cell can bulk register students.")

    results = []
    success_count = 0
    fail_count = 0

    pw_hash = hash_password(DEFAULT_PASSWORD)

    for student in req.students:
        try:
            # Hash password individually for unique salts
            student_pw_hash = hash_password(DEFAULT_PASSWORD)
            user = register_user(
                name=student.name,
                roll_no=student.roll_no,
                department=student.department,
                password_hash=student_pw_hash,
                role="student",
                college_email=student.college_email,
                passing_out_year=student.passing_out_year,
            )
            results.append({
                "roll_no": student.roll_no,
                "name": student.name,
                "status": "success",
            })
            success_count += 1
        except ValueError as e:
            results.append({
                "roll_no": student.roll_no,
                "name": student.name,
                "status": "failed",
                "error": str(e),
            })
            fail_count += 1

    return {
        "message": f"✅ Bulk registration complete. {success_count} succeeded, {fail_count} failed.",
        "default_password": DEFAULT_PASSWORD,
        "results": results,
    }


@router.get("/me")
async def get_me(authorization: Optional[str] = Header(None)):
    """Get current user profile from JWT token."""
    if not authorization:
        raise HTTPException(status_code=401, detail="No authorization token provided.")

    user_data = get_current_user_from_token(authorization)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    profile = get_user_profile(user_data["roll_no"])
    if not profile:
        raise HTTPException(status_code=404, detail="User not found.")

    return {"user": profile}
