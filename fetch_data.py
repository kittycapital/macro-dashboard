"""
글로벌 매크로 대시보드 — 데이터 수집 스크립트
FRED API + OECD 데이터를 수집하여 JSON 파일로 저장

사용법:
  FRED_API_KEY=your_key python fetch_data.py

필요한 패키지:
  pip install requests
"""

import os
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path

FRED_KEY = os.environ.get("FRED_API_KEY", "")
FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

TODAY = datetime.now().strftime("%Y-%m-%d")


def fred_fetch(series_id, start="2000-01-01", freq=None):
    """FRED API에서 시계열 데이터 가져오기"""
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "observation_start": start,
        "sort_order": "asc",
    }
    if freq:
        params["frequency"] = freq
    r = requests.get(FRED_BASE, params=params, timeout=30)
    r.raise_for_status()
    obs = r.json().get("observations", [])
    dates, values = [], []
    for o in obs:
        if o["value"] != ".":
            dates.append(o["date"])
            values.append(float(o["value"]))
    return dates, values


def save_json(filename, data):
    """JSON 파일 저장"""
    path = DATA_DIR / filename
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  ✅ {filename} saved ({len(json.dumps(data))} bytes)")


# ═══════════════════════════════════════
# 1. GLOBAL M2
# ═══════════════════════════════════════
def fetch_m2():
    print("📊 Fetching Global M2...")
    # M2 시리즈 (월간, 조 달러)
    # US: M2SL (billions USD)
    # EU: MYAGM2EZM196N (national currency -> need conversion, use MANMM101EZM189S for index or find USD)
    # Japan: MYAGM2JPM189N (billions yen -> convert)
    # Korea: MYAGM2KRM189S (index) or use BOK data
    # Simplified: Use M2 in national currency and convert roughly

    series = {
        "us": {"id": "M2SL", "divisor": 1000},  # billions -> trillions
        "eu": {"id": "MANMM101EZM189S", "divisor": 1},  # index
        "jp": {"id": "MANMM101JPM189S", "divisor": 1},   # index
        "kr": {"id": "MANMM101KRM189S", "divisor": 1},   # index
    }

    # For total global M2, we use US M2 as the main driver and estimate total
    us_dates, us_values = fred_fetch("M2SL", start="2015-01-01", freq="m")
    us_t = [v / 1000 for v in us_values]  # trillions

    # Rough global M2 estimate: US M2 * ~4.3 (US is ~23% of global M2)
    total_values = [round(v * 4.3, 1) for v in us_t]

    # Individual country M2 (use FRED broad money series)
    countries = {}
    country_series = {
        "us": ("M2SL", 1000, "미국", "🇺🇸"),
        "eu": ("MABMM301EZM189S", 1, "유로존", "🇪🇺"),
        "jp": ("MABMM301JPM189S", 1, "일본", "🇯🇵"),
        "kr": ("MABMM301KRM189S", 1, "한국", "🇰🇷"),
    }

    for key, (sid, div, name, flag) in country_series.items():
        try:
            d, v = fred_fetch(sid, start="2015-01-01", freq="m")
            vals = [round(x / div, 2) if div > 1 else round(x, 2) for x in v]
            # Calculate YoY
            yoy = round(((vals[-1] - vals[-13]) / vals[-13]) * 100, 1) if len(vals) > 13 else 0
            countries[key] = {
                "name": name, "flag": flag, "yoy_pct": yoy,
                "dates": d, "values": vals
            }
        except Exception as e:
            print(f"  ⚠️ {key} M2 fetch failed: {e}")

    # Total YoY
    total_yoy = round(((total_values[-1] - total_values[-13]) / total_values[-13]) * 100, 1) if len(total_values) > 13 else 0

    save_json("m2.json", {
        "last_updated": TODAY,
        "total": {
            "current_value": total_values[-1] if total_values else 0,
            "yoy_pct": total_yoy,
            "unit": "trillion_usd",
            "dates": us_dates,
            "values": total_values
        },
        "countries": countries
    })


# ═══════════════════════════════════════
# 2. FED BALANCE SHEET
# ═══════════════════════════════════════
def fetch_fed_bs():
    print("🏛️ Fetching Fed Balance Sheet...")
    dates, values = fred_fetch("WALCL", start="2008-01-01", freq="w")
    # Convert millions to trillions
    vals_t = [round(v / 1000000, 2) for v in values]

    weekly_change = round(vals_t[-1] - vals_t[-2], 3) if len(vals_t) >= 2 else 0

    save_json("fed_balance_sheet.json", {
        "last_updated": dates[-1] if dates else TODAY,
        "current_value": vals_t[-1] if vals_t else 0,
        "weekly_change": weekly_change,
        "unit": "trillion_usd",
        "dates": dates,
        "values": vals_t
    })


# ═══════════════════════════════════════
# 3. YIELD CURVE
# ═══════════════════════════════════════
def fetch_yield_curve():
    print("📐 Fetching Yield Curve...")
    maturities = {
        "1M": "DGS1MO", "3M": "DGS3MO", "6M": "DGS6MO",
        "1Y": "DGS1", "2Y": "DGS2", "3Y": "DGS3",
        "5Y": "DGS5", "7Y": "DGS7", "10Y": "DGS10",
        "20Y": "DGS20", "30Y": "DGS30"
    }

    current_rates = []
    one_year_ago_rates = []
    one_month_ago_rates = []
    mat_labels = []

    for label, sid in maturities.items():
        try:
            dates, values = fred_fetch(sid, start="2023-01-01")
            if values:
                current_rates.append(values[-1])
                mat_labels.append(label)

                # 1 year ago (approx -252 trading days)
                target_1y = len(values) - 252
                one_year_ago_rates.append(values[max(0, target_1y)])

                # 1 month ago (approx -22 trading days)
                target_1m = len(values) - 22
                one_month_ago_rates.append(values[max(0, target_1m)])
        except Exception as e:
            print(f"  ⚠️ {label} yield fetch failed: {e}")

    # Calculate spreads
    rate_map = dict(zip(mat_labels, current_rates))
    spread_2s10s = round(rate_map.get("10Y", 0) - rate_map.get("2Y", 0), 2)
    spread_3m10y = round(rate_map.get("10Y", 0) - rate_map.get("3M", 0), 2)

    def spread_status(s):
        if s < -0.1: return "INVERTED"
        if s < 0.1: return "FLAT"
        return "NORMAL"

    save_json("yield_curve.json", {
        "last_updated": TODAY,
        "current": {"maturities": mat_labels, "rates": current_rates},
        "one_month_ago": {"date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"), "rates": one_month_ago_rates},
        "one_year_ago": {"date": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"), "rates": one_year_ago_rates},
        "spreads": {
            "2s10s": spread_2s10s,
            "3m10y": spread_3m10y,
            "2s10s_status": spread_status(spread_2s10s),
            "3m10y_status": spread_status(spread_3m10y)
        }
    })


# ═══════════════════════════════════════
# 4. NFCI (Financial Conditions)
# ═══════════════════════════════════════
def fetch_nfci():
    print("🌡️ Fetching NFCI...")
    dates, values = fred_fetch("NFCI", start="2000-01-01", freq="w")
    vals = [round(v, 2) for v in values]
    current = vals[-1] if vals else 0

    if current < -0.3:
        status, status_en = "완화적", "loose"
    elif current < 0:
        status, status_en = "다소 완화적", "slightly_loose"
    elif current < 0.3:
        status, status_en = "다소 긴축적", "slightly_tight"
    else:
        status, status_en = "긴축적", "tight"

    save_json("nfci.json", {
        "last_updated": dates[-1] if dates else TODAY,
        "current_value": current,
        "status": status,
        "status_en": status_en,
        "dates": dates,
        "values": vals
    })


# ═══════════════════════════════════════
# 5. INTEREST RATES (G7 + Korea)
# ═══════════════════════════════════════
def fetch_rates():
    print("🏦 Fetching Interest Rates...")
    # Central bank policy rates from FRED
    rate_series = {
        "us": ("DFEDTARU", "미국", "🇺🇸", "Fed"),     # Fed upper target
        "kr": ("IRSTCI01KRM156N", "한국", "🇰🇷", "BOK"),
        "eu": ("ECBMRRFR", "유로존", "🇪🇺", "ECB"),    # ECB main refinancing rate
        "jp": ("IRSTCI01JPM156N", "일본", "🇯🇵", "BOJ"),
        "cn": ("INTDSRCNM193N", "중국", "🇨🇳", "PBoC"),  # PBoC discount rate
    }

    all_dates = set()
    series_data = {}
    countries_info = {}

    for key, (sid, name, flag, bank) in rate_series.items():
        try:
            d, v = fred_fetch(sid, start="2000-01-01", freq="m")
            series_data[key] = dict(zip(d, v))
            all_dates.update(d)
            # Current and previous
            current = v[-1] if v else 0
            prev = v[-2] if len(v) >= 2 else current
            countries_info[key] = {
                "name": name, "flag": flag, "bank": bank,
                "current": round(current, 2),
                "prev_change": round(current - prev, 2)
            }
        except Exception as e:
            print(f"  ⚠️ {key} rate fetch failed: {e}")

    # Align dates
    sorted_dates = sorted(all_dates)
    aligned_series = {}
    for key in series_data:
        aligned_series[key] = []
        last_val = 0
        for d in sorted_dates:
            if d in series_data[key]:
                last_val = round(series_data[key][d], 2)
            aligned_series[key].append(last_val)

    save_json("rates.json", {
        "last_updated": TODAY,
        "countries": countries_info,
        "dates": sorted_dates,
        "series": aligned_series
    })


# ═══════════════════════════════════════
# 6. DEBT / GDP
# ═══════════════════════════════════════
def fetch_debt_gdp():
    print("💳 Fetching Debt/GDP...")
    debt_series = {
        "us": ("GFDEGDQ188S", "미국", "🇺🇸"),       # US federal debt/GDP quarterly
        "jp": ("GGGDTAJPA188N", "일본", "🇯🇵"),      # Japan govt debt/GDP annual
        "eu": ("GGGDTAEZA188N", "유로존", "🇪🇺"),     # Euro area
        "kr": ("GGGDTAKRA188N", "한국", "🇰🇷"),       # Korea
        "cn": ("GGGDTACNA188N", "중국", "🇨🇳"),       # China
    }

    all_dates = set()
    series_data = {}
    countries_info = {}

    for key, (sid, name, flag) in debt_series.items():
        try:
            d, v = fred_fetch(sid, start="2000-01-01", freq="a")
            # Use yearly labels
            yearly_dates = [dt[:4] for dt in d]
            series_data[key] = dict(zip(yearly_dates, v))
            all_dates.update(yearly_dates)
            current = round(v[-1]) if v else 0
            countries_info[key] = {"name": name, "flag": flag, "current": current}
        except Exception as e:
            print(f"  ⚠️ {key} debt/GDP fetch failed: {e}")

    sorted_dates = sorted(all_dates)
    aligned_series = {}
    for key in series_data:
        aligned_series[key] = []
        last_val = 0
        for d in sorted_dates:
            if d in series_data[key]:
                last_val = round(series_data[key][d])
            aligned_series[key].append(last_val)

    save_json("debt_gdp.json", {
        "last_updated": TODAY,
        "countries": countries_info,
        "dates": sorted_dates,
        "series": aligned_series
    })


# ═══════════════════════════════════════
# 7. GLOBAL PMI (OECD CLI as proxy)
# ═══════════════════════════════════════
def fetch_pmi():
    print("🏭 Fetching PMI (OECD CLI)...")
    # OECD CLI (Composite Leading Indicators) — free, no API key
    # Alternatively use FRED's OECD CLI series
    pmi_series = {
        "us": ("USALOLITONOSTSAM", "미국", "🇺🇸"),
        "jp": ("JPNLOLITONOSTSAM", "일본", "🇯🇵"),
        "eu": ("EA19LOLITONOSTSAM", "유로존", "🇪🇺"),
        "kr": ("KORLOLITONOSTSAM", "한국", "🇰🇷"),
        "cn": ("CHNLOLITONOSTSAM", "중국", "🇨🇳"),
    }

    all_dates = set()
    series_data = {}
    countries_info = {}

    for key, (sid, name, flag) in pmi_series.items():
        try:
            d, v = fred_fetch(sid, start="2015-01-01", freq="m")
            # CLI is centered at 100, convert to PMI-like (centered at 50)
            # PMI ≈ (CLI - 100) * 5 + 50 (rough mapping)
            pmi_vals = [round(max(30, min(65, (x - 100) * 5 + 50)), 1) for x in v]
            series_data[key] = dict(zip(d, pmi_vals))
            all_dates.update(d)

            current = pmi_vals[-1] if pmi_vals else 50
            prev = pmi_vals[-2] if len(pmi_vals) >= 2 else current
            countries_info[key] = {
                "name": name, "flag": flag,
                "current": current,
                "prev_change": round(current - prev, 1)
            }
        except Exception as e:
            print(f"  ⚠️ {key} PMI fetch failed: {e}")

    sorted_dates = sorted(all_dates)
    aligned_series = {}
    for key in series_data:
        aligned_series[key] = []
        last_val = 50
        for d in sorted_dates:
            if d in series_data[key]:
                last_val = series_data[key][d]
            aligned_series[key].append(last_val)

    save_json("pmi.json", {
        "last_updated": TODAY,
        "countries": countries_info,
        "dates": sorted_dates,
        "series": aligned_series
    })


# ═══════════════════════════════════════
# 8. UNEMPLOYMENT RATE
# ═══════════════════════════════════════
def fetch_unemployment():
    print("👷 Fetching Unemployment Rate...")
    unemp_series = {
        "us": ("UNRATE", "미국", "🇺🇸"),
        "kr": ("LRUN64TTKRM156S", "한국", "🇰🇷"),
        "eu": ("LRHUTTTTEZM156S", "유로존", "🇪🇺"),
        "jp": ("LRUN64TTJPM156S", "일본", "🇯🇵"),
        "cn": ("LRUN64TTCNM156S", "중국", "🇨🇳"),
    }

    all_dates = set()
    series_data = {}
    countries_info = {}

    for key, (sid, name, flag) in unemp_series.items():
        try:
            d, v = fred_fetch(sid, start="2000-01-01", freq="m")
            vals = [round(x, 1) for x in v]
            series_data[key] = dict(zip(d, vals))
            all_dates.update(d)

            current = vals[-1] if vals else 0
            prev = vals[-2] if len(vals) >= 2 else current
            countries_info[key] = {
                "name": name, "flag": flag,
                "current": current,
                "prev_change": round(current - prev, 1)
            }
        except Exception as e:
            print(f"  ⚠️ {key} unemployment fetch failed: {e}")

    sorted_dates = sorted(all_dates)
    aligned_series = {}
    for key in series_data:
        aligned_series[key] = []
        last_val = 0
        for d in sorted_dates:
            if d in series_data[key]:
                last_val = series_data[key][d]
            aligned_series[key].append(last_val)

    save_json("unemployment.json", {
        "last_updated": TODAY,
        "countries": countries_info,
        "dates": sorted_dates,
        "series": aligned_series
    })


# ═══════════════════════════════════════
# MAIN
# ═══════════════════════════════════════
def main():
    print(f"🚀 글로벌 매크로 대시보드 데이터 수집 시작 ({TODAY})")
    print(f"   FRED API Key: {'✅ 설정됨' if FRED_KEY else '❌ 없음'}")
    print()

    if not FRED_KEY:
        print("❌ FRED_API_KEY 환경변수를 설정해주세요.")
        print("   https://fred.stlouisfed.org/docs/api/api_key.html 에서 무료 발급")
        return

    tasks = [
        ("Global M2", fetch_m2),
        ("Fed Balance Sheet", fetch_fed_bs),
        ("Yield Curve", fetch_yield_curve),
        ("NFCI", fetch_nfci),
        ("Interest Rates", fetch_rates),
        ("Debt/GDP", fetch_debt_gdp),
        ("PMI", fetch_pmi),
        ("Unemployment", fetch_unemployment),
    ]

    for name, func in tasks:
        try:
            func()
        except Exception as e:
            print(f"  ❌ {name} failed: {e}")

    print()
    print("✅ 데이터 수집 완료!")


if __name__ == "__main__":
    main()
