"""Synthetic-only input examples for the *shape* of live observation artifacts."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.validate_solana_history import ObservationValidationError, validate_document, validate_history

MINT_A = 'So11111111111111111111111111111111111111112'
MINT_B = 'So11111111111111111111111111111111111111113'


def decision(status='blocked', reasons=None):
    if reasons is None:
        reasons = ['security_unknown'] if status == 'blocked' else []
    return {'status': status, 'score': 75, 'reasons': reasons}


def fixture(*, started=1_800_000_000_000, missing=False, illiquid=False, source='dexscreener'):
    """In-memory invented contract fixture; never evidence of a real market call."""
    mints = [MINT_A, MINT_B]
    observations = []
    for i in range(3):
        for mint in mints:
            row = {'timestamp_ms': started + (i + 1) * 60_000, 'mint': mint, 'status': 'priced'}
            if mint == MINT_B and missing:
                row.update(status='missing_price', price_source=None, strategies={})
            else:
                low = illiquid and mint == MINT_B
                reasons = (['liquidity_below_10000_or_unknown', 'security_unknown']
                           if low else ['security_unknown'])
                row.update(
                    discovery_source='geckoterminal' if mint == MINT_A else 'dexscreener',
                    discovery_pool_id='solana_original_pool' if mint == MINT_A else 'dex_pool',
                    price_source=source if mint == MINT_A else 'dexscreener',
                    price_pair_id=('solana_original_pool' if source == 'geckoterminal' else 'dex_price_pool')
                                  if mint == MINT_A else 'dex_pool',
                    price_usd='0.100', liquidity_usd='300' if low else '25000',
                    volume_h24_usd='100000', buys_m5=30, sells_m5=10,
                    change_m5_pct=5.0, risk_record_present=False,
                    strategies={'new_coin_hunter': decision(reasons=reasons),
                                'momentum_watcher': decision(reasons=reasons)},
                )
            observations.append(row)
    good = not missing
    return {
        'schema_version': 1, 'mode': 'bounded_prospective_public_market_observations',
        'data_origin': 'live_public_api_not_historical',
        'trading_enabled': False, 'wallet_enabled': False,
        'background_schedule_enabled': False, 'performance_calculated': False,
        'start_timestamp_ms': started, 'requested_rounds': 3,
        'minimum_interval_seconds': 60, 'tracked_mints': mints,
        'observations': observations, 'errors': [],
        'summary': {'result': 'passed' if good else 'degraded', 'rounds': 3,
                    'selected_tokens': 2, 'valid_price_observations': 6 if good else 3,
                    'missing_price_observations': 0 if good else 3,
                    'complete_token_series': 2 if good else 1,
                    'provider_error_classes': []},
    }


def test_full_two_mint_capture_is_schema_valid_but_not_verified_performance():
    x = fixture()
    one = validate_document(x)
    assert one['result'] == 'passed' and one['priced_rows'] == 6
    report = validate_history([x])
    assert report['quality_result'] == 'complete_captures'
    assert report['total_priced_rows'] == 6
    assert report['ready_for_verified_paper_performance'] is False
    assert report['safety']['trading_enabled'] is False
    assert report['safety']['external_requests'] == 0


def test_two_separate_runs_accumulate_counts_without_same_token_assumption():
    first = fixture()
    second = fixture(started=1_800_005_000_000)
    history = validate_history([first, second])
    assert history['input_capture_count'] == 2
    assert history['total_priced_rows'] == 12
    assert history['samples_per_mint'] == [6, 6]
    assert not history['ready_for_verified_paper_performance']


def test_degraded_real_price_capture_is_never_green():
    x = validate_history([fixture(missing=True)])
    assert x['quality_result'] == 'degraded_capture_data'
    assert x['total_missing_rows'] == 3


def test_liquidity_drop_retains_price_but_blocks_both_strategies():
    x = validate_history([fixture(illiquid=True)])
    assert x['total_illiquid_price_rows'] == 3
    assert x['total_priced_rows'] == 6


def test_verified_original_gecko_pool_fallback_allowed():
    x = fixture(source='geckoterminal')
    assert validate_document(x)['result'] == 'passed'
    x['observations'][0]['price_pair_id'] = 'solana_DIFFERENT_POOL'
    with pytest.raises(ObservationValidationError, match='pool substitution'):
        validate_document(x)


@pytest.mark.parametrize('edit', [
    lambda x: x.update(data_origin='synthetic'),
    lambda x: x.update(performance_calculated=True),
    lambda x: x.update(trading_enabled=True),
    lambda x: x.update(wallet_enabled=True),
    lambda x: x['tracked_mints'].append(MINT_A),
    lambda x: x['observations'][1].update(mint='NOT_SOLANA_TOKEN'),
    lambda x: x['observations'][1].update(timestamp_ms=x['observations'][0]['timestamp_ms']+1),
    lambda x: x['observations'][1].update(price_usd='NaN'),
    lambda x: x['observations'][1].update(price_usd='-2'),
    lambda x: x['observations'][1].update(price_usd=0),
    lambda x: x['observations'][1].update(risk_record_present=False, strategies={
        'new_coin_hunter': decision('watch'), 'momentum_watcher': decision('watch')}),
    lambda x: x['observations'][1].update(liquidity_usd='100', strategies={
        'new_coin_hunter': decision('watch'), 'momentum_watcher': decision('watch')}),
    lambda x: x['observations'][1].update(status='missing_price', strategies={}, price_source=None),
    lambda x: x['summary'].update(valid_price_observations=99),
    lambda x: x['observations'].append(deepcopy(x['observations'][-1])),
])
def test_bad_input_provenance_timestamps_prices_or_safety_fail_closed(edit):
    x = fixture()
    edit(x)
    with pytest.raises(ObservationValidationError):
        validate_document(x)


def test_duplicate_capture_is_rejected():
    x = fixture()
    with pytest.raises(ObservationValidationError, match='Repeated capture'):
        validate_history([x, deepcopy(x)])


def test_cannot_mark_missing_risk_as_watch():
    x = fixture()
    x['observations'][0]['strategies']['momentum_watcher'] = decision('watch')
    with pytest.raises(ObservationValidationError, match='Missing security'):
        validate_document(x)


def test_cannot_mark_missing_price_as_zero():
    x = fixture(missing=True)
    x['observations'][1]['price_usd'] = '0'
    with pytest.raises(ObservationValidationError, match='fabricated'):
        validate_document(x)


def test_more_than_six_input_captures_rejected():
    with pytest.raises(ObservationValidationError, match='1 to 6'):
        validate_history([fixture(started=1_800_000_000_000 + i * 5_000_000) for i in range(7)])


def test_future_or_nonfinite_values_never_accepted():
    x = fixture()
    x['observations'][1]['change_m5_pct'] = float('inf')
    with pytest.raises(ObservationValidationError, match='Nonfinite'):
        validate_document(x)


def test_legacy_missing_price_preserves_attempted_provider_but_not_fake_price():
    # First real-data run recorded the attempted DEX provider on missing rows.
    x = fixture(missing=True)
    for row in x['observations']:
        if row['status'] == 'missing_price':
            row['price_source'] = 'dexscreener'
    result = validate_history([x])
    assert result['quality_result'] == 'degraded_capture_data'
    assert result['total_missing_rows'] == 3
