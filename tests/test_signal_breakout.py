"""Test logic breakout volume dengan data sample, tanpa API asli."""

from src.signal_breakout import check_breakout


def make_latest(volume: float) -> dict:
    return {"date": "2026-07-03", "close": 5000.0, "volume": volume}


class TestCheckBreakout:
    def test_triggers_when_volume_exceeds_threshold(self):
        assert check_breakout(make_latest(2500), avg_volume=1000, threshold=2.0) is True

    def test_no_signal_when_volume_below_threshold(self):
        assert check_breakout(make_latest(1500), avg_volume=1000, threshold=2.0) is False

    def test_no_signal_at_exact_threshold(self):
        # Tepat di ambang belum dianggap breakout (harus DI ATAS threshold).
        assert check_breakout(make_latest(2000), avg_volume=1000, threshold=2.0) is False

    def test_no_signal_when_average_volume_is_zero(self):
        assert check_breakout(make_latest(2500), avg_volume=0, threshold=2.0) is False

    def test_threshold_is_configurable(self):
        assert check_breakout(make_latest(1600), avg_volume=1000, threshold=1.5) is True
