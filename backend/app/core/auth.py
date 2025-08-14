from typing import Optional

from fastapi import Header, HTTPException, status
from pydantic import BaseModel

from .config import supabase_client


class AuthenticatedUser(BaseModel):
    # Модель текущего пользователя (минимальная)
    id: str
    email: Optional[str] = None


async def get_current_user(
    authorization: Optional[str] = Header(default=None, alias="Authorization"),
) -> AuthenticatedUser:
    # Достаём пользователя из Supabase по access token (Bearer)
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        auth_resp = supabase_client.auth.get_user(token)
        user_data = auth_resp.user
        if not user_data or not getattr(user_data, "id", None):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return AuthenticatedUser(id=str(user_data.id), email=getattr(user_data, "email", None))
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


