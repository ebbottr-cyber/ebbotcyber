"""Offline data-quality gate for manually downloaded Solana observation artifacts.

Never imports a trading engine, performs HTTP requests, places orders or reports
hypothetical P&L. Validates artifact provenance and continuity before reuse.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Sequence

_MINT = re.compile(r"[1-9A-HJ-NP-Za-km-z]{32,44}\Z")
_PROVIDERS = {"geckoterminal", "dexscreener"}
_STRATEGIES = {"new_coin_hunter", "momentum_watcher"}
_MAX_INPUT_BYTES = 2_000_000
_MAX_INPUT_FILES = 6


class ObservationValidationError(ValueError):
    """The observed data cannot be safely interpreted or aggregated."""


def _check(condition: bool, message: str) -> None:
    if not condition:
        raise ObservationValidationError(message)


def _money(value: Any, *, allow_zero: bool = False) -> Decimal:
    _check(not isinstance(value, bool) and value is not None, "Missing or invalid numeric data")
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ObservationValidationError("Missing or invalid numeric data") from exc
    _check(amount.is_finite() and (amount >= 0 if allow_zero else amount > 0),
           "Nonfinite, negative or zero numeric data")
    return amount


def _int(value: Any, label: str, low: int, high: int) -> int:
    _check(type(value) is int and low <= value <= high, f"Invalid {label}")
    return value


def _address(value: Any) -> bool:
    return isinstance(value, str) and _MINT.fullmatch(value) is not None


def validate_document(doc: Any) -> dict[str, Any]:
    """Check one complete report without assuming provider data is trustworthy."""
    _check(isinstance(doc, dict) and doc.get("schema_version") == 1, "Invalid report schema")
    for key, expected in (
        ("mode", "bounded_prospective_public_market_observations"),
        ("data_origin", "live_public_api_not_historical"),
        ("trading_enabled", False),
        ("wallet_enabled", False),
        ("background_schedule_enabled", False),
        ("performance_calculated", False),
    ):
        _check(type(doc.get(key)) is type(expected) and doc[key] == expected,
               f"Unsupported provenance or safety flag: {key}")

    rounds = _int(doc.get("requested_rounds"), "round count", 2, 4)
    spacing = _int(doc.get("minimum_interval_seconds"), "minimum spacing", 60, 120)
    started = _int(doc.get("start_timestamp_ms"), "start timestamp", 1, 10**16)
    mints = doc.get("tracked_mints")
    _check(isinstance(mints, list) and len(mints) <= 2 and
           all(_address(mint) for mint in mints) and len(mints) == len(set(mints)),
           "Invalid fixed mint list")
    observations = doc.get("observations")
    _check(isinstance(observations, list) and len(observations) == rounds * len(mints),
           "Observation rows must match the frozen token budget")
    errors = doc.get("errors")
    _check(isinstance(errors, list) and len(errors) <= 64, "Invalid provider error list")
    reported_error_types: set[str] = set()
    for e in errors:
        _check(isinstance(e, dict) and isinstance(e.get("provider"), str) and
               isinstance(e.get("error_class"), str), "Malformed provider error")
        reported_error_types.add(f"{e['provider']}:{e['error_class']}")

    per_mint: dict[str, list[tuple[int, bool]]] = defaultdict(list)
    by_timestamp: dict[int, set[str]] = defaultdict(set)
    row_keys: set[tuple[int, str]] = set()
    valid_count = 0
    missing_count = 0
    blocked_count = 0
    watch_count = 0
    low_liquidity_rows = 0
    for observation in observations:
        _check(isinstance(observation, dict), "Invalid price observation")
        mint = observation.get("mint")
        _check(mint in mints, "Observation introduced an unselected token")
        ts = _int(observation.get("timestamp_ms"), "quote receipt timestamp", 1, 10**16)
        _check(ts >= started and ts - started <= 3_600_000,
               "Observation timestamp exceeds bounded capture period")
        key = (ts, mint)
        _check(key not in row_keys, "Duplicate timestamp for the same token")
        row_keys.add(key)
        by_timestamp[ts].add(mint)
        status = observation.get("status")
        _check(status in ("priced", "missing_price"), "Invalid observation state")
        has_price = status == "priced"
        per_mint[mint].append((ts, has_price))
        if not has_price:
            missing_count += 1
            _check("price_usd" not in observation and observation.get("strategies") == {} and
                   observation.get("price_source") in (None, "dexscreener") and
                   "price_pair_id" not in observation,
                   "Missing quote has fabricated price or strategy")
            continue

        valid_count += 1
        _money(observation.get("price_usd"))
        source = observation.get("price_source")
        discovery_source = observation.get("discovery_source")
        pair = observation.get("price_pair_id")
        discovery_pair = observation.get("discovery_pool_id")
        _check(source in _PROVIDERS and discovery_source in _PROVIDERS and
               isinstance(pair, str) and bool(pair) and
               isinstance(discovery_pair, str) and bool(discovery_pair),
               "Invalid quote or discovery provenance")
        if source == "geckoterminal":
            _check(discovery_source == "geckoterminal" and pair == discovery_pair,
                   "Unverified GeckoTerminal pool substitution")
        liquidity = observation.get("liquidity_usd")
        if liquidity is not None:
            liquidity_value = _money(liquidity, allow_zero=True)
        else:
            liquidity_value = None
        volume = observation.get("volume_h24_usd")
        if volume is not None:
            _money(volume, allow_zero=True)
        for field in ("buys_m5", "sells_m5"):
            v = observation.get(field)
            _check(v is None or (type(v) is int and v >= 0), "Invalid transaction count")
        change = observation.get("change_m5_pct")
        if change is not None:
            _check(not isinstance(change, bool), "Invalid percentage")
            try:
                x = Decimal(str(change))
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ObservationValidationError("Invalid percentage") from exc
            _check(x.is_finite(), "Nonfinite percentage")
        risk_present = observation.get("risk_record_present")
        _check(type(risk_present) is bool, "Unknown risk record state")
        strategies = observation.get("strategies")
        _check(isinstance(strategies, dict) and set(strategies) == _STRATEGIES,
               "Both strategy assessments are required")
        for decision in strategies.values():
            _check(isinstance(decision, dict), "Malformed strategy assessment")
            state = decision.get("status")
            reasons = decision.get("reasons")
            score = decision.get("score")
            _check(state in ("watch", "blocked") and type(score) is int and
                   0 <= score <= 100 and isinstance(reasons, list) and
                   all(isinstance(reason, str) and reason for reason in reasons),
                   "Malformed strategy status, score or risk reasons")
            _check((state == "blocked") == bool(reasons),
                   "Risk reasons and candidate status disagree")
            if not risk_present:
                _check(state == "blocked" and "security_unknown" in reasons,
                       "Missing security data cannot generate watch status")
            if liquidity_value is None or liquidity_value < 10_000:
                _check(state == "blocked" and
                       "liquidity_below_10000_or_unknown" in reasons,
                       "Illiquid quote cannot be approved")
            blocked_count += state == "blocked"
            watch_count += state == "watch"
        if liquidity_value is None or liquidity_value < 10_000:
            low_liquidity_rows += 1

    _check(len(by_timestamp) == (rounds if mints else 0),
           "Missing or extra observation rounds")
    for ts, round_mints in by_timestamp.items():
        _check(round_mints == set(mints), "Each observation round needs the same mints")
    for mint, rows in per_mint.items():
        _check(len(rows) == rounds, "Incomplete fixed-mint observations")
        stamps = [ts for ts, _ in rows]
        _check(stamps == sorted(stamps) and len(stamps) == len(set(stamps)),
               "Unordered or repeated receipt times")
        for t0, t1 in zip(stamps, stamps[1:]):
            _check((spacing - 15) * 1_000 <= t1 - t0 <= 10 * 60_000,
                   "Unrealistic or insufficient time spacing")

    # Never trust a producer-supplied summary over the validated row content.
    complete_tokens = sum(sum(priced for _, priced in rows) == rounds
                          for rows in per_mint.values())
    expected_result = ("passed" if mints and complete_tokens == len(mints) and not errors
                       else "degraded" if observations else "inconclusive")
    summary = doc.get("summary")
    _check(isinstance(summary, dict), "Missing capture summary")
    for key, value in (
        ("result", expected_result), ("rounds", rounds),
        ("selected_tokens", len(mints)), ("valid_price_observations", valid_count),
        ("missing_price_observations", missing_count),
        ("complete_token_series", complete_tokens),
        ("provider_error_classes", sorted(reported_error_types)),
    ):
        _check(summary.get(key) == value and type(summary.get(key)) is type(value),
               f"Capture summary disagrees with data: {key}")
    return {
        "result": expected_result,
        "start_timestamp_ms": started,
        "mints": sorted(mints),
        "rounds": rounds,
        "priced_rows": valid_count,
        "missing_rows": missing_count,
        "watch_assessments_not_trade_signals": watch_count,
        "blocked_assessments": blocked_count,
        "illiquid_price_rows": low_liquidity_rows,
        "provider_error_count": len(errors),
    }


def validate_history(docs: Sequence[Any]) -> dict[str, Any]:
    _check(1 <= len(docs) <= _MAX_INPUT_FILES, "Use 1 to 6 independent captures")
    summaries = [validate_document(doc) for doc in docs]
    spans = [s["start_timestamp_ms"] for s in summaries]
    _check(len(set(spans)) == len(spans), "Repeated capture or duplicate input run")
    series: dict[str, set[int]] = defaultdict(set)
    for doc in docs:
        for observation in doc["observations"]:
            token = observation["mint"]
            stamp = observation["timestamp_ms"]
            _check(stamp not in series[token], "Same token/timestamp from multiple runs")
            series[token].add(stamp)
    all_complete = all(x["result"] == "passed" for x in summaries)
    return {
        "schema_version": 1,
        "mode": "offline_observation_quality_review",
        "input_provenance": "live_public_api_not_historical_unverified_execution",
        "safety": {"trading_enabled": False, "wallet_enabled": False,
                   "external_requests": 0, "performance_calculated": False},
        "quality_result": "complete_captures" if all_complete else "degraded_capture_data",
        "input_capture_count": len(summaries),
        "unique_mints": len(series),
        "total_priced_rows": sum(x["priced_rows"] for x in summaries),
        "total_missing_rows": sum(x["missing_rows"] for x in summaries),
        "total_illiquid_price_rows": sum(x["illiquid_price_rows"] for x in summaries),
        "total_provider_errors": sum(x["provider_error_count"] for x in summaries),
        "samples_per_mint": sorted(len(stamps) for stamps in series.values()),
        "ready_for_verified_paper_performance": False,
        "performance_not_ready_reasons": [
            "Snapshot receipt timestamps are not on-chain execution timestamps",
            "No verified executable spread, depth, Solana network costs or slippage",
            "No sufficiently long, continuous history of executable prices",
        ],
        "disclaimer": "Read-only data quality; not verified PnL, trades, or strategy performance.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline GitHub Solana observation data quality")
    parser.add_argument("--inputs", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("solana-observation-quality.json"))
    args = parser.parse_args()
    if not 1 <= len(args.inputs) <= _MAX_INPUT_FILES:
        parser.error("Use 1..6 distinct observation JSON artifacts")
    try:
        docs = []
        for path in args.inputs:
            if path.stat().st_size > _MAX_INPUT_BYTES:
                raise ObservationValidationError("Artifact exceeds maximum allowed size")
            docs.append(json.loads(path.read_text(encoding="utf-8")))
        report = validate_history(docs)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"result": "rejected", "error_class": type(exc).__name__,
                          "trading_enabled": False, "performance_calculated": False}))
        return 1
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["quality_result"] == "complete_captures" else 1


if __name__ == "__main__":
    raise SystemExit(main())
