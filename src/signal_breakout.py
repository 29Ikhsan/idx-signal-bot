"""Sinyal B — breakout volume intraday.

Fungsi tunggal: volume berjalan hari ini di atas `threshold` kali
rata-rata volume N hari sebelumnya (N diatur di config.yaml).
"""


def check_breakout(latest: dict, avg_volume: float, threshold: float) -> bool:
    """True kalau volume di `latest` menembus threshold x rata-rata.

    Asumsi:
    - `latest["volume"]` adalah volume berjalan hari ini (bukan final),
      jadi sinyal bisa muncul kapan pun selama jam bursa begitu ambang
      terlampaui — tidak perlu menunggu closing.
    - `avg_volume` dihitung TANPA hari ini, supaya baseline tidak
      terkontaminasi lonjakan yang sedang dideteksi.
    - `avg_volume` <= 0 dianggap data tidak sehat -> tidak ada sinyal.
    """
    if avg_volume <= 0:
        return False
    return latest["volume"] > threshold * avg_volume
