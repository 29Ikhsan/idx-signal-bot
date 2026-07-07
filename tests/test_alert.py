"""Test penggabungan blok sinyal jadi pesan Telegram."""

from src.alert import build_messages


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
