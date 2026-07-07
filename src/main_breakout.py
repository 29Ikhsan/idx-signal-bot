"""Orkestrasi Sinyal B (breakout volume): fetch batch -> hitung -> alert.

Dijalankan tiap 15 menit selama jam bursa oleh
.github/workflows/breakout_check.yml. Scan seluruh watchlist (bisa
ratusan emiten) dalam satu batch download, dedup alert per hari via
alert_state, dan kirim hasil sebagai pesan ringkasan.
"""

import logging
import os
import sys

import yaml

from src.alert import (
    build_messages,
    detection_time_wib,
    format_breakout_block,
    send_telegram_message,
)
from src.alert_state import filter_new_alerts, load_state, save_state
from src.data_source import create_data_source
from src.signal_breakout import check_breakout

HISTORY_BUFFER_DAYS = 5
DEFAULT_STATE_PATH = ".state/breakout_alerts.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("breakout")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, encoding="utf-8") as config_file:
        return yaml.safe_load(config_file)


def evaluate_breakout(
    bars: list[dict] | None, period: int, threshold: float, min_avg_value: float
) -> tuple[str, tuple | None]:
    """Evaluasi satu ticker -> (status, payload).

    Status: "hit" (payload = (harga, rasio)), "quiet", "illiquid", "no_data".
    Rata-rata volume & nilai transaksi dihitung dari bar SEBELUM hari ini,
    supaya lonjakan hari ini tidak menaikkan baseline-nya sendiri.
    """
    if not bars or len(bars) < period + 1:
        return "no_data", None
    latest, past = bars[-1], bars[-period - 1 : -1]  # `period` bar sebelum latest
    avg_volume = sum(bar["volume"] for bar in past) / period
    avg_value = sum(bar["close"] * bar["volume"] for bar in past) / period
    if avg_volume <= 0 or avg_value < min_avg_value:
        return "illiquid", None
    if check_breakout(latest, avg_volume, threshold):
        return "hit", (latest["close"], latest["volume"] / avg_volume)
    return "quiet", None


def run(config: dict) -> int:
    breakout_config = config["breakout"]
    source = create_data_source(config["data_source"])
    period = breakout_config["volume_avg_period"]
    threshold = breakout_config["volume_threshold"]
    min_avg_value = config.get("min_avg_value_idr", 0)
    tickers = config["tickers"]
    state_path = os.environ.get("ALERT_STATE_PATH", DEFAULT_STATE_PATH)

    logger.info("scan %d ticker (threshold %.1fx)...", len(tickers), threshold)
    data = source.fetch_ohlcv_bulk(tickers, period + 1 + HISTORY_BUFFER_DAYS)

    counts = {"quiet": 0, "illiquid": 0, "no_data": 0}
    hits: dict[str, tuple] = {}
    for ticker in tickers:
        status, payload = evaluate_breakout(
            data.get(ticker), period, threshold, min_avg_value
        )
        if status == "hit":
            hits = {**hits, ticker: payload}
        else:
            counts = {**counts, status: counts[status] + 1}

    today = next((data[t][-1]["date"] for t in hits), None)
    state = load_state(state_path)
    new_tickers, next_state = filter_new_alerts(sorted(hits), state, today)
    save_state(state_path, next_state)

    logger.info(
        "hasil: %d breakout (%d baru), %d sepi, %d illiquid, %d tanpa data",
        len(hits), len(new_tickers), counts["quiet"], counts["illiquid"], counts["no_data"],
    )
    for ticker in new_tickers:
        logger.info("%s BREAKOUT: harga %.0f, volume %.1fx", ticker, *hits[ticker])

    if not new_tickers:
        logger.info("tidak ada breakout baru — tidak kirim pesan")
        return 0

    header = (
        f"🅱️ <b>SINYAL B — BREAKOUT VOLUME</b>\n"
        f"{len(new_tickers)} ticker baru | {detection_time_wib()}"
    )
    blocks = [format_breakout_block(t, *hits[t]) for t in new_tickers]
    messages = build_messages(header, blocks)
    for message in messages:
        send_telegram_message(message)
    logger.info("terkirim %d pesan alert breakout", len(messages))
    return 0


if __name__ == "__main__":
    sys.exit(run(load_config()))
