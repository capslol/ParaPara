from __future__ import annotations

from typing import List
from uuid import uuid4

from app.core.supabase import get_supabase_client
from app.schemas.order import OrderCreate, OrderPublic


def _row_to_order_public(row: dict) -> OrderPublic:
    return OrderPublic(
        id=str(row["id"]),
        owner_id=str(row["owner_id"]),
        created_at=row["created_at"],
        type=row["type"],
        asset=row["asset"],
        fiat=row["fiat"],
        price=float(row["price"]),
        available_amount=float(row["available_amount"]),
        limit_min=float(row["limit_min"]),
        limit_max=float(row["limit_max"]),
        payment_methods=row.get("payment_methods") or [],
        terms=row.get("terms"),
    )


async def create_order(owner_id: str, payload: OrderCreate, jwt_token: str | None = None) -> OrderPublic:
    # Создаем ордер от имени текущего пользователя максимально простым способом
    supabase = get_supabase_client()
    # Установим контекст пользователя для RLS при работе через anon key
    try:
        if jwt_token:
            supabase.postgrest.auth(jwt_token)
    except Exception:
        pass

    order_id = str(uuid4())
    insert_payload = {
        "id": order_id,
        "owner_id": owner_id,
        "type": payload.type,
        "asset": payload.asset,
        "fiat": payload.fiat,
        "price": payload.price,
        "available_amount": payload.available_amount,
        "limit_min": payload.limit_min,
        "limit_max": payload.limit_max,
        "payment_methods": payload.payment_methods,
        "terms": payload.terms,
    }
    # Вставка без chained select — затем отдельный безопасный select
    supabase.table("orders").insert(insert_payload).execute()
    sel = (
        supabase
        .table("orders")
        .select("*")
        .eq("id", order_id)
        .single()
        .execute()
    )
    return _row_to_order_public(sel.data)


async def list_orders(order_type: str | None = None) -> List[OrderPublic]:
    # Список публичных ордеров
    supabase = get_supabase_client()
    query = supabase.table("orders").select("*")
    if order_type:
        query = query.eq("type", order_type)
    query = query.order("price", desc=False)
    res = query.execute()
    rows = res.data or []
    return [_row_to_order_public(r) for r in rows]


async def delete_order(order_id: str, jwt_token: str | None = None) -> None:
    # Удаление ордера. Право удаления обеспечивает RLS (владелец).
    supabase = get_supabase_client()
    try:
        if jwt_token:
            supabase.postgrest.auth(jwt_token)
    except Exception:
        pass

    # Если запись не найдена или нет прав — Postgrest вернет пустой результат/ошибку, пробрасываем как есть
    supabase.table("orders").delete().eq("id", order_id).execute()

