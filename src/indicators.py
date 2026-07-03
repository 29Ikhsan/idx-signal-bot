"""Indikator teknikal sebagai pure function.

Semua fungsi di modul ini: input berupa list angka, output angka/list,
tanpa efek samping. Tidak ada I/O, tidak ada state — memudahkan unit test.
"""

DEFAULT_PIVOT_WINDOW = 2


def moving_average(values: list[float], period: int) -> float:
    """Simple moving average dari `period` nilai terakhir.

    Asumsi: `values` urut kronologis (paling lama di depan).
    Raises ValueError kalau data kurang dari `period`.
    """
    if period <= 0:
        raise ValueError("period harus > 0")
    if len(values) < period:
        raise ValueError(f"butuh minimal {period} data, dapat {len(values)}")
    return sum(values[-period:]) / period


def rsi(closes: list[float], period: int = 14) -> float:
    """Relative Strength Index dengan smoothing Wilder.

    Asumsi perhitungan:
    - `closes` urut kronologis, butuh minimal period+1 titik.
    - Rata-rata gain/loss awal = SMA `period` delta pertama,
      selanjutnya di-smooth ala Wilder: avg = (avg*(period-1) + delta) / period.
    - Semua delta nol (harga flat) -> 50.0 (netral).
    - Tidak ada loss sama sekali -> 100.0.
    """
    if len(closes) < period + 1:
        raise ValueError(f"butuh minimal {period + 1} closes, dapat {len(closes)}")

    deltas = [closes[i + 1] - closes[i] for i in range(len(closes) - 1)]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    relative_strength = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + relative_strength)


def find_support_resistance(
    highs: list[float],
    lows: list[float],
    window: int = DEFAULT_PIVOT_WINDOW,
) -> tuple[list[float], list[float]]:
    """Deteksi level support & resistance via pivot point sederhana.

    Sebuah bar adalah pivot high (resistance) kalau high-nya adalah maksimum
    dari `window` bar di kiri dan kanannya; pivot low (support) analog dengan
    minimum. Metode ini sengaja sederhana untuk v1 — bukan clustering level.

    Returns (supports, resistances), masing-masing urut kronologis.
    """
    if len(highs) != len(lows):
        raise ValueError("highs dan lows harus sama panjang")

    supports: list[float] = []
    resistances: list[float] = []
    for i in range(window, len(highs) - window):
        neighborhood_high = highs[i - window : i + window + 1]
        neighborhood_low = lows[i - window : i + window + 1]
        if highs[i] == max(neighborhood_high):
            resistances = resistances + [highs[i]]
        if lows[i] == min(neighborhood_low):
            supports = supports + [lows[i]]
    return supports, resistances


def find_swing_low(lows: list[float], window: int = DEFAULT_PIVOT_WINDOW) -> float | None:
    """Swing low terakhir: pivot low paling baru dari deret `lows`.

    Dipakai sebagai level stop loss sinyal swing. Return None kalau
    tidak ada pivot low yang terdeteksi (mis. harga naik terus).
    """
    supports, _ = find_support_resistance(lows, lows, window)
    return supports[-1] if supports else None
