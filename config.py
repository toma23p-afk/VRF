"""Konfiguracja agenta VRF (Wolumenowa Formacja Odwrócenia)."""

# --- Uniwersum (tylko instrumenty z prawdziwym wolumenem: akcje) ---
# WIG20 – sprawdź aktualny skład po każdej rewizji GPW (marzec/czerwiec/wrzesień/grudzień)
# CCC -> MDV (Modivo, od 19.02.2026), SPL -> EBP (Erste Bank Polska, od 28.04.2026)
WIG20 = [
    "ALE", "ALR", "BDX", "CDR", "DNP", "EBP", "KGH", "KRU", "KTY", "LPP",
    "MBK", "MDV", "PCO", "PEO", "PGE", "PKN", "PKO", "PZU", "TPE", "ZAB",
]
GPW = [f"{t}.WA" for t in WIG20]

USA = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "AMD", "NFLX",
    "JPM", "BAC", "XOM", "CVX", "LLY", "UNH", "WMT", "COST", "ORCL", "PLTR",
    "MSTR", "RIVN", "HOOD", "COIN",
]

MARKETS = {
    # godziny lokalne sesji, strefa czasowa, opóźnienie danych Yahoo (min)
    "GPW": {"tickers": GPW, "tz": "Europe/Warsaw", "open": "09:00", "close": "17:05"},
    "USA": {"tickers": USA, "tz": "America/New_York", "open": "09:30", "close": "16:00"},
}

# --- Parametry formacji ---
VOL_SMA = 20            # średnia wolumenu (bez bieżącej świecy)
VOL_MULT = 2.0          # wolumen świecy >= VOL_MULT * SMA(20)
CLOSE_POS = 0.60        # LONG: zamknięcie w górnych 40% zakresu (>= 0.60); SHORT: <= 0.40
EXTREME_LOOKBACK = 10   # świeca robi najniższy dołek / najwyższy szczyt z N sesji
EMA_FAST = 9
EMA_SLOW = 26
TREND_LOOKBACK = 10     # trend przed świecą: min. TREND_MIN z ostatnich N zamknięć po złej stronie EMA26
TREND_MIN = 6
CONFIRM_BARS = 3        # potwierdzenie: wybicie max/min świecy sygnałowej w ciągu N sesji

# --- Alerty agenta ---
# Backtest GPW 10 lat: LONG ma przewagę, SHORT ~0. Domyślnie tylko LONG.
SHORT_MODE = "off"      # "off" – brak alertów SHORT | "info" – sam alert, bez POTW | "full" – jak LONG
MAIN_TARGET_R = 3       # główny cel w alercie POTW

# --- Backtest ---
BT_PERIOD = "10y"
BT_TIME_EXIT = 10       # wyjście czasowe po N sesjach
BT_TARGETS_R = [1, 2, 3]
