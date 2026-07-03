"""Orkestrasi Sinyal A (swing): fetch -> hitung -> alert.

Dijalankan sekali per hari bursa setelah closing oleh
.github/workflows/swing_check.yml. Semua aktivitas di-log ke stdout
supaya bisa diperiksa di log GitHub Actions.
"""

import logging
import sys

import yaml

from src.alert import format_swing_message, send_telegram_message
from src.data_source import create_data_source
from src.signal_swing import check_swing_signal

HISTORY_BUFFER_DAYS = 30

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("swing")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def run(config: dict) -> int:
    swing_config = config["swing"]
    source = create_data_source(config["data_source"])
    fetch_days = swing_config["ma_period"] + HISTORY_BUFFER_DAYS

    messages: list[str] = []
    for ticker in config["tickers"]:
        try:
            ohlcv = source.fetch_ohlcv(ticker, fetch_days)
            result = check_swing_signal(ohlcv, swing_config)
        except Exception:
            logger.exception("gagal memproses %s, lanjut ke ticker berikutnya", ticker)
            continue

        failed = [name for name, ok in result["criteria"].items() if not ok]
        if result["passed"]:
            logger.info("%s LOLOS semua kriteria swing", ticker)
            messages = messages + [format_swing_message(ticker, result)]
        else:
            logger.info("%s tidak lolos, kriteria gagal: %s", ticker, ", ".join(failed))

    if not messages:
        logger.info("tidak ada sinyal swing hari ini — tidak kirim pesan")
        return 0

    for message in messages:
        send_telegram_message(message)
    logger.info("terkirim %d alert swing ke Telegram", len(messages))
    return 0


if __name__ == "__main__":
    sys.exit(run(load_config()))
