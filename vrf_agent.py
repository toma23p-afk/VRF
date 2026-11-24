"""Agent VRF – Wolumenowa Formacja Odwrócenia, alerty na Telegram.

Uruchamiany co 15 min (GitHub Actions). W każdym przebiegu, osobno dla GPW i USA:
  1. Po zamknięciu sesji (raz dziennie) skanuje zamkniętą świecę dzienną -> alert "VRF".
  2. W trakcie kolejnych sesji pilnuje potwierdzenia (wybicie max/min świecy
     sygnałowej) -> alert "VRF POTW" z wejściem, SL i celami 1R/2R/3R.
  3. Sygnał wygasa po CONFIRM_BARS sesjach albo gdy cena przebije świecę w złą stronę.
Stan (oczekujące sygnały, daty skanów) trzymany w state/vrf_state.json.
"""
import json
import os
import sys
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import yfinance as yf

import config as C
from vrf_core import clean, detect

STATE_FILE = Path(__file__).parent / "state" / "vrf_state.json"
SCAN_DELAY_MIN = 25  # Yahoo ma ~15 min opóźnienia dla GPW


# ---------- pomocnicze ----------
def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"scanned": {}, "pending": []}


def save_state(st):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(st, indent=2, ensure_ascii=False))


def tg(msg: str):
    token, chat = os.getenv("TELEGRAM_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    print(msg, "\n---")
    if not token or not chat:
        return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": msg, "parse_mode": "HTML"}, timeout=20)
    except Exception as e:
        print("Telegram error:", e)


def hm(s):
    h, m = map(int, s.split(":"))
    return time(h, m)


def fmt(x):
    return f"{x:,.2f}".replace(",", " ")


def download(tickers, period):
    data = yf.download(tickers, period=period, interval="1d", group_by="ticker",
                       auto_adjust=False, progress=False, threads=True)
    out = {}
    for t in tickers:
        try:
            df = data[t] if len(tickers) > 1 else data
            df = clean(df)
            if len(df):
                out[t] = df
        except Exception:
            pass
    return out


def name(t):
    return t.replace(".WA", "")


# ---------- 1. skan po zamknięciu ----------
def eod_scan(market, cfg, st, today):
    frames = download(cfg["tickers"], "6mo")
    # wygaszanie: każda nowa zamknięta sesja zmniejsza licznik
    for p in st["pending"]:
        if p["market"] == market and p["date"] < today:
            p["bars_left"] -= 1
    expired = [p for p in st["pending"] if p["market"] == market and p["bars_left"] <= 0]
    for p in expired:
        print(f"Wygasł: {p['ticker']} {p['date']}")
    st["pending"] = [p for p in st["pending"] if p not in expired]

    hits = []
    for t, df in frames.items():
        if df.index[-1].date().isoformat() != today:
            continue  # brak dzisiejszej świecy (święto / brak danych)
        d = detect(df)
        row = d.iloc[-1]
        if row["signal"] == 0:
            continue
        side = "LONG" if row["signal"] == 1 else "SHORT"
        hits.append((t, side, row))
        st["pending"].append({
            "market": market, "ticker": t, "side": side, "date": today,
            "high": float(row["High"]), "low": float(row["Low"]),
            "bars_left": C.CONFIRM_BARS,
        })

    for t, side, r in hits:
        trig = r["High"] if side == "LONG" else r["Low"]
        sl = r["Low"] if side == "LONG" else r["High"]
        arrow = "🟢" if side == "LONG" else "🔴"
        tg(f"{arrow} <b>VRF {side}</b> {'(KEY REVERSAL) ' if r['key'] else ''}– <b>{name(t)}</b>\n"
           f"Kulminacja wolumenu: {r['vol_ratio']:.1f}× średniej 20 sesji\n"
           f"Zamknięcie {fmt(r['Close'])} ({r['close_pos']*100:.0f}% zakresu świecy)\n"
           f"Czekam na potwierdzenie: {'wybicie powyżej' if side=='LONG' else 'zejście poniżej'} "
           f"{fmt(trig)} w ciągu {C.CONFIRM_BARS} sesji\nSL: {fmt(sl)}")
    print(f"{market}: skan {today}, sygnałów {len(hits)}")


# ---------- 2. potwierdzenia w trakcie sesji ----------
def check_confirmations(market, st, today):
    pend = [p for p in st["pending"] if p["market"] == market and p["date"] < today]
    if not pend:
        return
    frames = download(sorted({p["ticker"] for p in pend}), "5d")
    done = []
    for p in pend:
        df = frames.get(p["ticker"])
        if df is None or df.index[-1].date().isoformat() != today:
            continue
        bar = df.iloc[-1]
        hi, lo, last = float(bar["High"]), float(bar["Low"]), float(bar["Close"])
        if p["side"] == "LONG":
            confirmed, broken = hi > p["high"], lo < p["low"]
            entry, sl = p["high"], p["low"]
        else:
            confirmed, broken = lo < p["low"], hi > p["high"]
            entry, sl = p["low"], p["high"]
        r = abs(entry - sl)
        if confirmed and not broken:
            sgn = 1 if p["side"] == "LONG" else -1
            tg(f"✅ <b>VRF POTW {p['side']}</b> – <b>{name(p['ticker'])}</b> (świeca z {p['date']})\n"
               f"Wejście: {fmt(entry)} | teraz {fmt(last)}\nSL: {fmt(sl)} (ryzyko {r/entry*100:.1f}%)\n"
               f"Cele: 1R {fmt(entry+sgn*r)} | 2R {fmt(entry+sgn*2*r)} | 3R {fmt(entry+sgn*3*r)}")
            done.append(p)
        elif broken:
            tg(f"⚪ VRF anulowany – {name(p['ticker'])} ({p['side']}, {p['date']}): "
               f"cena przebiła świecę sygnałową w złą stronę")
            done.append(p)
    st["pending"] = [p for p in st["pending"] if p not in done]


# ---------- main ----------
def main():
    st = load_state()
    force = "--scan" in sys.argv  # ręczny skan ostatniej świecy
    for market, cfg in C.MARKETS.items():
        tz = ZoneInfo(cfg["tz"])
        now = datetime.now(tz)
        if now.weekday() >= 5:
            continue
        today = now.date().isoformat()
        o, c = hm(cfg["open"]), hm(cfg["close"])
        in_session = o <= now.time() <= c
        after_close = now >= datetime.combine(now.date(), c, tz) + timedelta(minutes=SCAN_DELAY_MIN)

        if in_session:
            check_confirmations(market, st, today)
        if (after_close or force) and st["scanned"].get(market) != today:
            check_confirmations(market, st, today)  # domknięcie dnia przed skanem
            eod_scan(market, cfg, st, today)
            st["scanned"][market] = today
    save_state(st)


if __name__ == "__main__":
    main()
