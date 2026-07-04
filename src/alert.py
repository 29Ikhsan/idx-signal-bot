"""Kirim alert ke Telegram via Bot API.

Kredensial dibaca dari environment variable (di GitHub Actions diisi
lewat Secrets — JANGAN pernah hardcode token di kode/config):
- TELEGRAM_BOT_TOKEN : token dari @BotFather
- TELEGRAM_CHAT_ID   : chat ID tujuan (lihat README cara mendapatkannya)
"""

import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests

TELEGRAM_TIMEOUT_SECONDS = 15
WIB = ZoneInfo("Asia/Jakarta")


def send_telegram_message(text: str) -> None:
    """Kirim satu pesan. Raise kalau kredensial kosong atau API gagal —

    biar kegagalan terlihat jelas di log GitHub Actions, bukan diam-diam.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID belum diset. "
            "Isi sebagai GitHub Secrets (lihat README)."
        )

    response = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=TELEGRAM_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise RuntimeError(
            f"Telegram API gagal ({response.status_code}): {response.text}"
        )


def detection_time_wib() -> str:
    """Waktu deteksi dalam WIB, format mudah dibaca di pesan alert."""
    return datetime.now(tz=WIB).strftime("%Y-%m-%d %H:%M WIB")


def format_swing_message(ticker: str, result: dict) -> str:
    """Pesan Sinyal A: entry, stop, TP1/TP2, R/R, kriteria, waktu deteksi."""
    criteria_lines = "\n".join(
        f"  {'✅' if passed else '❌'} {name}"
        for name, passed in result["criteria"].items()
    )
    tp2 = result["take_profit_2"]
    tp2_text = f"{tp2:,.0f}" if tp2 is not None else "-"
    return (
        f"🅰️ <b>SINYAL A — SWING</b>\n"
        f"Ticker: <b>{ticker}</b>\n"
        f"Entry: {result['entry']:,.0f}\n"
        f"Stop loss: {result['stop_loss']:,.0f}\n"
        f"Take profit 1: {result['take_profit_1']:,.0f}\n"
        f"Take profit 2: {tp2_text}\n"
        f"Risk-reward (TP1): 1:{result['risk_reward']:.2f}\n"
        f"Kriteria:\n{criteria_lines}\n"
        f"Terdeteksi: {detection_time_wib()}"
    )


def format_breakout_message(ticker: str, price: float, volume_ratio: float) -> str:
    """Pesan Sinyal B: harga terakhir, rasio volume, waktu deteksi."""
    return (
        f"🅱️ <b>SINYAL B — BREAKOUT VOLUME</b>\n"
        f"Ticker: <b>{ticker}</b>\n"
        f"Harga terakhir: {price:,.0f}\n"
        f"Volume: {volume_ratio:.1f}x rata-rata\n"
        f"Terdeteksi: {detection_time_wib()}"
    )
