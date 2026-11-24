# VRF – Wolumenowa Formacja Odwrócenia

Agent wysyła na Telegram alerty kulminacji wolumenu na akcjach WIG20 i dużych spółkach z USA.

## Reguły (świeca dzienna, zamknięta)
**LONG (kulminacja sprzedaży)**
- trend spadkowy: EMA9 < EMA26 i co najmniej 6 z ostatnich 10 zamknięć pod EMA26
- świeca robi najniższy dołek z 10 sesji
- zamknięcie w górnych 40% zakresu świecy
- wolumen ≥ 2× średnia z 20 poprzednich sesji

**SHORT (kulminacja kupna)**: to samo w lustrzanym odbiciu.

Dopisek **KEY REVERSAL** pojawia się, gdy świeca ma niższy dołek i zamyka się powyżej poprzedniego zamknięcia (dla SHORT odwrotnie).

## Alerty
| Alert | Kiedy |
|---|---|
| 🟢/🔴 `VRF LONG/SHORT` | ok. 25 min po zamknięciu sesji (GPW i USA osobno) |
| ✅ `VRF POTW` | w trakcie jednej z 3 kolejnych sesji cena wybija max (LONG) / min (SHORT) świecy sygnałowej. Alert podaje wejście, SL i cele 1R/2R/3R |
| ⚪ `VRF anulowany` | cena przebiła świecę sygnałową w złą stronę, zanim przyszło potwierdzenie |

Wszystkie parametry są w `config.py`.

## Instalacja
1. Utwórz prywatne repo, np. `toma23p-afk/VRF`, i wrzuć do niego zawartość paczki.
2. W **Settings → Secrets and variables → Actions** dodaj `TELEGRAM_TOKEN` i `TELEGRAM_CHAT_ID`. Możesz użyć tego samego bota co agent EMA albo założyć nowego w @BotFather.
3. Zakładka **Actions**: włącz workflowy.
   - **VRF backtest** → *Run workflow*, market = `GPW` (albo `USA`, `ALL`). Podsumowanie przyjdzie na Telegram, a pełne CSV z transakcjami będzie w artefakcie `vrf-backtest`.
   - **VRF agent** startuje sam co 15 min w dni robocze.

## Backtest – co liczy
- **POTW**: wejście po potwierdzeniu (wybicie świecy w ciągu 3 sesji). **NEXT**: wejście na otwarciu następnej sesji, bez potwierdzenia.
- SL zawsze za ekstremum świecy sygnałowej. Wynik liczony w R.
- Wyjścia: cel 1R, 2R, 3R albo wyjście czasowe po 10 sesjach. Gdy SL i cel wypadają w tej samej świecy, liczony jest SL (wersja konserwatywna). Bez prowizji.
- Osobny wiersz porównuje świece KEY z resztą.

Uwaga: backtest używa obecnego składu WIG20 (survivorship bias), więc wyniki mogą wyjść trochę zawyżone.
