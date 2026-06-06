import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserBase(_OrmBase):
    name:  str
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserUpdate(_OrmBase):
    name:     Optional[str]      = None
    email:    Optional[EmailStr] = None
    password: Optional[str]      = None


class User(UserBase):
    id:         uuid.UUID
    created_at: datetime