"""State alert breakout antar-run: cegah spam alert berulang.

Tanpa ini, saham yang breakout jam 09.15 akan dikirim ulang tiap 15 menit
sampai closing. State disimpan sebagai file JSON kecil dan dipersist antar
run GitHub Actions lewat actions/cache (lihat breakout_check.yml).
"""

import json
import os

EMPTY_STATE: dict = {"date": None, "alerted": []}


def load_state(path: str) -> dict:
    """Baca state dari file; state kosong kalau file tidak ada/korup."""
    try:
        with open(path, encoding="utf-8") as state_file:
            state = json.load(state_file)
    except (FileNotFoundError, json.JSONDecodeError):
        return dict(EMPTY_STATE)
    if not isinstance(state, dict) or "alerted" not in state:
        return dict(EMPTY_STATE)
    return state


def save_state(path: str, state: dict) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as state_file:
        json.dump(state, state_file)


def filter_new_alerts(
    tickers: list[str], state: dict, today: str | None
) -> tuple[list[str], dict]:
    """Pisahkan ticker yang BELUM pernah dialert hari ini.

    State dari hari sebelumnya otomatis di-reset (dedup hanya berlaku
    dalam satu hari bursa). Return (ticker_baru, state_berikutnya) —
    state lama tidak dimutasi.
    """
    already = set(state.get("alerted", [])) if state.get("date") == today else set()
    new_tickers = [ticker for ticker in tickers if ticker not in already]
    next_state = {"date": today, "alerted": sorted(already | set(tickers))}
    return new_tickers, next_state
