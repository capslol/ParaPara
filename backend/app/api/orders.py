from fastapi import APIRouter, Depends, Header, HTTPException, status, Request

from app.schemas.order import OrderCreate, OrderPublic
from app.services.order_service import create_order, list_orders, delete_order
from app.services.user_service import get_or_create_user_by_jwt, get_or_create_user_by_telegram
from app.api.auth import _get_jwt_from_request


router = APIRouter(prefix="/orders")


def _extract_bearer_token(authorization: str | None = Header(default=None)) -> str:
    # Достаем токен из заголовка Authorization: Bearer <token>
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization format")
    return parts[1]


async def _get_current_user(request: Request):
    """Получаем текущего пользователя из JWT (Bearer или cookie)"""
    import os, jwt
    from app.services.user_service import get_or_create_user_by_telegram
    
    token = _get_jwt_from_request(request)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    
    jwt_secret = os.environ.get("TELEGRAM_JWT_SECRET", "change-me")
    try:
        data = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    tg = data.get("tg") or {}
    if not tg.get("id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    
    # Получим/создадим локального пользователя по Telegram
    user = await get_or_create_user_by_telegram(
        tg_id=tg.get("id"),
        username=tg.get("username"),
        first_name=tg.get("first_name"),
        photo_url=tg.get("photo_url"),
    )
    return user


@router.get("/", response_model=list[OrderPublic])
async def get_orders(type: str | None = None, authorization: str | None = Header(default=None)) -> list[OrderPublic]:
    # Публичный листинг ордеров. Если токен не передан, используем anon key на сервере
    # (политики RLS для SELECT публичные, поэтому достаточно anon)
    return await list_orders(order_type=type)


@router.post("/", response_model=OrderPublic, status_code=status.HTTP_201_CREATED)
async def post_order(payload: OrderCreate, request: Request) -> OrderPublic:
    # Создание ордера текущим пользователем через JWT (Bearer или cookie)
    user = await _get_current_user(request)
    return await create_order(user.id, payload, jwt_token=None)


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_order(order_id: str, request: Request) -> None:
    # Удаление ордера текущим пользователем через JWT (Bearer или cookie)
    user = await _get_current_user(request)
    
    # Жёсткая проверка владельца: читаем ордер и сверяем owner_id с нашим пользователем
    from app.core.supabase import get_supabase_client
    supabase = get_supabase_client()
    result = supabase.table("orders").select("owner_id").eq("id", order_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    
    if str(result.data.get("owner_id")) != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    
    await delete_order(order_id, jwt_token=None)

