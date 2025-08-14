import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router


# Создаем приложение FastAPI (минимальная конфигурация)
app = FastAPI(title="Parapara API", version="0.1.0")

# Разрешаем CORS для фронтенда и локальной разработки
frontend_url = os.environ.get("FRONTEND_PUBLIC_URL", "http://localhost:5173")
allowed_origins = list({frontend_url, "http://localhost:5173", "https://localhost:5173"})

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])  # Простой health-check
def health_check() -> dict:
    # Возвращаем минимальный статус
    return {"status": "ok"}


# Подключаем основной роутер API
app.include_router(api_router)


