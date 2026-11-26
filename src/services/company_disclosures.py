"""Public company disclosures, independent of paid news search configuration."""
from __future__ import annotations

import logging
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Issuer identifiers and investor-relations sites are reference data.
_LI_CODES = {'HK02015', 'HK2015', '2015.HK', '02015.HK', 'LI'}


def collect_company_disclosures(code: str, stock_name: str) -> dict:
    """Return evidence and explicit failures. Never equate fetch failure with no news."""
    evidence = []
    errors = []
    latest_period_seen = None
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    if code.upper() not in _LI_CODES and code != '000002':
        return {'evidence': [], 'errors': ['issuer not covered by public disclosure collector'], 'checked_at': now.isoformat()}
    if code.upper() in _LI_CODES:
        try:
            base = 'https://ir.lixiang.com'
            response = requests.get(base + '/news/', timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            links = {}
            for anchor in soup.select('a[href]'):
                url = urljoin(base, anchor['href'])
                title = anchor.get_text(' ', strip=True)
                if (urlparse(url).hostname == 'ir.lixiang.com'
                        and '/news-release-details/' in url
                        and any(word in title.lower() for word in ('financial', '财务', '財務'))):
                    links.setdefault(url, title)
            if not links:
                raise ValueError('official listing contains no financial release links')
            for url, title in list(links.items())[:3]:
                page = requests.get(url, timeout=10)
                page.raise_for_status()
                document = BeautifulSoup(page.text, 'html.parser')
                content = document.select_one('article') or document.select_one('main')
                if content is None:
                    raise ValueError('official release article is unavailable')
                for element in content.select('script,style,nav,footer'):
                    element.decompose()
                text = content.get_text(' ', strip=True)
                if len(text) < 200:
                    raise ValueError('official release text is incomplete')
                evidence.append(f'[官方公告] {title}\n来源 {url}\n{text[:18000]}')
        except (requests.RequestException, ValueError) as exc:
            errors.append(f'公司官网公告获取失败 ({type(exc).__name__})')

    if code.upper() in _LI_CODES:
        try:
            import akshare as ak
            from data_provider.akshare_fetcher import _akshare_call_with_timeout
            financials = _akshare_call_with_timeout(
                ak.stock_financial_hk_analysis_indicator_em, timeout=15,
                call_name='company_financial_crosscheck', symbol='02015', indicator='报告期',
            )
            if financials.empty:
                raise ValueError('empty financial crosscheck')
            import pandas as pd
            dates = pd.to_datetime(financials['REPORT_DATE'], errors='coerce')
            financials = financials.assign(_period=dates).dropna(subset=['_period']).sort_values('_period', ascending=False).drop(columns=['_period'])
            if financials.empty:
                raise ValueError('financial crosscheck has no valid report date')
            latest_period_seen = pd.Timestamp(financials.iloc[0]['REPORT_DATE']).date().isoformat()
            if financials.head(3).get('CURRENCY', pd.Series(dtype=str)).nunique() > 1:
                errors.append('财报交叉核验的跨期币种标记不一致，金额及比率已隔离；仅可确认报告期，不可引用或推算财务数值')
                # Keep discovery of a newer period, but quarantine values whose
                # currency basis cannot be verified against an issuer filing.
                metadata = ['REPORT_DATE', 'START_DATE', 'CURRENCY', 'DATE_TYPE_CODE']
                financials = financials[[key for key in metadata if key in financials.columns]]
            # Preserve original period/type/currency fields. The provider may
            # report cumulative values; do not relabel these as single-quarter.
            evidence.append(
                '[东方财富财报交叉核验，非公司公告原文] 不得称为官方口径；原始报告期、币种、累计/季度口径须保留。\n'
                '来源 https://emweb.securities.eastmoney.com/PC_HKF10/NewFinancialAnalysis/index?type=web&code=02015\n'
                + financials.head(3).to_json(orient='records', force_ascii=False, date_format='iso')
            )
        except Exception as exc:
            errors.append(f'财报交叉核验接口获取失败 ({type(exc).__name__})')

    if code == '000002':
        try:
            import akshare as ak
            from data_provider.akshare_fetcher import _akshare_call_with_timeout
            filings = _akshare_call_with_timeout(
                ak.stock_zh_a_disclosure_report_cninfo, timeout=15,
                call_name='company_official_filings', symbol=code, market='沪深京',
                start_date=(now - timedelta(days=120)).strftime('%Y%m%d'),
                end_date=now.strftime('%Y%m%d'),
            )
            for _, row in filings.head(12).iterrows():
                title = str(row.get('公告标题') or '')
                url = str(row.get('公告链接') or '')
                published = str(row.get('公告时间') or '')
                if urlparse(url).hostname not in {'static.cninfo.com.cn', 'www.cninfo.com.cn'}:
                    continue
                evidence.append(f'[巨潮官方公告索引，正文尚未读取] {published} {title}\n来源 {url}\n只能确认公告存在，不能推断正文数值。')
        except Exception as exc:
            errors.append(f'巨潮公告索引获取失败 ({type(exc).__name__})')

    # Eastmoney public search requires no API key. Its publisher is retained so
    # syndicated reporting cannot silently become an official company filing.
    try:
        import akshare as ak
        from data_provider.akshare_fetcher import _akshare_call_with_timeout

        keyword = '理想汽车' if code.upper() in _LI_CODES else code
        news = _akshare_call_with_timeout(
            ak.stock_news_em, timeout=15, call_name='company_public_news', symbol=keyword,
        )
        cutoff = (now - timedelta(days=7)).date()
        for _, row in news.head(10).iterrows():
            import pandas as pd
            published = pd.to_datetime(row.get('发布时间'), errors='coerce')
            if pd.isna(published) or not cutoff <= published.date() <= now.date():
                continue
            title = str(row.get('新闻标题') or '')
            url = str(row.get('新闻链接') or '')
            publisher = str(row.get('文章来源') or '')
            if not title or not url.startswith(('https://', 'http://')):
                continue
            evidence.append(
                f'[公开资讯，需区分媒体与公司公告] {published.date()} {title}\n'
                f'来源 {publisher} {url}\n{str(row.get("新闻内容") or "")[:2500]}'
            )
            if len(evidence) >= 10:
                break
    except Exception as exc:
        # Optional external provider failure must remain visible to the report.
        errors.append(f'公开资讯接口获取失败 ({type(exc).__name__})')
    logger.info('[Company disclosures] %s evidence=%d errors=%s', code, len(evidence), len(errors))
    return {'evidence': evidence, 'errors': errors, 'checked_at': now.isoformat(), 'latest_period_seen': latest_period_seen}
