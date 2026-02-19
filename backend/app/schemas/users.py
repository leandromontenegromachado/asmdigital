from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "viewer"
    is_active: bool = True


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class UserPasswordReset(BaseModel):
    password: str
