from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="0050 溫度計 API")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in ALLOWED_ORIGINS.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def _make_twse_session() -> requests.Session:
    """Create a browser-like session with TWSE cookies."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept":           "application/json, text/javascript, */*; q=0.01",
        "Accept-Language":  "zh-TW,zh;q=0.9,en;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer":          "https://www.twse.com.tw/zh/trading/fund/TWT38U.html",
    })
    try:
        s.get("https://www.twse.com.tw/zh/trading/fund/TWT38U.html", timeout=10)
    except Exception:
        pass
    return s


_twse_session: Optional[requests.Session] = None


def _get_twse_session() -> requests.Session:
    global _twse_session
    if _twse_session is None:
        _twse_session = _make_twse_session()
    return _twse_session

WEIGHTS = {
    "rsi":          0.10,
    "kd":           0.08,
    "macd":         0.09,
    "bias":         0.12,
    "bollinger":    0.06,
    "volume_ratio": 0.05,
    "foreign":      0.15,
    "etf_holders":  0.08,
    "margin":       0.10,
    "big_holder":   0.10,
    "short":        0.07,
}

INDICATOR_META = {
    "rsi":          {"label": "RSI 相對強弱", "weight": 0.10, "category": "technical"},
    "kd":           {"label": "KD 隨機指標",  "weight": 0.08, "category": "technical"},
    "macd":         {"label": "MACD 動能",    "weight": 0.09, "category": "technical"},
    "bias":         {"label": "均線乖離率",    "weight": 0.12, "category": "technical"},
    "bollinger":    {"label": "布林通道 %B",   "weight": 0.06, "category": "technical"},
    "volume_ratio": {"label": "方向量均比",    "weight": 0.05, "category": "technical"},
    "foreign":      {"label": "外資買賣超",    "weight": 0.15, "category": "chip"},
    "etf_holders":  {"label": "ETF 受益人數",  "weight": 0.08, "category": "chip"},
    "margin":       {"label": "融資餘額",      "weight": 0.10, "category": "chip"},
    "big_holder":   {"label": "大戶持股",      "weight": 0.10, "category": "chip"},
    "short":        {"label": "融券餘額",      "weight": 0.07, "category": "chip"},
}


# ─── Caching ──────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now().strftime("%Y%m%d")


def _cache_path(name: str) -> str:
    return os.path.join(CACHE_DIR, f"{name}_{_today()}.json")


def _load_cache(name: str) -> Optional[dict | list]:
    path = _cache_path(name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _save_cache(name: str, data) -> None:
    with open(_cache_path(name), "w") as f:
        json.dump(data, f, ensure_ascii=False)


# ─── TWSE price data ──────────────────────────────────────────────────────────

def _parse_twse_row(row: list) -> Optional[dict]:
    """Parse a TWSE STOCK_DAY row into OHLCV dict."""
    try:
        # row: [民國日期, 成交量, 成交金額, 開盤, 最高, 最低, 收盤, 漲跌, 成交筆數, ...]
        roc_date = row[0].strip()          # e.g. "115/05/22"
        parts = roc_date.split("/")
        year  = int(parts[0]) + 1911
        month = int(parts[1])
        day   = int(parts[2])
        date  = datetime(year, month, day)

        def to_float(s: str) -> float:
            return float(s.replace(",", ""))

        return {
            "date":   date,
            "open":   to_float(row[3]),
            "high":   to_float(row[4]),
            "low":    to_float(row[5]),
            "close":  to_float(row[6]),
            "volume": int(row[1].replace(",", "")),
        }
    except Exception:
        return None


def _fetch_twse_monthly(year: int, month: int) -> list[dict]:
    """Fetch one month of 0050 OHLCV from TWSE."""
    date_str = f"{year}{month:02d}01"
    url = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
    try:
        r = _get_twse_session().get(
            url,
            params={"date": date_str, "stockNo": "0050", "response": "json"},
            timeout=10,
        )
        data = r.json()
        if data.get("stat") != "OK":
            logger.warning("TWSE STOCK_DAY %s-%02d stat: %s", year, month, data.get("stat"))
            return []
        rows = [_parse_twse_row(row) for row in data.get("data", [])]
        return [r for r in rows if r is not None]
    except Exception as e:
        logger.warning("TWSE STOCK_DAY %s-%02d error: %s", year, month, e)
        return []


def get_price_df(months: int = 14) -> pd.DataFrame:
    """Return a DataFrame with OHLCV for 0050, covering ~months of history."""
    cached = _load_cache("price")
    if cached:
        df = pd.DataFrame(cached)
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()
        return df

    records: list[dict] = []
    now = datetime.now()
    # Only fetch months that are >= 2010 (TWSE only goes back to 2010)
    for i in range(months):
        target = now - timedelta(days=30 * i)
        if target.year < 2010:
            break
        month_records = _fetch_twse_monthly(target.year, target.month)
        records.extend(month_records)

    if not records:
        raise HTTPException(status_code=503, detail="無法取得 TWSE 價格資料")

    df = pd.DataFrame(records).drop_duplicates("date").set_index("date").sort_index()
    df.rename(columns={
        "open": "Open", "high": "High",
        "low": "Low",   "close": "Close",
        "volume": "Volume",
    }, inplace=True)

    out = df.reset_index().copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    _save_cache("price", out.to_dict(orient="records"))
    return df


# ─── TWSE chip data ───────────────────────────────────────────────────────────

def _fetch_twse_institutional(date_str: str) -> Optional[dict]:
    """
    Endpoint: https://www.twse.com.tw/fund/TWT38U
    Fields: ['', '證券代號', '證券名稱', '買進', '賣出', '買賣超(外資)',
             '買進', '賣出', '買賣超(投信)', '買進', '賣出', '買賣超(合計)']
    0050 row: [' ','0050  ','元大台灣50',buy,sell,net_foreign,...]
    """
    url = "https://www.twse.com.tw/fund/TWT38U"
    try:
        r = _get_twse_session().get(
            url,
            params={"date": date_str, "response": "json"},
            timeout=10,
        )
        data = r.json()
        if data.get("stat") != "OK":
            return None

        def to_int(s: str) -> int:
            return int(s.replace(",", "").replace("+", "").replace("−", "-").strip())

        for row in data.get("data", []):
            if row[1].strip() == "0050":
                return {
                    "foreign_buy":  to_int(row[3]),
                    "foreign_sell": to_int(row[4]),
                    "foreign_net":  to_int(row[5]),
                }
    except Exception as e:
        logger.debug("TWSE institutional %s: %s", date_str, e)
    return None


def _fetch_twse_margin(date_str: str) -> Optional[dict]:
    """
    Endpoint: https://www.twse.com.tw/exchangeReport/MI_MARGN
    tables[1] fields: ['代號','名稱','買進','賣出','現金償還','前日餘額','今日餘額',
                       '限額','買進','賣出','現券償還','前日餘額','今日餘額','限額','資券互抵','註記']
    0050: row[6] = 融資今日餘額, row[12] = 融券今日餘額
    """
    url = "https://www.twse.com.tw/exchangeReport/MI_MARGN"
    try:
        r = _get_twse_session().get(
            url,
            params={"date": date_str, "selectType": "ALL", "response": "json"},
            timeout=10,
        )
        data = r.json()
        if data.get("stat") != "OK":
            return None

        # table[1] = 融資融券彙總 (全部)
        tables = data.get("tables", [])
        if len(tables) < 2:
            return None

        def to_int(s: str) -> int:
            return int(s.replace(",", "").strip())

        for row in tables[1].get("data", []):
            if row[0] == "0050":
                return {
                    "margin_balance": to_int(row[6]),   # 融資今日餘額
                    "short_balance":  to_int(row[12]),  # 融券今日餘額
                }
    except Exception as e:
        logger.debug("TWSE margin %s: %s", date_str, e)
    return None


def get_chip_df(target_days: int = 40) -> pd.DataFrame:
    cached = _load_cache("chip")
    if cached:
        df = pd.DataFrame(cached)
        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()
            return df

    records: list[dict] = []
    cursor   = datetime.now()
    attempts = 0

    while len(records) < target_days and attempts < target_days * 3:
        if cursor.weekday() < 5:
            ds     = cursor.strftime("%Y%m%d")
            inst   = _fetch_twse_institutional(ds)
            margin = _fetch_twse_margin(ds)
            if inst or margin:
                rec = {"date": cursor.strftime("%Y-%m-%d")}
                if inst:
                    rec.update(inst)
                if margin:
                    rec.update(margin)
                records.append(rec)
                logger.info("Chip fetched: %s", rec["date"])
        cursor -= timedelta(days=1)
        attempts += 1

    if not records:
        return pd.DataFrame()

    df = (
        pd.DataFrame(records)
        .drop_duplicates("date")
        .set_index("date")
        .sort_index()
    )
    df.index = pd.to_datetime(df.index)
    records_out = df.reset_index().copy()
    records_out["date"] = records_out["date"].dt.strftime("%Y-%m-%d")
    _save_cache("chip", records_out.to_dict(orient="records"))
    return df


# ─── Technical indicators ─────────────────────────────────────────────────────

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta    = close.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).clip(0, 100)


def calc_kd(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9):
    lo_n = low.rolling(period).min()
    hi_n = high.rolling(period).max()
    rsv  = ((close - lo_n) / (hi_n - lo_n).replace(0, np.nan) * 100).fillna(50)
    K    = rsv.ewm(com=2, min_periods=period).mean()
    D    = K.ewm(com=2, min_periods=period).mean()
    return K.clip(0, 100), D.clip(0, 100)


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif      = ema_fast - ema_slow
    dea      = dif.ewm(span=signal, adjust=False).mean()
    hist     = 2 * (dif - dea)
    return dif, dea, hist


def calc_bias(close: pd.Series, period: int = 20) -> pd.Series:
    ma = close.rolling(period).mean()
    return (close - ma) / ma * 100


def calc_bollinger_pctb(close: pd.Series, period: int = 20, k: float = 2.0) -> pd.Series:
    ma    = close.rolling(period).mean()
    std   = close.rolling(period).std()
    upper = ma + k * std
    lower = ma - k * std
    return (close - lower) / (upper - lower).replace(0, np.nan)


def calc_dvr(close: pd.Series, volume: pd.Series, period: int = 20) -> pd.Series:
    vol_ma    = volume.rolling(period).mean().replace(0, np.nan)
    direction = close.diff().apply(lambda x: 1 if x > 0 else (-1 if x < 0 else 0))
    return volume / vol_ma * direction


# ─── Normalization ────────────────────────────────────────────────────────────

def norm_pct_rank(series: pd.Series, window: int = 252) -> pd.Series:
    return series.rolling(window, min_periods=30).apply(
        lambda x: float((x < x[-1]).sum()) / len(x) * 100, raw=True
    ).clip(0, 100)


def norm_linear(series: pd.Series, lo: float, hi: float) -> pd.Series:
    return ((series - lo) / (hi - lo) * 100).clip(0, 100)


# ─── Chip scores ──────────────────────────────────────────────────────────────

def score_foreign(chip: pd.DataFrame) -> tuple[float, bool]:
    if "foreign_net" not in chip.columns or len(chip) < 5:
        return 50.0, False
    net20 = chip["foreign_net"].fillna(0).rolling(20, min_periods=5).sum()
    valid = net20.dropna()
    if len(valid) < 5:
        return 50.0, False
    pct = float((valid < valid.iloc[-1]).sum()) / len(valid) * 100
    return round(pct, 1), True


def score_margin(chip: pd.DataFrame) -> tuple[float, bool]:
    if "margin_balance" not in chip.columns or len(chip) < 10:
        return 50.0, False
    margin  = chip["margin_balance"].ffill()
    ma60    = margin.rolling(60, min_periods=10).mean()
    last_ma = ma60.iloc[-1]
    if pd.isna(last_ma) or last_ma == 0:
        return 50.0, False
    chg = (margin.iloc[-1] - last_ma) / last_ma * 100
    return float(norm_linear(pd.Series([chg]), -30, 30).iloc[0]), True


def score_short(chip: pd.DataFrame) -> tuple[float, bool]:
    if "short_balance" not in chip.columns or "margin_balance" not in chip.columns:
        return 50.0, False
    short  = chip["short_balance"].fillna(0)
    margin = chip["margin_balance"].ffill().replace(0, np.nan).ffill()
    ratio  = (short / margin * 100).clip(0, 20)
    score  = float((1 - ratio.iloc[-1] / 20) * 100)
    return round(score, 1), True


# ─── Temperature ──────────────────────────────────────────────────────────────

def compute_temperature(price_df: pd.DataFrame, chip_df: pd.DataFrame) -> dict:
    close  = price_df["Close"]
    high   = price_df["High"]
    low    = price_df["Low"]
    volume = price_df["Volume"]

    rsi             = calc_rsi(close)
    K, D            = calc_kd(high, low, close)
    _, _, macd_hist = calc_macd(close)
    bias            = calc_bias(close)
    pctb            = calc_bollinger_pctb(close)
    dvr             = calc_dvr(close, volume)

    def last(s: pd.Series) -> float:
        v = s.iloc[-1]
        return float(v) if not pd.isna(v) else 50.0

    rsi_score  = round(last(rsi), 1)
    kd_score   = round((last(K) + last(D)) / 2, 1)
    macd_score = round(last(norm_pct_rank(macd_hist)), 1)
    bias_score = round(last(norm_linear(bias, -15, 15)), 1)
    bb_score   = round(float(np.clip(last(pctb) * 100, 0, 100)), 1)
    vr_score   = round(last(norm_linear(dvr, -3, 3)), 1)

    foreign_score, foreign_real = score_foreign(chip_df)
    margin_score,  margin_real  = score_margin(chip_df)
    short_score,   short_real   = score_short(chip_df)

    scores = {
        "rsi":          rsi_score,
        "kd":           kd_score,
        "macd":         macd_score,
        "bias":         bias_score,
        "bollinger":    bb_score,
        "volume_ratio": vr_score,
        "foreign":      foreign_score,
        "etf_holders":  50.0,
        "margin":       margin_score,
        "big_holder":   50.0,
        "short":        short_score,
    }

    temperature = round(sum(scores[k] * WEIGHTS[k] for k in scores), 1)

    data_real = {
        "rsi": True, "kd": True, "macd": True,
        "bias": True, "bollinger": True, "volume_ratio": True,
        "foreign": foreign_real, "etf_holders": False,
        "margin": margin_real,   "big_holder":  False,
        "short": short_real,
    }

    price_now  = round(float(close.iloc[-1]), 2)
    price_prev = round(float(close.iloc[-2]), 2)
    change_pct = round((price_now - price_prev) / price_prev * 100, 2)

    return {
        "temperature":      temperature,
        "scores":           scores,
        "data_real":        data_real,
        "price":            price_now,
        "price_change_pct": change_pct,
        "updated_at":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "meta":             INDICATOR_META,
    }


def compute_history(price_df: pd.DataFrame) -> list[dict]:
    close  = price_df["Close"]
    high   = price_df["High"]
    low    = price_df["Low"]
    volume = price_df["Volume"]

    rsi             = calc_rsi(close)
    K, D            = calc_kd(high, low, close)
    _, _, macd_hist = calc_macd(close)
    bias            = calc_bias(close)
    pctb            = calc_bollinger_pctb(close)
    dvr             = calc_dvr(close, volume)

    rsi_n  = rsi.clip(0, 100)
    kd_n   = ((K + D) / 2).clip(0, 100)
    macd_n = norm_pct_rank(macd_hist)
    bias_n = norm_linear(bias, -15, 15)
    bb_n   = (pctb * 100).clip(0, 100)
    vr_n   = norm_linear(dvr, -3, 3)

    tw    = {k: WEIGHTS[k] for k in ("rsi", "kd", "macd", "bias", "bollinger", "volume_ratio")}
    total = sum(tw.values())

    tech_temp = (
        rsi_n  * (tw["rsi"]          / total) +
        kd_n   * (tw["kd"]           / total) +
        macd_n * (tw["macd"]         / total) +
        bias_n * (tw["bias"]         / total) +
        bb_n   * (tw["bollinger"]    / total) +
        vr_n   * (tw["volume_ratio"] / total)
    )

    result = []
    for date, temp in tech_temp.items():
        p = close.get(date)
        if pd.isna(temp) or p is None or pd.isna(p):
            continue
        result.append({
            "date":      date.strftime("%Y-%m-%d"),
            "tech_temp": round(float(temp), 1),
            "price":     round(float(p), 2),
        })

    return result[-90:]


# ─── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/temperature")
async def api_temperature():
    try:
        price_df = get_price_df()
        chip_df  = get_chip_df()
        return compute_temperature(price_df, chip_df)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("temperature error")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def api_history():
    try:
        price_df = get_price_df()
        return {"data": compute_history(price_df)}
    except Exception as e:
        logger.exception("history error")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "ok", "time": datetime.now().isoformat()}
