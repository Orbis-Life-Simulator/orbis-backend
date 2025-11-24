from pydantic import BaseModel, EmailStr, Field
from .types import PyObjectId


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: PyObjectId = Field(..., alias="_id")

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
