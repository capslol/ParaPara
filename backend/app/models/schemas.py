from typing import Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    # Ответ healthcheck
    status: str


class EchoRequest(BaseModel):
    # Запрос echo
    message: str


class EchoResponse(BaseModel):
    # Ответ echo
    message: str


class UserSettings(BaseModel):
    # Настройки пользователя
    notifications_enabled: bool = True
    language: str = "ru"


class UserProfile(BaseModel):
    # Профиль пользователя
    id: str = Field(..., description="Auth user id (UUID)")
    email: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    rating: float = 0.0
    settings: UserSettings = Field(default_factory=UserSettings)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UpdateUserProfileRequest(BaseModel):
    # Поля для обновления профиля
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    settings: Optional[UserSettings] = None
    rating: Optional[float] = None


