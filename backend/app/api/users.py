from typing import Any, Dict

from fastapi import APIRouter, Depends

from ..core.auth import AuthenticatedUser, get_current_user
from ..models.schemas import UpdateUserProfileRequest, UserProfile, UserSettings
from ..services.profiles import ensure_profile_exists, update_profile


router = APIRouter(prefix="/users", tags=["users"])


def _to_user_profile(row: Dict[str, Any], current: AuthenticatedUser) -> UserProfile:
    # Маппинг БД-строки к API-схеме
    return UserProfile(
        id=current.id,
        email=current.email or row.get("email"),
        full_name=row.get("full_name"),
        avatar_url=row.get("avatar_url"),
        rating=float(row.get("rating") or 0.0),
        settings=UserSettings(**(row.get("settings") or {})),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


@router.get("/me", response_model=UserProfile)
async def get_me(current: AuthenticatedUser = Depends(get_current_user)) -> UserProfile:
    # Возвращаем профиль текущего пользователя; создаём при первом обращении
    row = ensure_profile_exists(current.id, current.email)
    return _to_user_profile(row, current)


@router.put("/me", response_model=UserProfile)
async def update_me(
    payload: UpdateUserProfileRequest,
    current: AuthenticatedUser = Depends(get_current_user),
) -> UserProfile:
    # Обновляем профиль пользователя (только разрешённые поля)
    update_values: Dict[str, Any] = {}
    if payload.full_name is not None:
        update_values["full_name"] = payload.full_name
    if payload.avatar_url is not None:
        update_values["avatar_url"] = payload.avatar_url
    if payload.settings is not None:
        update_values["settings"] = payload.settings.model_dump()
    if payload.rating is not None:
        update_values["rating"] = float(payload.rating)

    if not update_values:
        row = ensure_profile_exists(current.id, current.email)
        return _to_user_profile(row, current)

    _ = ensure_profile_exists(current.id, current.email)
    row = update_profile(current.id, update_values)
    return _to_user_profile(row, current)


