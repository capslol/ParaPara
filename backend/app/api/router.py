from fastapi import APIRouter

from app.api.users import router as users_router
from app.api.orders import router as orders_router
from app.api.auth import router as auth_router


# Общий роутер API с единым префиксом
api_router = APIRouter(prefix="/api")

# Подключаем модули
api_router.include_router(users_router, tags=["users"])
api_router.include_router(orders_router, tags=["orders"])
api_router.include_router(auth_router)


