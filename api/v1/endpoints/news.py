"""ETRE market news inbox endpoints. Mutations are protected by existing auth middleware."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from starlette.responses import JSONResponse

from src.services import news_hub_service as service

router = APIRouter()


class NotificationPreference(BaseModel):
    enabled: bool


@router.get("/status")
def get_news_status():
    return JSONResponse(service.news_status(), headers={"Cache-Control": "private, no-store"})


@router.get("/items")
def get_news_items(
    market: str | None = Query(default=None),
    unread_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=200),
):
    try:
        result = service.list_news(market=market, unread_only=unread_only, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bilinmeyen piyasa.") from exc
    return JSONResponse(result, headers={"Cache-Control": "private, no-store"})


@router.post("/refresh")
def refresh_news():
    """Manual RSS refresh, not an uncontrolled AI or stock analysis run."""
    return service.refresh_news()


@router.post("/{article_id}/read")
def mark_read(article_id: str):
    try:
        return service.mark_one_read(article_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Geçersiz haber kimliği.") from exc


@router.post("/read-all")
def mark_all_read():
    return service.mark_all_read()


@router.put("/ai")
def save_news_ai(payload: NotificationPreference):
    return service.set_ai_enabled(payload.enabled)


@router.put("/notifications")
def save_notifications(payload: NotificationPreference):
    return service.set_notifications(payload.enabled)
