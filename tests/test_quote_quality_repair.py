"""Regression coverage for the two-market daily report data contract."""
from unittest.mock import Mock

import pandas as pd
import pytest
import requests

from data_provider.akshare_fetcher import AkshareFetcher
from src.notification import _format_volume_metric


def test_daily_volume_normalization_is_idempotent():
    fetcher = AkshareFetcher()
    bars = pd.DataFrame({
        'date': ['2026-11-23', '2026-11-24'],
        'close': [2.83, 2.81], 'low': [2.74, 2.79], 'high': [2.84, 2.88],
        'volume': [1254682, 1016478], 'amount': [349816000, 288585900],
    })
    cleaned = fetcher._clean_data(bars)
    assert list(cleaned.volume) == [125468200, 101647800]
    assert round(cleaned.volume.iloc[-1] / cleaned.volume.iloc[-2], 2) == 0.81
    pd.testing.assert_frame_equal(fetcher._clean_data(cleaned), cleaned)
    shares = bars.copy()
    shares.volume *= 100
    assert list(fetcher._clean_data(shares).volume) == list(shares.volume)


@pytest.mark.parametrize('value', [None, 'N/A', '数据缺失，无法判断', float('nan'), float('inf'), -1])
def test_missing_turnover_has_no_percent_suffix(value):
    assert _format_volume_metric(value, percent=True) == 'N/A'


def test_numeric_turnover_has_one_percent_suffix():
    assert _format_volume_metric('1.05%', percent=True) == '1.05%'
    assert _format_volume_metric(0, percent=True) == '0%'


def test_hk_single_quote_retries_and_preserves_decimal_fields(monkeypatch):
    response = Mock()
    response.json.return_value = {'data': {
        'f57': '02015', 'f58': '理想汽车-W', 'f43': 43.6,
        'f47': 8738503, 'f48': 378835280, 'f50': 1.64, 'f168': 0.51,
        'f86': 1795578450,
    }}
    get = Mock(side_effect=[requests.Timeout('transient'), response])
    monkeypatch.setattr('data_provider.akshare_fetcher.requests.get', get)
    monkeypatch.setattr('data_provider.akshare_fetcher.time.sleep', lambda _: None)
    quote = AkshareFetcher()._get_hk_single_quote('HK02015')
    assert get.call_count == 2
    assert 'secid=116.02015' in get.call_args.args[0]
    assert quote.price == 43.6
    assert quote.volume_ratio == 1.64
    assert quote.turnover_rate == 0.51
    assert quote.volume == 8738503
    assert quote.provider_timestamp is not None


def test_hk_single_quote_rejects_wrong_symbol(monkeypatch):
    response = Mock()
    response.json.return_value = {'data': {'f57': '00700', 'f43': 370}}
    monkeypatch.setattr('data_provider.akshare_fetcher.requests.get', Mock(return_value=response))
    monkeypatch.setattr('data_provider.akshare_fetcher.time.sleep', lambda _: None)
    assert AkshareFetcher()._get_hk_single_quote('HK02015') is None


def test_hk_single_quote_falls_back_after_two_failures(monkeypatch):
    get = Mock(side_effect=requests.Timeout('unavailable'))
    monkeypatch.setattr('data_provider.akshare_fetcher.requests.get', get)
    monkeypatch.setattr('data_provider.akshare_fetcher.time.sleep', lambda _: None)
    assert AkshareFetcher()._get_hk_single_quote('HK02015') is None
    assert get.call_count == 2


def test_snapshot_uses_quote_previous_close_instead_of_adjusted_history():
    from src.analyzer import GeminiAnalyzer
    analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)
    result = analyzer._build_market_snapshot({
        'date': '2026-11-25',
        'today': {'close': 43.62, 'open': 41.38, 'high': 43.92, 'low': 41.38},
        'yesterday': {'close': 41.62},
        'realtime': {'price': 43.62, 'pre_close': 41.38},
    })
    assert result['prev_close'] == '41.38'
    assert result['change_amount'] == '2.24'


def test_hk_valid_single_quote_keeps_timestamp_without_optional_metrics(monkeypatch):
    from data_provider.realtime_types import UnifiedRealtimeQuote, RealtimeSource
    quote = UnifiedRealtimeQuote(code='HK02015', source=RealtimeSource.AKSHARE_EM,
                                 price=45.8, high=48.0, low=44.0,
                                 provider_timestamp='2026-11-26T08:08:05+00:00')
    monkeypatch.setattr(AkshareFetcher, '_get_hk_single_quote', lambda *args: quote)
    assert AkshareFetcher()._get_hk_realtime_quote('HK02015') is quote
