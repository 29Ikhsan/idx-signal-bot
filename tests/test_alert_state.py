"""Test dedup alert harian dan persistensi state."""

from src.alert_state import filter_new_alerts, load_state, save_state


class TestFilterNewAlerts:
    def test_all_new_when_state_empty(self):
        new, state = filter_new_alerts(["AAAA", "BBBB"], {"date": None, "alerted": []}, "2026-07-07")
        assert new == ["AAAA", "BBBB"]
        assert state == {"date": "2026-07-07", "alerted": ["AAAA", "BBBB"]}

    def test_already_alerted_today_is_suppressed(self):
        state = {"date": "2026-07-07", "alerted": ["AAAA"]}
        new, next_state = filter_new_alerts(["AAAA", "BBBB"], state, "2026-07-07")
        assert new == ["BBBB"]
        assert next_state["alerted"] == ["AAAA", "BBBB"]

    def test_new_day_resets_dedup(self):
        state = {"date": "2026-07-06", "alerted": ["AAAA"]}
        new, next_state = filter_new_alerts(["AAAA"], state, "2026-07-07")
        assert new == ["AAAA"]
        assert next_state == {"date": "2026-07-07", "alerted": ["AAAA"]}

    def test_input_state_is_not_mutated(self):
        state = {"date": "2026-07-07", "alerted": ["AAAA"]}
        filter_new_alerts(["BBBB"], state, "2026-07-07")
        assert state == {"date": "2026-07-07", "alerted": ["AAAA"]}


class TestStatePersistence:
    def test_missing_file_returns_empty_state(self, tmp_path):
        assert load_state(str(tmp_path / "nope.json")) == {"date": None, "alerted": []}

    def test_corrupt_file_returns_empty_state(self, tmp_path):
        path = tmp_path / "state.json"
        path.write_text("{bukan json")
        assert load_state(str(path)) == {"date": None, "alerted": []}

    def test_roundtrip(self, tmp_path):
        path = str(tmp_path / "sub" / "state.json")
        save_state(path, {"date": "2026-07-07", "alerted": ["AAAA"]})
        assert load_state(path) == {"date": "2026-07-07", "alerted": ["AAAA"]}
