"""Sinyal A — swing trading dengan 6 kriteria berlapis.

Sinyal hanya valid kalau SEMUA kriteria terpenuhi:
1. Trend    : close di atas MA(ma_period)
2. Momentum : RSI(rsi_period) di rentang [rsi_min, rsi_max]
3. Volume   : volume hari sinyal di atas rata-rata volume_avg_period hari sebelumnya
4. Struktur : harga dalam radius X% dari support/resistance terdekat
5. Stop     : swing low terakhir ada dan di bawah harga entry
6. R/R      : (TP1 - entry) / (entry - stop) >= min_risk_reward

Level take profit:
- TP1 = resistance terdekat DI ATAS entry (dipakai untuk kriteria R/R,
  konservatif: sinyal hanya lolos kalau target terdekat pun sudah layak).
- TP2 = resistance berikutnya di atas TP1; kalau tidak ada, fallback
  entry + tp2_risk_multiple x risk (default 2x risk).

Semua threshold dibaca dari config (section `swing` di config.yaml).
"""

from src.indicators import (
    find_support_resistance,
    find_swing_low,
    moving_average,
    rsi,
)

DEFAULT_TP2_RISK_MULTIPLE = 2.0


def check_swing_signal(ohlcv: list[dict], config: dict) -> dict:
    """Evaluasi 6 kriteria swing terhadap data OHLCV harian.

    Asumsi:
    - `ohlcv` urut kronologis; bar terakhir = hari sinyal (setelah closing).
    - Rata-rata volume dihitung dari bar SEBELUM hari sinyal, supaya
      volume hari sinyal dibandingkan ke baseline yang tidak memuat dirinya.
    - Entry price = harga close hari sinyal.

    Returns dict: {passed, criteria, entry, stop_loss, take_profit_1,
    take_profit_2, risk_reward, ma, rsi} — level harga bernilai None
    kalau tidak bisa dihitung.
    """
    _validate_length(ohlcv, config)

    closes = [bar["close"] for bar in ohlcv]
    highs = [bar["high"] for bar in ohlcv]
    lows = [bar["low"] for bar in ohlcv]
    volumes = [bar["volume"] for bar in ohlcv]

    entry = closes[-1]
    ma_value = moving_average(closes, config["ma_period"])
    rsi_value = rsi(closes, config["rsi_period"])
    avg_volume = moving_average(volumes[:-1], config["volume_avg_period"])
    levels = compute_trade_levels(
        ohlcv, config.get("tp2_risk_multiple", DEFAULT_TP2_RISK_MULTIPLE)
    )

    criteria = {
        "trend_above_ma": entry > ma_value,
        "rsi_in_range": config["rsi_min"] <= rsi_value <= config["rsi_max"],
        "volume_above_average": volumes[-1] > avg_volume,
        "near_support_resistance": _is_near_level(
            entry, levels["all_levels"], config["support_resistance_radius_pct"]
        ),
        "stop_loss_valid": levels["stop_loss"] is not None
        and levels["stop_loss"] < entry,
        "risk_reward_ok": levels["risk_reward"] is not None
        and levels["risk_reward"] >= config["min_risk_reward"],
    }

    return {
        "passed": all(criteria.values()),
        "criteria": criteria,
        "entry": entry,
        "stop_loss": levels["stop_loss"],
        "take_profit_1": levels["take_profit_1"],
        "take_profit_2": levels["take_profit_2"],
        "risk_reward": levels["risk_reward"],
        "ma": ma_value,
        "rsi": rsi_value,
    }


def compute_trade_levels(
    ohlcv: list[dict], tp2_risk_multiple: float = DEFAULT_TP2_RISK_MULTIPLE
) -> dict:
    """Level trading dari struktur harga — dipakai sinyal A dan B.

    Entry = close bar terakhir, SL = swing low terakhir, TP1 = resistance
    terdekat di atas entry, TP2 = resistance berikutnya (fallback
    entry + tp2_risk_multiple x risk). Nilai None kalau struktur tidak
    menyediakan levelnya.
    """
    closes = [bar["close"] for bar in ohlcv]
    highs = [bar["high"] for bar in ohlcv]
    lows = [bar["low"] for bar in ohlcv]

    entry = closes[-1]
    supports, resistances = find_support_resistance(highs, lows)
    stop_loss = find_swing_low(lows)
    take_profit_1 = _nearest_above(resistances, entry)
    take_profit_2 = _take_profit_2(
        resistances, entry, stop_loss, take_profit_1, tp2_risk_multiple
    )
    return {
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit_1": take_profit_1,
        "take_profit_2": take_profit_2,
        "risk_reward": _risk_reward(entry, stop_loss, take_profit_1),
        "all_levels": supports + resistances,
    }


def _validate_length(ohlcv: list[dict], config: dict) -> None:
    minimum = max(
        config["ma_period"],
        config["rsi_period"] + 1,
        config["volume_avg_period"] + 1,
    )
    if len(ohlcv) < minimum:
        raise ValueError(f"butuh minimal {minimum} bar OHLCV, dapat {len(ohlcv)}")


def _nearest_above(levels: list[float], price: float) -> float | None:
    """Level terdekat yang berada di atas `price`; None kalau tidak ada."""
    above = [level for level in levels if level > price]
    return min(above) if above else None


def _take_profit_2(
    resistances: list[float],
    entry: float,
    stop_loss: float | None,
    take_profit_1: float | None,
    risk_multiple: float,
) -> float | None:
    """TP2: resistance berikutnya di atas TP1, atau fallback kelipatan risk.

    Kalau struktur harga tidak menyediakan resistance kedua (mis. harga
    mendekati all-time high), TP2 dihitung sebagai entry + risk_multiple x
    (entry - stop) — konsisten dengan kebiasaan target berbasis R-multiple.
    """
    if take_profit_1 is None or stop_loss is None:
        return None
    higher = _nearest_above(resistances, take_profit_1)
    if higher is not None:
        return higher
    risk = entry - stop_loss
    if risk <= 0:
        return None
    return entry + risk_multiple * risk


def _is_near_level(price: float, levels: list[float], radius_pct: float) -> bool:
    """True kalau `price` berjarak <= radius_pct% dari salah satu level."""
    if not levels:
        return False
    nearest_distance = min(abs(price - level) for level in levels)
    return (nearest_distance / price) * 100.0 <= radius_pct


def _risk_reward(
    entry: float, stop_loss: float | None, target: float | None
) -> float | None:
    if stop_loss is None or target is None:
        return None
    risk = entry - stop_loss
    if risk <= 0:
        return None
    return (target - entry) / risk
