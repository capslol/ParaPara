from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class OrderBase(BaseModel):
    # Базовые поля заявки
    type: Literal["buy", "sell"]
    asset: Literal["USDT"] = Field(default="USDT")
    fiat: Literal["EUR", "DINAR", "RUB", "USD"]
    price: float
    available_amount: float
    limit_min: float
    limit_max: float
    payment_methods: list[str] = Field(default_factory=list)
    terms: Optional[str] = None


class OrderCreate(OrderBase):
    # Вставка — owner_id и id/created_at ставятся на сервере
    pass


class OrderPublic(OrderBase):
    # Публичная модель ответа
    id: str
    owner_id: str
    created_at: datetime


