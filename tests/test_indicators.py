"""Test indikator dengan data sample yang hasilnya sudah diketahui.

Tidak ada panggilan API — semua input adalah list angka literal.
"""

import pytest

from src.indicators import (
    find_support_resistance,
    find_swing_low,
    moving_average,
    rsi,
)

# Deret zigzag: naik ke puncak 110 (pivot high), pullback ke 100 (pivot low),
# lalu rebound. high = close+1, low = close-1.
ZIGZAG_CLOSES = [95, 96, 97, 98, 99, 100, 102, 104, 106, 108, 110, 108, 105, 102, 100, 102, 104]
ZIGZAG_HIGHS = [c + 1 for c in ZIGZAG_CLOSES]
ZIGZAG_LOWS = [c - 1 for c in ZIGZAG_CLOSES]


class TestMovingAverage:
    def test_averages_last_period_values(self):
        assert moving_average([1, 2, 3, 4, 5], 5) == 3.0

    def test_uses_only_tail_of_series(self):
        assert moving_average([1, 2, 3, 4, 5], 2) == 4.5

    def test_raises_when_data_shorter_than_period(self):
        with pytest.raises(ValueError):
            moving_average([1, 2], 5)


class TestRsi:
    def test_returns_100_when_prices_only_rise(self):
        closes = list(range(100, 120))
        assert rsi(closes, 14) == 100.0

    def test_returns_0_when_prices_only_fall(self):
        closes = list(range(120, 100, -1))
        assert rsi(closes, 14) == 0.0

    def test_returns_neutral_50_when_prices_flat(self):
        assert rsi([100.0] * 20, 14) == 50.0

    def test_stays_within_bounds_for_mixed_series(self):
        value = rsi(ZIGZAG_CLOSES, 3)
        assert 0.0 < value < 100.0

    def test_raises_when_data_too_short(self):
        with pytest.raises(ValueError):
            rsi([1, 2, 3], 14)


class TestSupportResistance:
    def test_finds_pivot_high_as_resistance(self):
        _, resistances = find_support_resistance(ZIGZAG_HIGHS, ZIGZAG_LOWS)
        assert 111 in resistances  # puncak 110 + 1

    def test_finds_pivot_low_as_support(self):
        supports, _ = find_support_resistance(ZIGZAG_HIGHS, ZIGZAG_LOWS)
        assert 99 in supports  # lembah pullback 100 - 1

    def test_no_pivots_in_strictly_rising_series(self):
        highs = [float(i) for i in range(100, 115)]
        lows = [h - 1 for h in highs]
        supports, resistances = find_support_resistance(highs, lows)
        assert supports == []
        assert resistances == []


class TestSwingLow:
    def test_returns_most_recent_pivot_low(self):
        assert find_swing_low(ZIGZAG_LOWS) == 99

    def test_returns_none_when_no_pivot_exists(self):
        assert find_swing_low([float(i) for i in range(100, 115)]) is None
