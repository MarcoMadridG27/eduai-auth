from pydantic import BaseModel, EmailStr
from typing import Optional
from typing import Dict, Any
from datetime import datetime


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleLogin(BaseModel):
    id_token: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    provider: str

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SessionCreate(BaseModel):
    user_id: str
    session_data: Dict[str, Any]


class SessionOut(BaseModel):
    id: int
    user_id: str
    session_data: Dict[str, Any]
    created_at: datetime

    class Config:
        orm_mode = True
