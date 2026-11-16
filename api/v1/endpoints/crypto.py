"""Read-only CoinGecko Top 100 and on-demand technical screening API."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from src.services.coingecko_top100 import CoinGeckoError, analyze_coin, top100

router = APIRouter()


def _translate_error(exc: CoinGeckoError) -> HTTPException:
    codes = {
        "unknown_coin": (404, "Coin is not in the current CoinGecko Top 100."),
        "insufficient_history": (422, "Not enough complete daily candles for this coin."),
        "rate_limited": (503, "CoinGecko request quota exceeded. Try later."),
        "access_denied": (503, "CoinGecko denied API access. Check the Demo API key."),
        "invalid_top100": (503, "CoinGecko did not provide 100 valid coins."),
        "invalid_history": (503, "CoinGecko historical data was invalid."),
        "unavailable": (503, "CoinGecko is currently unavailable."),
    }
    status, message = codes.get(str(exc), (503, "CoinGecko is currently unavailable."))
    return HTTPException(status_code=status, detail={"error": str(exc), "message": message})


@router.get("/top100", summary="CoinGecko current market-cap Top 100")
def get_crypto_top100():
    try:
        result = top100()
    except CoinGeckoError as exc:
        raise _translate_error(exc) from exc
    return JSONResponse(content=result, headers={"Cache-Control": "private, no-store"})


@router.get("/{coin_id}/technical", summary="Apply Daily's technical strategy to a Top 100 coin")
def get_crypto_technical(coin_id: str):
    try:
        result = analyze_coin(coin_id)
    except CoinGeckoError as exc:
        raise _translate_error(exc) from exc
    return JSONResponse(content=result, headers={"Cache-Control": "private, no-store"})
