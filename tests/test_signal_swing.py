"""Test logic sinyal swing: satu skenario lolos penuh, lalu satu skenario
gagal per kriteria. Semua pakai data sample, tanpa API asli.

Geometri skenario LOLOS (periode indikator diperkecil agar data ringkas):
- Uptrend ke 110 (pivot high -> resistance 111), pullback ke 100
  (pivot low -> swing low 99), rebound tutup di 104.
- Entry 104, stop 99 (risk 5), target 111 (reward 7) -> R/R 1.4.
- Volume hari sinyal 5000 vs rata-rata 1000 sebelumnya.
"""

import pytest

from src.signal_swing import check_swing_signal

BASE_CONFIG = {
    "ma_period": 5,
    "rsi_period": 3,
    "rsi_min": 1,     # band lebar: test RSI presisi ada di test_indicators
    "rsi_max": 99,
    "volume_avg_period": 3,
    "support_resistance_radius_pct": 5,
    "min_risk_reward": 1.2,
}

PASSING_CLOSES = [95, 96, 97, 98, 99, 100, 102, 104, 106, 108, 110, 108, 105, 102, 100, 102, 104]


def build_ohlcv(closes: list[float], last_volume: float = 5000) -> list[dict]:
    volumes = [1000.0] * (len(closes) - 1) + [last_volume]
    return [
        {
            "date": f"2026-06-{i + 1:02d}",
            "open": close,
            "high": close + 1,
            "low": close - 1,
            "close": float(close),
            "volume": volume,
        }
        for i, (close, volume) in enumerate(zip(closes, volumes))
    ]


class TestPassingScenario:
    def test_all_criteria_pass(self):
        result = check_swing_signal(build_ohlcv(PASSING_CLOSES), BASE_CONFIG)
        assert result["criteria"] == {name: True for name in result["criteria"]}
        assert result["passed"] is True

    def test_trade_levels_are_derived_from_structure(self):
        result = check_swing_signal(build_ohlcv(PASSING_CLOSES), BASE_CONFIG)
        assert result["entry"] == 104
        assert result["stop_loss"] == 99   # swing low pullback
        assert result["target"] == 111     # resistance puncak sebelumnya
        assert result["risk_reward"] == pytest.approx(1.4)


class TestFailurePerCriterion:
    def test_fails_trend_when_close_below_ma(self):
        closes = PASSING_CLOSES[:-1] + [100]  # tutup di bawah MA5 (~101.8)
        result = check_swing_signal(build_ohlcv(closes), BASE_CONFIG)
        assert result["criteria"]["trend_above_ma"] is False
        assert result["passed"] is False

    def test_fails_rsi_when_outside_configured_range(self):
        config = {**BASE_CONFIG, "rsi_min": 98, "rsi_max": 99}
        result = check_swing_signal(build_ohlcv(PASSING_CLOSES), config)
        assert result["criteria"]["rsi_in_range"] is False
        assert result["passed"] is False

    def test_fails_volume_when_below_average(self):
        result = check_swing_signal(
            build_ohlcv(PASSING_CLOSES, last_volume=900), BASE_CONFIG
        )
        assert result["criteria"]["volume_above_average"] is False
        assert result["passed"] is False

    def test_fails_structure_when_price_far_from_levels(self):
        config = {**BASE_CONFIG, "support_resistance_radius_pct": 0.5}
        result = check_swing_signal(build_ohlcv(PASSING_CLOSES), config)
        assert result["criteria"]["near_support_resistance"] is False
        assert result["passed"] is False

    def test_fails_stop_loss_when_no_swing_low_exists(self):
        rising_closes = [float(c) for c in range(100, 117)]
        result = check_swing_signal(build_ohlcv(rising_closes), BASE_CONFIG)
        assert result["criteria"]["stop_loss_valid"] is False
        assert result["passed"] is False

    def test_fails_risk_reward_when_ratio_below_minimum(self):
        config = {**BASE_CONFIG, "min_risk_reward": 2.0}  # aktual 1.4
        result = check_swing_signal(build_ohlcv(PASSING_CLOSES), config)
        assert result["criteria"]["risk_reward_ok"] is False
        assert result["passed"] is False


class TestInputValidation:
    def test_raises_when_history_too_short(self):
        with pytest.raises(ValueError):
            check_swing_signal(build_ohlcv([100, 101, 102]), BASE_CONFIG)
