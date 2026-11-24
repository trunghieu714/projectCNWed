from typing import Optional, List
from sqlalchemy.orm import Session
from ..models.entities import Exercise

class ExerciseRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, exercise_id: int) -> Optional[Exercise]:
        return self.db.query(Exercise).filter(Exercise.id == exercise_id).first()

    def get_all(self, category: Optional[str] = None, skip: int = 0, limit: int = 50) -> List[Exercise]:
        query = self.db.query(Exercise)
        if category:
            query = query.filter(Exercise.category == category)
        return query.offset(skip).limit(limit).all()

    def create(self, title: str, category: str, coach_video_url: str, created_by: int, description: Optional[str] = None) -> Exercise:
        exercise = Exercise(
            title=title,
            category=category,
            coach_video_url=coach_video_url,
            created_by=created_by,
            description=description
        )
        self.db.add(exercise)
        self.db.commit()
        self.db.refresh(exercise)
        return exercise
