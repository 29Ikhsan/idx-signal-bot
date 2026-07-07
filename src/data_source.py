"""Sumber data harga & volume — adapter pattern.

Logic sinyal hanya bergantung pada interface `DataSource`, sehingga sumber
data bisa diganti (API resmi broker, vendor berbayar, dsb.) tanpa mengubah
signal_swing.py / signal_breakout.py.

>>> GANTI DI SINI <<<
Kalau sumber data resmi sudah ditentukan, buat subclass DataSource baru
dan daftarkan di `create_data_source()`. Jangan ubah interface-nya.
"""

import hashlib
import math
from abc import ABC, abstractmethod
from datetime import date, timedelta

MOCK_BASE_VOLUME = 1_000_000


class DataSource(ABC):
    """Interface sumber data. Semua tanggal dalam ISO string (YYYY-MM-DD)."""

    @abstractmethod
    def fetch_ohlcv(self, ticker: str, days: int) -> list[dict]:
        """Data harian OHLCV `days` hari bursa terakhir, urut kronologis.

        Tiap elemen: {date, open, high, low, close, volume}.
        """

    @abstractmethod
    def fetch_latest(self, ticker: str) -> dict:
        """Harga & volume terkini (dipakai sinyal B).

        Return: {date, close, volume}. Saat jam bursa, volume adalah
        volume berjalan hari itu.
        """

    def fetch_ohlcv_bulk(self, tickers: list[str], days: int) -> dict[str, list[dict]]:
        """OHLCV banyak ticker sekaligus: {ticker: bars}.

        Ticker yang gagal diambil TIDAK ada di hasil (bukan raise), supaya
        satu ticker bermasalah tidak menggagalkan scan ratusan lainnya.
        Default: loop fetch_ohlcv; adapter bisa override dengan batch API.
        """
        result: dict[str, list[dict]] = {}
        for ticker in tickers:
            try:
                result = {**result, ticker: self.fetch_ohlcv(ticker, days)}
            except Exception:  # noqa: BLE001 — sengaja: lanjut ke ticker lain
                continue
        return result


class MockDataSource(DataSource):
    """Data sintetis deterministik — HANYA untuk testing/wiring lokal.

    Pola harga: uptrend landai + gelombang sinus, seed dari nama ticker,
    supaya hasil konsisten antar-run tanpa perlu API asli.
    """

    def fetch_ohlcv(self, ticker: str, days: int) -> list[dict]:
        base_price = self._base_price(ticker)
        today = date.today()
        trading_days = _last_weekdays(today, days)
        bars = []
        for i, day in enumerate(trading_days):
            wave = math.sin(i / 5.0) * base_price * 0.03
            trend = i * base_price * 0.001
            close = round(base_price + trend + wave, 2)
            bars = bars + [{
                "date": day.isoformat(),
                "open": round(close * 0.995, 2),
                "high": round(close * 1.01, 2),
                "low": round(close * 0.99, 2),
                "close": close,
                "volume": MOCK_BASE_VOLUME,
            }]
        return bars

    def fetch_latest(self, ticker: str) -> dict:
        latest_bar = self.fetch_ohlcv(ticker, 1)[-1]
        return {
            "date": latest_bar["date"],
            "close": latest_bar["close"],
            "volume": latest_bar["volume"],
        }

    @staticmethod
    def _base_price(ticker: str) -> float:
        seed = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % 1000
        return 1000.0 + seed


class YahooFinanceDataSource(DataSource):
    """Adapter Yahoo Finance via yfinance. Ticker IDX memakai suffix .JK.

    Catatan keterbatasan (sumber tidak resmi, tapi gratis & cukup stabil):
    - Data delayed (bukan real-time tick), cukup untuk sinyal 15-menitan.
    - `fetch_latest` mengembalikan bar harian yang sedang berjalan.

    >>> GANTI DI SINI <<< kalau pindah ke API resmi/berbayar:
    buat class baru dengan interface sama, lalu update create_data_source().
    """

    SUFFIX = ".JK"

    def fetch_ohlcv(self, ticker: str, days: int) -> list[dict]:
        history = self._download_history(ticker, days)
        return _frame_to_bars(history)[-days:]

    def fetch_latest(self, ticker: str) -> dict:
        bars = self.fetch_ohlcv(ticker, 1)
        latest_bar = bars[-1]
        return {
            "date": latest_bar["date"],
            "close": latest_bar["close"],
            "volume": latest_bar["volume"],
        }

    def fetch_ohlcv_bulk(self, tickers: list[str], days: int) -> dict[str, list[dict]]:
        """Batch download via yf.download — satu sesi untuk semua ticker.

        Jauh lebih cepat dan aman dari rate limit dibanding request
        per ticker saat scan ratusan emiten.
        """
        import yfinance  # lazy import: test suite tidak butuh dependency ini

        if len(tickers) == 1:
            return super().fetch_ohlcv_bulk(tickers, days)

        start = date.today() - timedelta(days=days * 2 + 14)
        symbols = [f"{t}{self.SUFFIX}" for t in tickers]
        data = yfinance.download(
            symbols,
            start=start.isoformat(),
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=True,
        )

        result: dict[str, list[dict]] = {}
        for ticker in tickers:
            try:
                frame = data[f"{ticker}{self.SUFFIX}"].dropna(subset=["Close"])
            except KeyError:
                continue
            if frame.empty:
                continue
            result = {**result, ticker: _frame_to_bars(frame)[-days:]}
        return result

    def _download_history(self, ticker: str, days: int):
        import yfinance  # lazy import: test suite tidak butuh dependency ini

        # Buffer 2x hari kalender untuk menutup akhir pekan + libur bursa.
        start = date.today() - timedelta(days=days * 2 + 14)
        symbol = f"{ticker}{self.SUFFIX}"
        history = yfinance.Ticker(symbol).history(start=start.isoformat())
        if history.empty:
            raise ValueError(f"Yahoo Finance tidak mengembalikan data untuk {symbol}")
        return history


def create_data_source(name: str) -> DataSource:
    """Factory: pilih adapter berdasarkan `data_source` di config.yaml."""
    registry = {
        "mock": MockDataSource,
        "yahoo": YahooFinanceDataSource,
    }
    if name not in registry:
        raise ValueError(f"data_source tidak dikenal: {name!r} (pilihan: {sorted(registry)})")
    return registry[name]()


def _frame_to_bars(frame) -> list[dict]:
    """Konversi DataFrame yfinance (index tanggal, kolom OHLCV) ke list bar."""
    bars = []
    for index, row in frame.iterrows():
        bars = bars + [{
            "date": index.date().isoformat(),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
            "volume": float(row["Volume"]),
        }]
    return bars


def _last_weekdays(end: date, count: int) -> list[date]:
    """`count` hari kerja terakhir sampai `end`, urut kronologis."""
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if cursor.weekday() < 5:
            days = [cursor] + days
        cursor = cursor - timedelta(days=1)
    return days
