from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ....core.database import get_db
from ....models.entities import User, UserRole
from ....schemas.course import CourseCreate, CourseResponse, CourseMemberResponse
from ....schemas.response import ApiResponse, ErrorCodes
from ....repositories.course_repository import CourseRepository
from ...deps import get_current_user, get_current_coach

router = APIRouter()

@router.post("/", response_model=ApiResponse[CourseResponse], status_code=status.HTTP_201_CREATED)
def create_course(
    course_in: CourseCreate,
    current_coach: User = Depends(get_current_coach),
    db: Session = Depends(get_db)
):
    """
    Giáo viên tạo khóa học trực tuyến:
    - Ràng buộc: Mỗi Giáo viên chỉ quản lý tối đa 01 khóa học (Slide 25 & 27).
    - Tối đa 500 học viên.
    """
    repo = CourseRepository(db)
    try:
        course = repo.create(
            teacher_id=current_coach.id,
            title=course_in.title,
            description=course_in.description,
            max_students=course_in.max_students
        )
        return ApiResponse(code=ErrorCodes.OK, message="Tạo khóa học thành công.", data=course)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": ErrorCodes.ACTION_DONE_PREVIOUSLY, "message": str(e)}
        )

@router.get("/", response_model=ApiResponse[List[CourseResponse]])
def get_courses(
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Lấy danh sách các lớp học trực tuyến."""
    repo = CourseRepository(db)
    courses = repo.get_all(skip=skip, limit=limit)
    return ApiResponse(code=ErrorCodes.OK, message="OK", data=courses)

@router.get("/{course_id}", response_model=ApiResponse[CourseResponse])
def get_course_detail(course_id: int, db: Session = Depends(get_db)):
    repo = CourseRepository(db)
    course = repo.get_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCodes.PARAMETER_VALUE_INVALID, "message": "Không tìm thấy khóa học."}
        )
    return ApiResponse(code=ErrorCodes.OK, message="OK", data=course)

@router.post("/{course_id}/enroll", response_model=ApiResponse[CourseMemberResponse])
def enroll_course(
    course_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Học viên gửi yêu cầu tham gia lớp học; giáo viên duyệt qua set_approve_enrollment."""
    from ....services.relationship_service import CourseService
    repo = CourseRepository(db)
    course = repo.get_by_id(course_id)
    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": ErrorCodes.PARAMETER_VALUE_INVALID, "message": "Không tìm thấy khóa học."}
        )
    member = CourseService(db).request(current_user, course)
    return ApiResponse(code=ErrorCodes.OK, message="Đã gửi yêu cầu tham gia, chờ giáo viên duyệt.", data=member)
