"""Orkestrasi Sinyal A (swing): fetch batch -> hitung -> alert.

Dijalankan sekali per hari bursa setelah closing oleh
.github/workflows/swing_check.yml. Scan seluruh watchlist dalam satu
batch download; hasil dikirim sebagai pesan ringkasan.
"""

import logging
import sys

import yaml

from src.alert import (
    build_messages,
    detection_time_wib,
    format_swing_block,
    send_telegram_message,
)
from src.data_source import create_data_source
from src.signal_swing import check_swing_signal

HISTORY_BUFFER_DAYS = 30
DEFAULT_MAX_ALERTS = 3

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("swing")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def is_liquid_enough(bars: list[dict], period: int, min_avg_value: float) -> bool:
    """Filter likuiditas: rata-rata nilai transaksi `period` hari terakhir.

    Saham tidur menghasilkan level support/resistance dan sinyal yang
    tidak bisa dieksekusi wajar — buang sebelum evaluasi kriteria.
    """
    recent = bars[-period:]
    avg_value = sum(bar["close"] * bar["volume"] for bar in recent) / len(recent)
    return avg_value >= min_avg_value


def run(config: dict) -> int:
    swing_config = config["swing"]
    source = create_data_source(config["data_source"])
    min_avg_value = config.get("min_avg_value_idr", 0)
    tickers = config["tickers"]
    fetch_days = swing_config["ma_period"] + HISTORY_BUFFER_DAYS

    logger.info("scan %d ticker...", len(tickers))
    data = source.fetch_ohlcv_bulk(tickers, fetch_days)

    counts = {"lolos": 0, "gagal": 0, "illiquid": 0, "no_data": 0}
    passing: dict[str, dict] = {}
    for ticker in tickers:
        bars = data.get(ticker)
        if bars is None:
            counts = {**counts, "no_data": counts["no_data"] + 1}
            continue
        if not is_liquid_enough(bars, swing_config["volume_avg_period"], min_avg_value):
            counts = {**counts, "illiquid": counts["illiquid"] + 1}
            continue
        try:
            result = check_swing_signal(bars, swing_config)
        except ValueError:
            counts = {**counts, "no_data": counts["no_data"] + 1}
            continue

        if result["passed"]:
            counts = {**counts, "lolos": counts["lolos"] + 1}
            passing = {**passing, ticker: result}
        else:
            counts = {**counts, "gagal": counts["gagal"] + 1}

    # Rangking berdasarkan risk-reward terbaik, kirim top N saja.
    max_alerts = swing_config.get("max_alerts", DEFAULT_MAX_ALERTS)
    top = sorted(passing, key=lambda t: passing[t]["risk_reward"], reverse=True)[:max_alerts]

    logger.info(
        "hasil: %d lolos (kirim top %d), %d gagal kriteria, %d illiquid, %d tanpa data",
        counts["lolos"], len(top), counts["gagal"], counts["illiquid"], counts["no_data"],
    )
    for ticker in top:
        result = passing[ticker]
        logger.info(
            "%s LOLOS: entry %.0f SL %.0f TP1 %.0f R/R 1:%.2f",
            ticker, result["entry"], result["stop_loss"],
            result["take_profit_1"], result["risk_reward"],
        )

    if not top:
        logger.info("tidak ada sinyal swing hari ini — tidak kirim pesan")
        return 0

    header = (
        f"🅰️ <b>SINYAL A — SWING</b>\n"
        f"Top {len(top)} dari {counts['lolos']} yang lolos 6 kriteria | {detection_time_wib()}"
    )
    blocks = [format_swing_block(ticker, passing[ticker]) for ticker in top]
    for message in build_messages(header, blocks):
        send_telegram_message(message)
    logger.info("alert swing terkirim")
    return 0


if __name__ == "__main__":
    sys.exit(run(load_config()))
