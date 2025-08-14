from typing import Any, Optional

from supabase import create_client

from app.core.config import get_settings


_client: Optional[Any] = None


def get_supabase_client() -> Any:
    # Создаем lazy singleton клиента Supabase
    global _client
    if _client is None:
        settings = get_settings()
        # Разрешаем использовать либо SERVICE_ROLE_KEY, либо ANON_KEY
        key = settings.supabase_service_role_key or settings.supabase_anon_key
        if not settings.supabase_url or not key:
            raise RuntimeError("Supabase config is not set")
        _client = create_client(settings.supabase_url, key)
    return _client


