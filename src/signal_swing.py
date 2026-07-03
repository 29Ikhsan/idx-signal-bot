"""Sinyal A — swing trading dengan 6 kriteria berlapis.

Sinyal hanya valid kalau SEMUA kriteria terpenuhi:
1. Trend    : close di atas MA(ma_period)
2. Momentum : RSI(rsi_period) di rentang [rsi_min, rsi_max]
3. Volume   : volume hari sinyal di atas rata-rata volume_avg_period hari sebelumnya
4. Struktur : harga dalam radius X% dari support/resistance terdekat
5. Stop     : swing low terakhir ada dan di bawah harga entry
6. R/R      : (target - entry) / (entry - stop) >= min_risk_reward,
              dengan target = resistance terdekat DI ATAS entry

Semua threshold dibaca dari config (section `swing` di config.yaml).
"""

from src.indicators import (
    find_support_resistance,
    find_swing_low,
    moving_average,
    rsi,
)


def check_swing_signal(ohlcv: list[dict], config: dict) -> dict:
    """Evaluasi 6 kriteria swing terhadap data OHLCV harian.

    Asumsi:
    - `ohlcv` urut kronologis; bar terakhir = hari sinyal (setelah closing).
    - Rata-rata volume dihitung dari bar SEBELUM hari sinyal, supaya
      volume hari sinyal dibandingkan ke baseline yang tidak memuat dirinya.
    - Entry price = harga close hari sinyal.

    Returns dict: {passed, criteria, entry, stop_loss, target, risk_reward,
    ma, rsi} — level harga bernilai None kalau tidak bisa dihitung.
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
    supports, resistances = find_support_resistance(highs, lows)
    stop_loss = find_swing_low(lows)
    target = _nearest_above(resistances, entry)
    risk_reward = _risk_reward(entry, stop_loss, target)

    criteria = {
        "trend_above_ma": entry > ma_value,
        "rsi_in_range": config["rsi_min"] <= rsi_value <= config["rsi_max"],
        "volume_above_average": volumes[-1] > avg_volume,
        "near_support_resistance": _is_near_level(
            entry, supports + resistances, config["support_resistance_radius_pct"]
        ),
        "stop_loss_valid": stop_loss is not None and stop_loss < entry,
        "risk_reward_ok": risk_reward is not None
        and risk_reward >= config["min_risk_reward"],
    }

    return {
        "passed": all(criteria.values()),
        "criteria": criteria,
        "entry": entry,
        "stop_loss": stop_loss,
        "target": target,
        "risk_reward": risk_reward,
        "ma": ma_value,
        "rsi": rsi_value,
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
