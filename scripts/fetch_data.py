#!/usr/bin/env python3
"""
Fetch 0050 OHLCV + chip data from TWSE, calculate temperature,
and write frontend/public/data/latest.json + history.json.

Run locally:  python scripts/fetch_data.py
In CI:        called by GitHub Actions daily after market close.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(REPO_ROOT, "frontend", "public", "data")
os.makedirs(OUTPUT_DIR, exist_ok=True)

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


# ─── TWSE session ─────────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept":          "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer":         "https://www.twse.com.tw/",
    })
    return s


SESSION = make_session()


# ─── Price data ───────────────────────────────────────────────────────────────

def fetch_monthly_ohlcv(year: int, month: int) -> list[dict]:
    url = "https://www.twse.com.tw/rwd/zh/afterTrading/STOCK_DAY"
    try:
        r = SESSION.get(url, params={
            "date": f"{year}{month:02d}01",
            "stockNo": "0050",
            "response": "json",
        }, timeout=15)
        data = r.json()
        if data.get("stat") != "OK":
            return []
        rows = []
        for row in data.get("data", []):
            try:
                parts = row[0].strip().split("/")
                date  = datetime(int(parts[0]) + 1911, int(parts[1]), int(parts[2]))
                rows.append({
                    "date":   date,
                    "Open":   float(row[3].replace(",", "")),
                    "High":   float(row[4].replace(",", "")),
                    "Low":    float(row[5].replace(",", "")),
                    "Close":  float(row[6].replace(",", "")),
                    "Volume": int(row[1].replace(",", "")),
                })
            except Exception:
                continue
        return rows
    except Exception as e:
        logger.warning("OHLCV %d-%02d: %s", year, month, e)
        return []


def get_price_df(months: int = 14) -> pd.DataFrame:
    logger.info("Fetching price data (%d months)…", months)
    records = []
    now = datetime.now()
    for i in range(months):
        target = now - timedelta(days=30 * i)
        if target.year < 2010:
            break
        records.extend(fetch_monthly_ohlcv(target.year, target.month))
    if not records:
        raise RuntimeError("無法取得 TWSE 價格資料")
    df = pd.DataFrame(records).drop_duplicates("date").set_index("date").sort_index()
    logger.info("Price rows: %d", len(df))
    return df


# ─── Chip data ────────────────────────────────────────────────────────────────

def fetch_institutional(date_str: str) -> Optional[dict]:
    try:
        r = SESSION.get("https://www.twse.com.tw/fund/TWT38U", params={
            "date": date_str, "response": "json",
        }, timeout=15)
        data = r.json()
        if data.get("stat") != "OK":
            return None
        for row in data.get("data", []):
            if row[1].strip() == "0050":
                def n(s): return int(s.replace(",", "").replace("+", "").strip())
                return {"foreign_buy": n(row[3]), "foreign_sell": n(row[4]), "foreign_net": n(row[5])}
    except Exception as e:
        logger.debug("Institutional %s: %s", date_str, e)
    return None


def fetch_margin(date_str: str) -> Optional[dict]:
    try:
        r = SESSION.get("https://www.twse.com.tw/exchangeReport/MI_MARGN", params={
            "date": date_str, "selectType": "ALL", "response": "json",
        }, timeout=15)
        data = r.json()
        if data.get("stat") != "OK":
            return None
        tables = data.get("tables", [])
        if len(tables) < 2:
            return None
        for row in tables[1].get("data", []):
            if row[0] == "0050":
                def n(s): return int(s.replace(",", "").strip())
                return {"margin_balance": n(row[6]), "short_balance": n(row[12])}
    except Exception as e:
        logger.debug("Margin %s: %s", date_str, e)
    return None


def get_chip_df(target_days: int = 40) -> pd.DataFrame:
    logger.info("Fetching chip data (up to %d trading days)…", target_days)
    records, cursor, attempts = [], datetime.now(), 0
    while len(records) < target_days and attempts < target_days * 3:
        if cursor.weekday() < 5:
            ds   = cursor.strftime("%Y%m%d")
            inst = fetch_institutional(ds)
            mgn  = fetch_margin(ds)
            if inst or mgn:
                rec = {"date": cursor.strftime("%Y-%m-%d")}
                if inst: rec.update(inst)
                if mgn:  rec.update(mgn)
                records.append(rec)
                logger.info("  chip %s ✓", rec["date"])
        cursor -= timedelta(days=1)
        attempts += 1
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records).drop_duplicates("date").set_index("date").sort_index()
    df.index = pd.to_datetime(df.index)
    logger.info("Chip rows: %d", len(df))
    return df


# ─── Technical indicators ─────────────────────────────────────────────────────

def calc_rsi(c, p=14):
    d=c.diff(); g=d.clip(lower=0); l=(-d).clip(lower=0)
    ag=g.ewm(com=p-1,min_periods=p).mean(); al=l.ewm(com=p-1,min_periods=p).mean()
    return (100-100/(1+ag/al.replace(0,np.nan))).clip(0,100)

def calc_kd(h,l,c,p=9):
    rsv=((c-l.rolling(p).min())/(h.rolling(p).max()-l.rolling(p).min()).replace(0,np.nan)*100).fillna(50)
    K=rsv.ewm(com=2,min_periods=p).mean(); D=K.ewm(com=2,min_periods=p).mean()
    return K.clip(0,100), D.clip(0,100)

def calc_macd(c,fast=12,slow=26,sig=9):
    dif=c.ewm(span=fast,adjust=False).mean()-c.ewm(span=slow,adjust=False).mean()
    dea=dif.ewm(span=sig,adjust=False).mean()
    return 2*(dif-dea)

def calc_bias(c,p=20): ma=c.rolling(p).mean(); return (c-ma)/ma*100
def calc_bb(c,p=20,k=2):
    ma=c.rolling(p).mean(); std=c.rolling(p).std()
    return (c-ma+k*std)/(2*k*std).replace(0,np.nan)
def calc_dvr(c,v,p=20):
    d=c.diff().apply(lambda x:1 if x>0 else(-1 if x<0 else 0))
    return v/v.rolling(p).mean().replace(0,np.nan)*d

def norm_pct(s,w=252):
    return s.rolling(w,min_periods=30).apply(lambda x:float((x<x[-1]).sum())/len(x)*100,raw=True).clip(0,100)
def norm_lin(s,lo,hi): return ((s-lo)/(hi-lo)*100).clip(0,100)


# ─── Chip scores ──────────────────────────────────────────────────────────────

def score_foreign(chip):
    if "foreign_net" not in chip.columns or len(chip)<5: return 50.0,False
    net20=chip["foreign_net"].fillna(0).rolling(20,min_periods=5).sum(); v=net20.dropna()
    if len(v)<5: return 50.0,False
    return round(float((v<v.iloc[-1]).sum())/len(v)*100,1),True

def score_margin(chip):
    if "margin_balance" not in chip.columns or len(chip)<10: return 50.0,False
    m=chip["margin_balance"].ffill(); ma=m.rolling(60,min_periods=10).mean()
    lm=ma.iloc[-1]
    if pd.isna(lm) or lm==0: return 50.0,False
    return float(norm_lin(pd.Series([(m.iloc[-1]-lm)/lm*100]),-30,30).iloc[0]),True

def score_short(chip):
    if "short_balance" not in chip.columns or "margin_balance" not in chip.columns: return 50.0,False
    s=chip["short_balance"].fillna(0); m=chip["margin_balance"].ffill().replace(0,np.nan).ffill()
    r=(s/m*100).clip(0,20)
    return round(float((1-r.iloc[-1]/20)*100),1),True


# ─── Main calculation ─────────────────────────────────────────────────────────

def build_latest(price_df, chip_df):
    c=price_df["Close"]; h=price_df["High"]; l=price_df["Low"]; v=price_df["Volume"]

    rsi=calc_rsi(c); K,D=calc_kd(h,l,c); macd=calc_macd(c)
    bias=calc_bias(c); bb=calc_bb(c); dvr=calc_dvr(c,v)

    def last(s):
        val=s.iloc[-1]; return float(val) if not pd.isna(val) else 50.0

    f_sc, f_real = score_foreign(chip_df)
    m_sc, m_real = score_margin(chip_df)
    s_sc, s_real = score_short(chip_df)

    scores = {
        "rsi":          round(last(rsi),1),
        "kd":           round((last(K)+last(D))/2,1),
        "macd":         round(last(norm_pct(macd)),1),
        "bias":         round(last(norm_lin(bias,-15,15)),1),
        "bollinger":    round(float(np.clip(last(bb)*100,0,100)),1),
        "volume_ratio": round(last(norm_lin(dvr,-3,3)),1),
        "foreign":      f_sc,
        "etf_holders":  50.0,
        "margin":       round(m_sc,1),
        "big_holder":   50.0,
        "short":        s_sc,
    }

    temperature = round(sum(scores[k]*WEIGHTS[k] for k in scores),1)

    price_now  = round(float(c.iloc[-1]),2)
    price_prev = round(float(c.iloc[-2]),2)

    return {
        "temperature":      temperature,
        "scores":           scores,
        "data_real": {
            "rsi":True,"kd":True,"macd":True,"bias":True,
            "bollinger":True,"volume_ratio":True,
            "foreign":f_real,"etf_holders":False,
            "margin":m_real,"big_holder":False,"short":s_real,
        },
        "price":            price_now,
        "price_change_pct": round((price_now-price_prev)/price_prev*100,2),
        "updated_at":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "meta":             INDICATOR_META,
    }


def build_history(price_df):
    c=price_df["Close"]; h=price_df["High"]; l=price_df["Low"]; v=price_df["Volume"]
    rsi=calc_rsi(c); K,D=calc_kd(h,l,c); macd=calc_macd(c)
    bias=calc_bias(c); bb=calc_bb(c); dvr=calc_dvr(c,v)

    rsi_n=rsi.clip(0,100); kd_n=((K+D)/2).clip(0,100)
    macd_n=norm_pct(macd); bias_n=norm_lin(bias,-15,15)
    bb_n=(bb*100).clip(0,100); vr_n=norm_lin(dvr,-3,3)

    tw={k:WEIGHTS[k] for k in ("rsi","kd","macd","bias","bollinger","volume_ratio")}
    tot=sum(tw.values())
    tech=(rsi_n*tw["rsi"]+kd_n*tw["kd"]+macd_n*tw["macd"]+
          bias_n*tw["bias"]+bb_n*tw["bollinger"]+vr_n*tw["volume_ratio"])/tot

    result=[]
    for date,temp in tech.items():
        p=c.get(date)
        if pd.isna(temp) or p is None or pd.isna(p): continue
        result.append({"date":date.strftime("%Y-%m-%d"),"tech_temp":round(float(temp),1),"price":round(float(p),2)})
    return result[-90:]


# ─── Entry point ──────────────────────────────────────────────────────────────

def main():
    logger.info("=== 0050 溫度計資料更新 %s ===", datetime.now().strftime("%Y-%m-%d %H:%M"))
    price_df = get_price_df()
    chip_df  = get_chip_df()

    latest  = build_latest(price_df, chip_df)
    history = build_history(price_df)

    with open(os.path.join(OUTPUT_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(latest, f, ensure_ascii=False, indent=2)
    logger.info("✓ latest.json  temperature=%.1f  price=%.2f", latest["temperature"], latest["price"])

    with open(os.path.join(OUTPUT_DIR, "history.json"), "w", encoding="utf-8") as f:
        json.dump({"data": history}, f, ensure_ascii=False, indent=2)
    logger.info("✓ history.json  %d points", len(history))

    logger.info("=== 完成 ===")


if __name__ == "__main__":
    main()
