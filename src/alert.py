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


MESSAGE_CHAR_LIMIT = 3500  # batas aman di bawah limit 4096 Telegram


def format_swing_block(ticker: str, result: dict) -> str:
    """Blok ringkas satu ticker untuk pesan gabungan Sinyal A."""
    tp2 = result["take_profit_2"]
    tp2_text = f"{tp2:,.0f}" if tp2 is not None else "-"
    return (
        f"📈 <b>{ticker}</b> — entry {result['entry']:,.0f}\n"
        f"SL {result['stop_loss']:,.0f} | TP1 {result['take_profit_1']:,.0f} | "
        f"TP2 {tp2_text} | R/R 1:{result['risk_reward']:.2f}"
    )


def format_breakout_block(ticker: str, price: float, volume_ratio: float) -> str:
    """Baris ringkas satu ticker untuk pesan gabungan Sinyal B."""
    return f"🔊 <b>{ticker}</b> — {price:,.0f} | vol {volume_ratio:.1f}x rata-rata"


def build_messages(
    header: str, blocks: list[str], char_limit: int = MESSAGE_CHAR_LIMIT
) -> list[str]:
    """Gabungkan blok jadi sesedikit mungkin pesan, tiap pesan <= char_limit.

    Semua sinyal satu run masuk pesan gabungan (bukan satu pesan per ticker)
    supaya scan ratusan emiten tidak membanjiri notifikasi. Tiap pesan
    lanjutan tetap diawali header agar konteksnya jelas.
    """
    if not blocks:
        return []

    messages: list[str] = []
    current = header
    for block in blocks:
        candidate = f"{current}\n\n{block}"
        if len(candidate) > char_limit and current != header:
            messages = messages + [current]
            current = f"{header}\n\n{block}"
        else:
            current = candidate
    return messages + [current]
