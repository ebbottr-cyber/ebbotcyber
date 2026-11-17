"""EBBot crypto-office read-only gateway.

Only authenticated admin sessions may read the isolated paper-research data.
The existing global auth toggle can be disabled for stock browsing, but this
endpoint intentionally stays closed in that case.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from typing import Literal
from fastapi.responses import JSONResponse

from src.auth import COOKIE_NAME, is_auth_enabled, verify_session
from src.services.crypto_office_bridge import CryptoOfficeUnavailable, read_crypto_dashboard
from src.services.crypto_spot_bridge import SpotDataError, spot_data
from src.services.crypto_futures_bridge import FuturesDataError, futures_data

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


def _spot_error(exc: SpotDataError) -> HTTPException:
    status = {
        "invalid_symbol": 422,
        "invalid_parameters": 422,
        "unsupported_symbol": 404,
        "rate_limited": 503,
        "not_configured": 503,
        "stale_market_data": 503,
    }.get(exc.code, 502)
    return HTTPException(
        status_code=status,
        detail={"error": exc.code, "message": "Binance Spot verisi güvenli biçimde doğrulanamadı."},
    )


@router.get("/spot/ticker", dependencies=[Depends(require_crypto_admin)])
async def crypto_spot_ticker(symbol: str = Query("BTC/USDT", max_length=26)):
    try:
        payload = await spot_data("ticker", symbol.strip().upper())
    except SpotDataError as exc:
        raise _spot_error(exc) from exc
    return JSONResponse(content=payload, headers={"Cache-Control": "private, no-store"})


@router.get("/spot/ohlcv", dependencies=[Depends(require_crypto_admin)])
async def crypto_spot_ohlcv(
    symbol: str = Query("BTC/USDT", max_length=26),
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d"] = "1h",
    limit: int = Query(100, ge=20, le=300),
):
    try:
        payload = await spot_data("ohlcv", symbol.strip().upper(), timeframe, limit)
    except SpotDataError as exc:
        raise _spot_error(exc) from exc
    return JSONResponse(content=payload, headers={"Cache-Control": "private, no-store"})


@router.get("/spot/orderbook", dependencies=[Depends(require_crypto_admin)])
async def crypto_spot_orderbook(
    symbol: str = Query("BTC/USDT", max_length=26),
    limit: Literal[5, 10, 20, 50, 100] = 20,
):
    try:
        payload = await spot_data("orderbook", symbol.strip().upper(), limit=limit)
    except SpotDataError as exc:
        raise _spot_error(exc) from exc
    return JSONResponse(content=payload, headers={"Cache-Control": "private, no-store"})



def _futures_error(exc: FuturesDataError) -> HTTPException:
    status = {
        "invalid_symbol": 422,
        "invalid_parameters": 422,
        "unsupported_symbol": 404,
        "rate_limited": 503,
        "circuit_open": 503,
        "not_configured": 503,
        "stale_market_data": 503,
        "unsafe_mode": 503,
    }.get(exc.code, 502)
    return HTTPException(
        status_code=status,
        detail={"error": exc.code, "message": "Binance USD-M Futures verisi doğrulanamadı."},
    )


@router.get("/futures/ticker", dependencies=[Depends(require_crypto_admin)])
async def crypto_futures_ticker(symbol: str = Query("BTC/USDT", max_length=26)):
    try:
        data = await futures_data("ticker", symbol)
    except FuturesDataError as exc:
        raise _futures_error(exc) from exc
    return JSONResponse(content=data, headers={"Cache-Control": "private, no-store"})


@router.get("/futures/ohlcv", dependencies=[Depends(require_crypto_admin)])
async def crypto_futures_ohlcv(
    symbol: str = Query("BTC/USDT", max_length=26),
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1d"] = "1h",
    limit: int = Query(100, ge=20, le=300),
):
    try:
        data = await futures_data("ohlcv", symbol, timeframe, limit)
    except FuturesDataError as exc:
        raise _futures_error(exc) from exc
    return JSONResponse(content=data, headers={"Cache-Control": "private, no-store"})


@router.get("/futures/orderbook", dependencies=[Depends(require_crypto_admin)])
async def crypto_futures_orderbook(
    symbol: str = Query("BTC/USDT", max_length=26),
    limit: Literal[5, 10, 20, 50, 100] = 20,
):
    try:
        data = await futures_data("orderbook", symbol, limit=limit)
    except FuturesDataError as exc:
        raise _futures_error(exc) from exc
    return JSONResponse(content=data, headers={"Cache-Control": "private, no-store"})


@router.get("/futures/funding", dependencies=[Depends(require_crypto_admin)])
async def crypto_futures_funding(symbol: str = Query("BTC/USDT", max_length=26)):
    try:
        data = await futures_data("funding", symbol)
    except FuturesDataError as exc:
        raise _futures_error(exc) from exc
    return JSONResponse(content=data, headers={"Cache-Control": "private, no-store"})


@router.get("/futures/open-interest", dependencies=[Depends(require_crypto_admin)])
async def crypto_futures_open_interest(symbol: str = Query("BTC/USDT", max_length=26)):
    try:
        data = await futures_data("open-interest", symbol)
    except FuturesDataError as exc:
        raise _futures_error(exc) from exc
    return JSONResponse(content=data, headers={"Cache-Control": "private, no-store"})
