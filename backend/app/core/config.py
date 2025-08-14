import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from supabase import Client, create_client


# Инициализация приложения и Supabase клиента


def create_app() -> FastAPI:
    # Создаёт и настраивает FastAPI-приложение
    app = FastAPI(title="Parapara Backend", version="0.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


def create_supabase_client() -> Client:
    # Создаёт Supabase-клиент, используя service role key, если доступен
    supabase_url = os.environ.get("SUPABASE_URL")
    service_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    anon_key = os.environ.get("SUPABASE_ANON_KEY")
    if not supabase_url or not (service_key or anon_key):
        raise RuntimeError("Supabase env vars SUPABASE_URL and one of keys must be set")
    key_to_use = service_key or anon_key
    return create_client(supabase_url, key_to_use)


supabase_client: Client = create_supabase_client()


