"""Orkestrasi Sinyal B (breakout volume): fetch -> hitung -> alert.

Dijalankan tiap 15 menit selama jam bursa oleh
.github/workflows/breakout_check.yml. Log ke stdout untuk GitHub Actions.
"""

import logging
import sys

import yaml

from src.alert import format_breakout_message, send_telegram_message
from src.data_source import create_data_source
from src.signal_breakout import check_breakout

HISTORY_BUFFER_DAYS = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("breakout")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def average_volume(history: list[dict], latest_date: str, period: int) -> float:
    """Rata-rata volume `period` hari SEBELUM hari ini.

    Bar dengan tanggal sama dengan `latest_date` dibuang supaya lonjakan
    hari ini tidak ikut menaikkan baseline-nya sendiri.
    """
    past_volumes = [bar["volume"] for bar in history if bar["date"] != latest_date]
    if len(past_volumes) < period:
        raise ValueError(f"riwayat volume kurang: butuh {period}, dapat {len(past_volumes)}")
    return sum(past_volumes[-period:]) / period


def run(config: dict) -> int:
    breakout_config = config["breakout"]
    source = create_data_source(config["data_source"])
    period = breakout_config["volume_avg_period"]
    threshold = breakout_config["volume_threshold"]

    messages: list[str] = []
    for ticker in config["tickers"]:
        try:
            history = source.fetch_ohlcv(ticker, period + HISTORY_BUFFER_DAYS)
            latest = source.fetch_latest(ticker)
            avg_volume = average_volume(history, latest["date"], period)
        except Exception:
            logger.exception("gagal memproses %s, lanjut ke ticker berikutnya", ticker)
            continue

        ratio = latest["volume"] / avg_volume
        if check_breakout(latest, avg_volume, threshold):
            logger.info("%s BREAKOUT: volume %.1fx rata-rata", ticker, ratio)
            messages = messages + [
                format_breakout_message(ticker, latest["close"], ratio)
            ]
        else:
            logger.info("%s normal: volume %.1fx rata-rata (threshold %.1fx)", ticker, ratio, threshold)

    if not messages:
        logger.info("tidak ada breakout — tidak kirim pesan")
        return 0

    for message in messages:
        send_telegram_message(message)
    logger.info("terkirim %d alert breakout ke Telegram", len(messages))
    return 0


if __name__ == "__main__":
    sys.exit(run(load_config()))
