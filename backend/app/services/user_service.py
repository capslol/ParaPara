from __future__ import annotations

from typing import Optional
from uuid import uuid4

from app.core.supabase import get_supabase_client
from app.schemas.user import UserPublic, UserUpdate
from fastapi import HTTPException


async def _get_auth_user_by_jwt(jwt_token: str) -> Optional[dict]:
    # Получаем информацию о пользователе из Supabase Auth по JWT
    # Клиент supabase-py не имеет прямого метода verify, используем REST
    supabase = get_supabase_client()
    rest = supabase.postgrest
    # Обходимся без verify: берем пользователя из `auth.get_user()` через admin, если возможно
    try:
        user_resp = supabase.auth.get_user(jwt_token)
        if user_resp and user_resp.user:
            user = user_resp.user
            return {
                "id": user.id,
                "email": user.email,
                "user_metadata": user.user_metadata or {},
            }
    except Exception:
        return None
    return None


async def get_or_create_user_by_jwt(jwt_token: str) -> Optional[UserPublic]:
    # По данным Auth ищем/создаем пользователя в таблице app.users
    auth_user = await _get_auth_user_by_jwt(jwt_token)
    if not auth_user:
        return None

    user_id = auth_user["id"]
    email = auth_user.get("email")
    metadata = auth_user.get("user_metadata", {})

    supabase = get_supabase_client()
    # Включаем контекст пользователя для RLS, если клиент создан с anon key
    try:
        supabase.postgrest.auth(jwt_token)
    except Exception:
        pass

    # Пробуем найти пользователя
    result = (
        supabase
        .table("users")
        .select("*")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    row = getattr(result, "data", None)

    if not row:
        # Создаем нового
        payload = {
            "id": user_id,
            "email": email,
            "username": metadata.get("username"),
            "full_name": metadata.get("full_name"),
            "avatar_url": metadata.get("avatar_url"),
            "rating": 0,
            "settings_json": {},
        }
        # В supabase-py после insert безопаснее сделать отдельный select
        insert_res = (
            supabase
            .table("users")
            .insert(payload)
            .execute()
        )
        # Затем читаем созданную строку по id
        sel = (
            supabase
            .table("users")
            .select("*")
            .eq("id", user_id)
            .single()
            .execute()
        )
        row = getattr(sel, "data", None)

    return _row_to_user_public(row)


async def update_user_profile(user_id: str, patch: UserUpdate) -> UserPublic:
    # Обновляем профиль
    supabase = get_supabase_client()
    update_payload = {k: v for k, v in patch.model_dump(exclude_unset=True).items()}
    if not update_payload:
        # Нечего обновлять – вернем текущее
        existing = supabase.table("users").select("*").eq("id", user_id).single().execute().data
        return _row_to_user_public(existing)

    updated = (
        supabase.table("users")
        .update(update_payload)
        .eq("id", user_id)
        .select("*")
        .single()
        .execute()
        .data
    )
    return _row_to_user_public(updated)


def _row_to_user_public(row: dict) -> UserPublic:
    return UserPublic(
        id=row.get("id"),
        email=row.get("email"),
        username=row.get("username"),
        full_name=row.get("full_name"),
        avatar_url=row.get("avatar_url"),
        rating=row.get("rating", 0),
        settings_json=row.get("settings_json"),
    )


# Telegram-based auth helpers
async def get_or_create_user_by_telegram(tg_id: int | str, username: str | None, first_name: str | None, photo_url: str | None) -> UserPublic:
    supabase = get_supabase_client()
    # Пытаемся найти пользователя по telegram_id
    result = (
        supabase
        .table("users")
        .select("*")
        .eq("telegram_id", str(tg_id))
        .maybe_single()
        .execute()
    )
    found = result.data if result else None

    if not found:
        # Создаём нового пользователя
        payload = {
            "id": str(uuid4()),
            "email": None,
            "username": username,
            "full_name": first_name,
            "avatar_url": photo_url,
            "telegram_id": str(tg_id),
            "rating": 0,
            "settings_json": {},
        }
        # Если нет rpc для uuid, вставка без id позволит БД сгенерировать uuid
        insert_res = supabase.table("users").insert({k: v for k, v in payload.items() if v is not None}).execute()
        # Затем читаем созданную строку
        result = (
            supabase
            .table("users")
            .select("*")
            .eq("telegram_id", str(tg_id))
            .single()
            .execute()
        )
        found = result.data if result else None

    return _row_to_user_public(found)


