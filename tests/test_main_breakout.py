"""Test evaluasi breakout per ticker (mode scan papan penuh)."""

from src.main_breakout import evaluate_breakout


def make_bars(volumes: list[float], close: float = 1000.0) -> list[dict]:
    return [
        {"date": f"2026-06-{i + 1:02d}", "open": close, "high": close + 5,
         "low": close - 5, "close": close, "volume": volume}
        for i, volume in enumerate(volumes)
    ]


class TestEvaluateBreakout:
    def test_hit_when_volume_spikes(self):
        bars = make_bars([1000] * 20 + [5000])
        status, payload = evaluate_breakout(bars, period=20, threshold=2.0, min_avg_value=0)
        assert status == "hit"
        price, ratio = payload
        assert price == 1000.0
        assert ratio == 5.0

    def test_quiet_when_volume_normal(self):
        bars = make_bars([1000] * 20 + [1200])
        status, _ = evaluate_breakout(bars, period=20, threshold=2.0, min_avg_value=0)
        assert status == "quiet"

    def test_todays_spike_not_in_its_own_baseline(self):
        # Baseline = 20 bar SEBELUM hari ini; lonjakan 5000 tidak ikut.
        bars = make_bars([1000] * 20 + [5000])
        _, payload = evaluate_breakout(bars, period=20, threshold=2.0, min_avg_value=0)
        assert payload[1] == 5.0  # 5000/1000, bukan 5000/1190

    def test_illiquid_when_avg_value_below_minimum(self):
        # close 1000 x vol 1000 = Rp 1 jt/hari << minimum Rp 500 jt
        bars = make_bars([1000] * 20 + [5000])
        status, _ = evaluate_breakout(bars, period=20, threshold=2.0, min_avg_value=500_000_000)
        assert status == "illiquid"

    def test_no_data_when_history_too_short(self):
        status, _ = evaluate_breakout(make_bars([1000] * 5), period=20, threshold=2.0, min_avg_value=0)
        assert status == "no_data"

    def test_no_data_when_bars_missing(self):
        status, _ = evaluate_breakout(None, period=20, threshold=2.0, min_avg_value=0)
        assert status == "no_data"
