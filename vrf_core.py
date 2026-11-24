"""Wykrywanie Wolumenowej Formacji Odwrócenia (VRF) – wspólne dla agenta i backtestu."""
import numpy as np
import pandas as pd

import config as C


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema_f"] = df["Close"].ewm(span=C.EMA_FAST, adjust=False).mean()
    df["ema_s"] = df["Close"].ewm(span=C.EMA_SLOW, adjust=False).mean()
    # średnia wolumenu z poprzednich sesji (bez bieżącej świecy)
    df["vol_sma"] = df["Volume"].shift(1).rolling(C.VOL_SMA).mean()
    df["vol_ratio"] = df["Volume"] / df["vol_sma"]
    rng = (df["High"] - df["Low"]).replace(0, np.nan)
    df["close_pos"] = (df["Close"] - df["Low"]) / rng
    df["prev_low_min"] = df["Low"].shift(1).rolling(C.EXTREME_LOOKBACK).min()
    df["prev_high_max"] = df["High"].shift(1).rolling(C.EXTREME_LOOKBACK).max()
    below = (df["Close"] < df["ema_s"]).astype(int)
    above = (df["Close"] > df["ema_s"]).astype(int)
    df["n_below"] = below.shift(1).rolling(C.TREND_LOOKBACK).sum()
    df["n_above"] = above.shift(1).rolling(C.TREND_LOOKBACK).sum()
    return df


def detect(df: pd.DataFrame) -> pd.DataFrame:
    """Dodaje kolumny: signal (+1 LONG / -1 SHORT / 0), key (key reversal)."""
    df = add_indicators(df)
    vol_ok = df["vol_ratio"] >= C.VOL_MULT

    down = (df["ema_f"].shift(1) < df["ema_s"].shift(1)) & (df["n_below"] >= C.TREND_MIN)
    up = (df["ema_f"].shift(1) > df["ema_s"].shift(1)) & (df["n_above"] >= C.TREND_MIN)

    long_ = down & vol_ok & (df["Low"] <= df["prev_low_min"]) & (df["close_pos"] >= C.CLOSE_POS)
    short = up & vol_ok & (df["High"] >= df["prev_high_max"]) & (df["close_pos"] <= 1 - C.CLOSE_POS)

    df["signal"] = 0
    df.loc[long_, "signal"] = 1
    df.loc[short, "signal"] = -1
    key_long = (df["Low"] < df["Low"].shift(1)) & (df["Close"] > df["Close"].shift(1))
    key_short = (df["High"] > df["High"].shift(1)) & (df["Close"] < df["Close"].shift(1))
    df["key"] = ((df["signal"] == 1) & key_long) | ((df["signal"] == -1) & key_short)
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizuje ramkę z yfinance (MultiIndex kolumn, braki, zerowy wolumen)."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    return df[df["Volume"] > 0]
