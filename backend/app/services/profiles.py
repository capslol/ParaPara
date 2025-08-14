from datetime import datetime, timezone
from typing import Any, Dict

from ..core.config import supabase_client


PROFILES_TABLE_NAME = "profiles"


def _utc_now_iso() -> str:
    # Возвращает ISO8601 UTC
    return datetime.now(timezone.utc).isoformat()


def ensure_profile_exists(user_id: str, email: str | None) -> Dict[str, Any]:
    # Создаёт профиль пользователя, если не существует
    existing = (
        supabase_client
        .table(PROFILES_TABLE_NAME)
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if rows:
        return rows[0]

    now_iso = _utc_now_iso()
    payload = {
        "id": user_id,
        "email": email,
        "full_name": None,
        "avatar_url": None,
        "rating": 0.0,
        "settings": {"notifications_enabled": True, "language": "ru"},
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    created = supabase_client.table(PROFILES_TABLE_NAME).upsert(payload, on_conflict="id").execute()
    data = created.data or []
    return data[0] if data else payload


def update_profile(user_id: str, update_values: Dict[str, Any]) -> Dict[str, Any]:
    # Обновляет профиль и возвращает обновлённую запись
    update_values = {**update_values, "updated_at": _utc_now_iso()}
    updated = (
        supabase_client
        .table(PROFILES_TABLE_NAME)
        .update(update_values)
        .eq("id", user_id)
        .execute()
    )
    rows = updated.data or []
    if rows:
        return rows[0]
    # fallback — если апдейт ничего не вернул
    return ensure_profile_exists(user_id, None)


