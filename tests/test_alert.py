"""Test penggabungan blok sinyal jadi pesan Telegram."""

from src.alert import build_messages, format_breakout_block


class TestFormatBreakoutBlock:
    def test_includes_levels(self):
        levels = {"stop_loss": 95.0, "take_profit_1": 110.0, "take_profit_2": 120.0}
        block = format_breakout_block("TEST", 100.0, 5.3, levels)
        assert "TEST" in block and "5.3x" in block
        assert "SL 95" in block and "TP1 110" in block and "TP2 120" in block

    def test_missing_levels_shown_as_dash(self):
        levels = {"stop_loss": None, "take_profit_1": None, "take_profit_2": None}
        block = format_breakout_block("TEST", 100.0, 2.1, levels)
        assert "SL -" in block and "TP1 -" in block and "TP2 -" in block


class TestBuildMessages:
    def test_no_blocks_means_no_messages(self):
        assert build_messages("HEADER", []) == []

    def test_few_blocks_fit_in_one_message(self):
        messages = build_messages("HEADER", ["blok satu", "blok dua"])
        assert len(messages) == 1
        assert messages[0].startswith("HEADER")
        assert "blok satu" in messages[0] and "blok dua" in messages[0]

    def test_splits_when_over_limit_and_repeats_header(self):
        blocks = [f"blok-{i:02d} " + "x" * 80 for i in range(10)]
        messages = build_messages("HEADER", blocks, char_limit=300)
        assert len(messages) > 1
        assert all(message.startswith("HEADER") for message in messages)
        joined = "\n".join(messages)
        assert all(f"blok-{i:02d}" in joined for i in range(10))

    def test_every_message_respects_limit(self):
        blocks = ["y" * 100 for _ in range(20)]
        messages = build_messages("HEADER", blocks, char_limit=400)
        assert all(len(message) <= 400 for message in messages)
