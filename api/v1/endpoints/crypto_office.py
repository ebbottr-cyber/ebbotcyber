"""EBBot crypto-office read-only gateway.

Only authenticated admin sessions may read the isolated paper-research data.
The existing global auth toggle can be disabled for stock browsing, but this
endpoint intentionally stays closed in that case.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from src.auth import COOKIE_NAME, is_auth_enabled, verify_session
from src.services.crypto_office_bridge import CryptoOfficeUnavailable, read_crypto_dashboard

router = APIRouter()


def require_crypto_admin(request: Request) -> None:
    if not is_auth_enabled():
        raise HTTPException(
            status_code=403,
            detail={"error": "auth_required", "message": "Kripto ofisi için yönetici oturumunu etkinleştirin."},
        )
    session = request.cookies.get(COOKIE_NAME, "")
    if not session or not verify_session(session):
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Oturum gerekli."})


@router.get("/dashboard", dependencies=[Depends(require_crypto_admin)])
async def crypto_office_dashboard():
    try:
        payload = await read_crypto_dashboard()
    except CryptoOfficeUnavailable as exc:
        if exc.code in {"not_configured", "invalid_url"}:
            code = 503
        else:
            code = 502
        raise HTTPException(
            status_code=code,
            detail={"error": exc.code, "message": "Kripto ofisi verileri güvenli biçimde alınamadı."},
        ) from exc
    return JSONResponse(content=payload, headers={"Cache-Control": "private, no-store"})
