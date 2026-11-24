"""Backtest VRF na danych dziennych z Yahoo.

Warianty wejścia:
  POTW  – wejście po potwierdzeniu: wybicie max (LONG) / min (SHORT) świecy sygnałowej
          w ciągu CONFIRM_BARS sesji, po cenie wybicia (lub otwarcia przy luce).
  NEXT  – wejście na otwarciu sesji po świecy sygnałowej (bez potwierdzenia).
SL zawsze za ekstremum świecy sygnałowej. Wyjścia: cel 1R/2R/3R albo wyjście czasowe
po BT_TIME_EXIT sesjach (wariant "czas"). Gdy SL i cel w tej samej świecy -> liczymy SL
(konserwatywnie). Wynik w R (wielokrotność ryzyka), bez prowizji.

Użycie:  python backtest.py [GPW|USA|ALL]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import config as C
from vrf_core import clean, detect

OUT = Path(__file__).parent / "results"


def simulate(df, i, side, entry_mode):
    """Zwraca listę (wariant, R) dla sygnału na świecy i."""
    sgn = 1 if side == 1 else -1
    sig_hi, sig_lo = df["High"].iat[i], df["Low"].iat[i]
    sl = sig_lo if sgn == 1 else sig_hi
    n = len(df)

    if entry_mode == "NEXT":
        j = i + 1
        if j >= n:
            return None
        entry = df["Open"].iat[j]
        if (entry - sl) * sgn <= 0:  # luka za SL
            return None
    else:  # POTW
        j, entry = None, None
        for k in range(i + 1, min(i + 1 + C.CONFIRM_BARS, n)):
            o, h, l = df["Open"].iat[k], df["High"].iat[k], df["Low"].iat[k]
            trig = sig_hi if sgn == 1 else sig_lo
            hit = h > trig if sgn == 1 else l < trig
            if hit:
                j = k
                entry = max(o, trig) if sgn == 1 else min(o, trig)
                break
            broken = l < sig_lo if sgn == 1 else h > sig_hi
            if broken:
                return None
        if j is None:
            return None

    risk = abs(entry - sl)
    if risk <= 0:
        return None
    res = {"entry_date": df.index[j].date(), "entry": entry, "sl": sl, "risk_pct": risk / entry * 100}

    for tgt in C.BT_TARGETS_R + ["czas"]:
        tp = entry + sgn * tgt * risk if tgt != "czas" else None
        r = None
        last = min(j + C.BT_TIME_EXIT, n - 1)
        for k in range(j, last + 1):
            h, l = df["High"].iat[k], df["Low"].iat[k]
            # w świecy wejścia sprawdzamy SL tylko poniżej/powyżej ceny wejścia (jest zawsze)
            if (l <= sl) if sgn == 1 else (h >= sl):
                r = -1.0
                break
            if tp is not None and ((h >= tp) if sgn == 1 else (l <= tp)):
                r = float(tgt)
                break
        if r is None:  # wyjście czasowe na zamknięciu
            r = (df["Close"].iat[last] - entry) * sgn / risk
        res[f"R_{tgt}"] = r
    return res


def stats(s: pd.Series):
    if len(s) == 0:
        return {}
    wins, losses = s[s > 0], s[s <= 0]
    pf = wins.sum() / abs(losses.sum()) if losses.sum() != 0 else np.inf
    return {"transakcji": len(s), "trafność_%": round(len(wins) / len(s) * 100, 1),
            "śr_R": round(s.mean(), 3), "suma_R": round(s.sum(), 1),
            "profit_factor": round(pf, 2)}


def run(tickers, label):
    data = yf.download(tickers, period=C.BT_PERIOD, interval="1d", group_by="ticker",
                       auto_adjust=True, progress=False, threads=True)
    trades = []
    for t in tickers:
        try:
            df = clean(data[t] if len(tickers) > 1 else data)
        except Exception:
            continue
        if len(df) < 60:
            continue
        d = detect(df)
        for i in np.flatnonzero(d["signal"].values != 0):
            side = int(d["signal"].iat[i])
            for mode in ("POTW", "NEXT"):
                r = simulate(d, i, side, mode)
                if r:
                    trades.append({"ticker": t, "signal_date": d.index[i].date(),
                                   "side": "LONG" if side == 1 else "SHORT", "tryb": mode,
                                   "key": bool(d["key"].iat[i]),
                                   "vol_ratio": round(d["vol_ratio"].iat[i], 2), **r})
    tr = pd.DataFrame(trades)
    OUT.mkdir(exist_ok=True)
    if tr.empty:
        print(f"{label}: brak transakcji")
        return ""
    tr.to_csv(OUT / f"trades_{label}.csv", index=False)

    rows = []
    for (mode, side), g in tr.groupby(["tryb", "side"]):
        for tgt in C.BT_TARGETS_R + ["czas"]:
            rows.append({"tryb": mode, "strona": side, "wyjście": f"{tgt}R" if tgt != "czas" else f"czas {C.BT_TIME_EXIT}d",
                         **stats(g[f"R_{tgt}"])})
    # key reversal vs reszta (POTW, cel 2R)
    for k, g in tr[tr.tryb == "POTW"].groupby("key"):
        rows.append({"tryb": "POTW", "strona": "KEY" if k else "bez KEY", "wyjście": "2R", **stats(g["R_2"])})
    summ = pd.DataFrame(rows)
    summ.to_csv(OUT / f"summary_{label}.csv", index=False)
    txt = f"=== {label} | {C.BT_PERIOD} | {tr.ticker.nunique()} spółek ===\n" + summ.to_string(index=False)
    (OUT / f"summary_{label}.txt").write_text(txt)
    print(txt)
    return txt


if __name__ == "__main__":
    which = (sys.argv[1] if len(sys.argv) > 1 else "GPW").upper()
    out = []
    if which in ("GPW", "ALL"):
        out.append(run(C.GPW, "GPW"))
    if which in ("USA", "ALL"):
        out.append(run(C.USA, "USA"))
