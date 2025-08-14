from typing import Optional

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    # Базовые поля пользователя
    username: Optional[str] = Field(default=None)
    full_name: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    rating: int = Field(default=0)
    settings_json: dict | None = Field(default=None)


class UserCreate(UserBase):
    # Для будущего использования (если понадобится ручное создание)
    pass


class UserUpdate(BaseModel):
    # Обновляемые поля
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    settings_json: Optional[dict] = None


class UserPublic(UserBase):
    # Публичная модель ответа
    id: str
    email: Optional[str] = None


