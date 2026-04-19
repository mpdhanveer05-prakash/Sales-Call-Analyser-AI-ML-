from uuid import UUID

from pydantic import BaseModel, EmailStr
from app.models.user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: "UserOut"


class RefreshRequest(BaseModel):
    refresh_token: str


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole

    model_config = {"from_attributes": True}


TokenResponse.model_rebuild()
