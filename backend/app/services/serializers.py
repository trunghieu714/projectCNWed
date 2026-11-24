"""Chuyển entity -> dict JSON theo tên trường của đặc tả restful_api (kèm tên trường cũ cho frontend)."""
from datetime import datetime
from typing import Any, Dict, Optional
from ..models.entities import Submission, User, UserRole

def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None

def role_label(user: Optional[User]) -> str:
    if not user:
        return ""
    return {UserRole.COACH: "GV", UserRole.STUDENT: "HV", UserRole.ADMIN: "ADMIN"}.get(user.role, "HV")

def user_brief(user: Optional[User]) -> Optional[Dict[str, Any]]:
    if not user:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "name": user.full_name or user.username,
        "full_name": user.full_name,
        "avatar": user.avatar_url,
        "avatar_url": user.avatar_url,
        "role": user.role.value,
        "role_label": role_label(user),
    }

def submission_brief(sub: Optional[Submission]) -> Optional[Dict[str, Any]]:
    if not sub:
        return None
    return {
        "id": sub.id,
        "exercise_id": sub.exercise_id,
        "student_id": sub.student_id,
        "status": sub.status.value if hasattr(sub.status, "value") else sub.status,
        "score": sub.score,
        "feedback_text": sub.feedback_text,
        "fused_video_url": sub.fused_video_url,
        "report_html_url": sub.report_html_url,
        "error_message": sub.error_message,
        "student_video_url": sub.student_video_url,
        "created_at": iso(sub.created_at),
    }
