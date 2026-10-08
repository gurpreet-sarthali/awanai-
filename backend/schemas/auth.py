from pydantic import EmailStr, Field

from .common import APIModel


class RegisterRequest(APIModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(APIModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthUserResponse(APIModel):
    id: str
    email: str
    name: str
    profile_picture_url: str | None = None
    is_active: bool
    is_admin: bool = False
    created_at: str
    updated_at: str
    last_login_at: str | None = None


class AuthTokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


class MessageResponse(APIModel):
    message: str


class GoogleAuthStatusResponse(APIModel):
    configured: bool
    authorization_url: str | None = None


class GoogleCallbackRequest(APIModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=20, max_length=512)
