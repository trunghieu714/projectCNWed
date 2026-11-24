from typing import Optional, List
from sqlalchemy.orm import Session
from ..models.entities import User, UserRole
from ..core.security import get_password_hash

class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[User]:
        return self.db.query(User).filter(User.id == user_id).first()

    def get_by_username(self, username: str) -> Optional[User]:
        return self.db.query(User).filter(User.username == username).first()

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.query(User).filter(User.email == email).first()

    def get_by_phone(self, phonenumber: str) -> Optional[User]:
        return self.db.query(User).filter(User.phonenumber == phonenumber).first()

    def get_by_username_or_email(self, identifier: str) -> Optional[User]:
        return self.db.query(User).filter(
            (User.username == identifier) | 
            (User.email == identifier) | 
            (User.phonenumber == identifier)
        ).first()

    def create(
        self,
        username: str,
        email: Optional[str] = None,
        password: str = "",
        full_name: Optional[str] = None,
        phonenumber: Optional[str] = None,
        height: Optional[float] = None,
        avatar_url: Optional[str] = None,
        role: UserRole = UserRole.STUDENT
    ) -> User:
        user = User(
            username=username,
            email=email or f"{username}@local.vn",
            phonenumber=phonenumber,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            height=height,
            avatar_url=avatar_url,
            role=role
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update_profile(
        self,
        user_id: int,
        username: Optional[str] = None,
        full_name: Optional[str] = None,
        height: Optional[float] = None,
        avatar_url: Optional[str] = None
    ) -> Optional[User]:
        user = self.get_by_id(user_id)
        if not user:
            return None
        if username is not None:
            user.username = username
        if full_name is not None:
            user.full_name = full_name
        if height is not None:
            user.height = height
        if avatar_url is not None:
            user.avatar_url = avatar_url
        self.db.commit()
        self.db.refresh(user)
        return user
