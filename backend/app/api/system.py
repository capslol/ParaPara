from fastapi import APIRouter

from ..models.schemas import EchoRequest, EchoResponse, HealthResponse


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    # Простой healthcheck
    return HealthResponse(status="ok")


@router.post("/echo", response_model=EchoResponse)
def echo(payload: EchoRequest) -> EchoResponse:
    # Простой echo
    return EchoResponse(message=payload.message)


