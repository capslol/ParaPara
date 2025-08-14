from __future__ import annotations

import hashlib
import hmac
import os
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

from app.core.config import get_settings
from app.services.user_service import get_or_create_user_by_telegram


router = APIRouter(prefix="/auth", tags=["auth"])


# In-memory state store with TTL
STATE_TTL_SECONDS = 600  # 10 minutes
_state_store: dict[str, dict[str, Any]] = {}


def _state_save(state: str) -> None:
    _state_store[state] = {"created_at": int(time.time()), "token": None, "profile": None}


def _state_set_token(state: str, token: str, profile: dict[str, Any]) -> None:
    item = _state_store.get(state)
    if not item:
        return
    item["token"] = token
    item["profile"] = profile


def _state_get_and_consume(state: str) -> Optional[dict[str, Any]]:
    item = _state_store.get(state)
    if not item:
        return None
    # TTL check
    if int(time.time()) - int(item.get("created_at", 0)) > STATE_TTL_SECONDS:
        _state_store.pop(state, None)
        return None
    # one-time use
    _state_store.pop(state, None)
    return item


def _build_data_check_string(params: dict[str, str]) -> str:
    # Формируем data_check_string только из параметров Telegram (без hash и без наших доп. полей вроде state)
    allowed_keys = {
        "id",
        "first_name",
        "last_name",
        "username",
        "photo_url",
        "auth_date",
    }
    prepared: list[str] = []
    for key in sorted(k for k in params.keys() if k != "hash" and k in allowed_keys):
        prepared.append(f"{key}={params[key]}")
    return "\n".join(prepared)


def _validate_telegram_login(params: dict[str, str], bot_token: str, max_age_seconds: int = 300) -> dict[str, Any]:
    # Валидация подписи Telegram Login
    received_hash = params.get("hash")
    auth_date_str = params.get("auth_date")
    if not received_hash or not auth_date_str:
        raise HTTPException(status_code=400, detail="Invalid Telegram auth data")

    try:
        auth_date = int(auth_date_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid auth_date")

    now = int(time.time())
    if now - auth_date > max_age_seconds:
        raise HTTPException(status_code=400, detail="Auth data expired")

    data_check_string = _build_data_check_string(params)
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(status_code=400, detail="Bad signature")

    # Ок, собираем профиль
    profile = {
        "id": int(params["id"]) if "id" in params else None,
        "first_name": params.get("first_name"),
        "last_name": params.get("last_name"),
        "username": params.get("username"),
        "photo_url": params.get("photo_url"),
        "auth_date": auth_date,
    }
    return profile


def _issue_jwt(profile: dict[str, Any], jwt_secret: str, ttl_days: int = 30) -> str:
    # Выпускаем простой JWT по Telegram профилю
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(profile.get("id")),
        "tg": {
            "id": profile.get("id"),
            "username": profile.get("username"),
            "first_name": profile.get("first_name"),
            "last_name": profile.get("last_name"),
            "photo_url": profile.get("photo_url"),
        },
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=ttl_days)).timestamp()),
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    return token


def _cookie_settings_from_request(request: Request) -> dict[str, Any]:
    # В современных браузерах для кросс-сайтовых запросов нужна SameSite=None; Secure
    # Определяем secure по схеме текущего запроса
    scheme = request.url.scheme.lower()
    cookie_secure = scheme == "https"
    cookie_samesite = "None" if cookie_secure else "Lax"
    return {"secure": cookie_secure, "samesite": cookie_samesite}


@router.get("/telegram/callback", response_class=HTMLResponse)
def telegram_callback(request: Request) -> Response:
    # Обрабатываем callback от Telegram LoginUrl, валидируем и ставим cookie с JWT
    settings = get_settings()
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    jwt_secret = os.environ.get("TELEGRAM_JWT_SECRET", "change-me")
    frontend_url = os.environ.get("FRONTEND_PUBLIC_URL", "http://localhost:5173")

    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")

    params: dict[str, str] = dict(request.query_params)
    # Telegram может присылать user как JSON в поле 'user' (WebApp), но LoginUrl передает плоские параметры.
    # Мы валидируем только стандартизованный набор полей.
    profile = _validate_telegram_login(params, bot_token)

    jwt_token = _issue_jwt(profile, jwt_secret)

    # Ставим cookie и редиректим на фронт
    cookie_attrs = _cookie_settings_from_request(request)
    # Для сохранения cookie при редиректе лучше использовать 303 See Other
    response = RedirectResponse(url=frontend_url, status_code=303)
    response.set_cookie(
        key="tg_session",
        value=jwt_token,
        httponly=True,
        secure=cookie_attrs["secure"],
        samesite=cookie_attrs["samesite"],
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return response


def _get_jwt_from_request(request: Request) -> str | None:
    # Сначала пробуем получить из Authorization header (Bearer token)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    
    # Затем из cookie
    return request.cookies.get("tg_session")


@router.get("/me")
def me(request: Request) -> dict[str, Any]:
    # Возвращаем текущего пользователя из JWT (Bearer или cookie)
    jwt_secret = os.environ.get("TELEGRAM_JWT_SECRET", "change-me")
    token = _get_jwt_from_request(request)
    if not token:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        data = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    return {
        "id": data.get("tg", {}).get("id"),
        "username": data.get("tg", {}).get("username"),
        "first_name": data.get("tg", {}).get("first_name"),
        "last_name": data.get("tg", {}).get("last_name"),
        "photo_url": data.get("tg", {}).get("photo_url"),
    }


@router.get("/telegram/deeplink")
def telegram_deeplink(state: str | None = None) -> dict[str, str]:
    # Возвращаем ссылку t.me с deep-link параметром для старта бота
    bot_username = os.environ.get("TELEGRAM_BOT_USERNAME", "")
    if not bot_username:
        raise HTTPException(status_code=500, detail="Bot username not configured")
    start_param = state or "auth"
    link = f"https://t.me/{bot_username}?start={start_param}"
    return {"deeplink": link}


@router.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    # Чистим cookie сессии
    response.delete_cookie(key="tg_session", path="/")
    return {"success": True}


# New flow with state
@router.get("/telegram")
def start_telegram_oauth(state: str | None = None) -> Response:
    # Шаг 1-2: сохраняем state и редиректим в бота с start=auth_<state>
    if not state:
        raise HTTPException(status_code=400, detail="state is required")
    bot_username = os.environ.get("TELEGRAM_BOT_USERNAME", "")
    if not bot_username:
        raise HTTPException(status_code=500, detail="Bot username not configured")
    _state_save(state)
    tp = f"auth_{state}"
    deeplink = f"https://t.me/{bot_username}?start={tp}"
    return RedirectResponse(url=deeplink, status_code=303)


@router.post("/telegram/callback/bot")
async def telegram_bot_callback(request: Request) -> dict[str, Any]:
    # Шаг 3-4: бот присылает данные пользователя и state. Авторизуем и сохраняем токен на state
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")
    # Простейшая аутентификация запроса от бота
    auth_header = request.headers.get("X-Bot-Token")
    if auth_header != bot_token:
        raise HTTPException(status_code=401, detail="Unauthorized bot")

    body = await request.json()
    state = (body or {}).get("state")
    if not state or state not in _state_store:
        raise HTTPException(status_code=400, detail="Invalid state")

    tg_profile = {
        "id": (body or {}).get("id"),
        "username": (body or {}).get("username"),
        "first_name": (body or {}).get("first_name"),
        "last_name": (body or {}).get("last_name"),
        "photo_url": (body or {}).get("photo_url"),
    }
    if not tg_profile["id"]:
        raise HTTPException(status_code=400, detail="Missing telegram id")

    # Создаём/находим пользователя
    user = await get_or_create_user_by_telegram(
        tg_id=tg_profile["id"],
        username=tg_profile.get("username"),
        first_name=tg_profile.get("first_name"),
        photo_url=tg_profile.get("photo_url"),
    )

    # Генерим JWT
    jwt_secret = os.environ.get("TELEGRAM_JWT_SECRET", "change-me")
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(tg_profile["id"]),
        "tg": tg_profile,
        "uid": str(user.id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=30)).timestamp()),
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")

    _state_set_token(state, token, tg_profile)
    return {"ok": True}


@router.get("/token")
def exchange_token(state: str) -> dict[str, Any]:
    # Шаг 6: фронт обменивает state на jwt
    item = _state_get_and_consume(state)
    if not item or not item.get("token"):
        raise HTTPException(status_code=400, detail="Invalid or expired state")
    return {"token": item["token"], "profile": item.get("profile")}


@router.get("/success")
async def auth_success_redirect(state: str, request: Request):
    """Прокси-роут для перенаправления на frontend после авторизации"""
    # Перенаправляем на frontend с тем же state
    frontend_url = os.environ.get("FRONTEND_PUBLIC_URL", "http://localhost:5173")
    redirect_url = f"{frontend_url.rstrip('/')}/auth/success?state={state}"
    return RedirectResponse(url=redirect_url, status_code=303)


