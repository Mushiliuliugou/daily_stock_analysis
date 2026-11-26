from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import requests

from src.services.company_disclosures import collect_company_disclosures


def test_official_earnings_is_collected_without_search_key(monkeypatch):
    listing = '<a href="/news-releases/news-release-details/q3">Third Quarter Financial Results</a>'
    article = '<article><h1>Third Quarter Financial Results</h1>' + ('2026-09-30 revenue evidence. ' * 20) + '</article>'
    pages = []
    for html in [listing, article]:
        response = Mock(text=html)
        pages.append(response)
    monkeypatch.setattr('src.services.company_disclosures.requests.get', Mock(side_effect=pages))
    monkeypatch.setattr('data_provider.akshare_fetcher._akshare_call_with_timeout', lambda *a, **kw: pd.DataFrame())
    result = collect_company_disclosures('HK02015', '理想汽车')
    assert len(result['evidence']) == 1
    assert '[官方公告]' in result['evidence'][0]
    assert '2026-09-30' in result['evidence'][0]
    assert len(result['errors']) == 1
    assert '财报交叉核验' in result['errors'][0]


def test_official_and_news_failures_are_reported_explicitly(monkeypatch):
    monkeypatch.setattr('src.services.company_disclosures.requests.get', Mock(side_effect=requests.Timeout()))
    monkeypatch.setattr('data_provider.akshare_fetcher._akshare_call_with_timeout', Mock(side_effect=TimeoutError()))
    result = collect_company_disclosures('HK02015', '理想汽车')
    assert result['evidence'] == []
    assert len(result['errors']) == 3


def test_official_listing_does_not_follow_external_links(monkeypatch):
    response = Mock(text='<a href="https://untrusted.example/news-release-details/q3">Financial results</a>')
    get = Mock(return_value=response)
    monkeypatch.setattr('src.services.company_disclosures.requests.get', get)
    monkeypatch.setattr('data_provider.akshare_fetcher._akshare_call_with_timeout', lambda *a, **kw: pd.DataFrame())
    result = collect_company_disclosures('HK02015', '理想汽车')
    assert get.call_count == 1
    assert result['evidence'] == []
    assert result['errors']


def test_financial_crosscheck_keeps_period_and_currency_warning(monkeypatch):
    response = Mock(text='<a href="https://untrusted.example/no">Financial results</a>')
    monkeypatch.setattr('src.services.company_disclosures.requests.get', Mock(return_value=response))
    financials = pd.DataFrame([
        {'REPORT_DATE': '2026-06-30', 'CURRENCY': '人民币', 'OPERATE_INCOME': 100},
        {'REPORT_DATE': '2026-09-30', 'CURRENCY': 'HKD', 'OPERATE_INCOME': 150},
    ])
    def fetch(*args, **kwargs):
        return financials if kwargs['call_name'] == 'company_financial_crosscheck' else pd.DataFrame()
    monkeypatch.setattr('data_provider.akshare_fetcher._akshare_call_with_timeout', fetch)
    result = collect_company_disclosures('HK02015', '理想汽车')
    assert result['latest_period_seen'] == '2026-09-30'
    assert any('跨期币种' in error for error in result['errors'])
    assert '2026-09-30' in result['evidence'][0]

    assert 'OPERATE_INCOME' not in result['evidence'][0]
    assert 'HKD' in result['evidence'][0]
    assert any('已隔离' in error for error in result['errors'])
