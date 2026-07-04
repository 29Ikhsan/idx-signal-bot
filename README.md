# idx-signal-bot

Sistem semi-otomatis pemantau sinyal trading saham IDX. Jalan otomatis lewat GitHub Actions — tanpa laptop menyala, tanpa biaya server. Sistem ini **murni observasi dan notifikasi**: tidak ada eksekusi order, eksekusi tetap manual lewat aplikasi broker.

## Dua sinyal

| | Sinyal A — Swing | Sinyal B — Breakout Volume |
|---|---|---|
| Tujuan | Posisi beberapa hari–minggu | Deteksi lonjakan volume intraday |
| Jadwal | 1x per hari bursa, 16.30 WIB | Tiap 15 menit selama jam bursa |
| Logic | 6 kriteria berlapis (semua harus lolos) | Volume hari ini > 2x rata-rata 20 hari |
| Workflow | `.github/workflows/swing_check.yml` | `.github/workflows/breakout_check.yml` |

Kedua sinyal jalan independen. Satu ticker bisa memicu A, B, keduanya, atau tidak sama sekali.

### Kriteria Sinyal A (semua harus terpenuhi)

1. **Trend** — close di atas MA50
2. **Momentum** — RSI(14) di rentang 40–60 (rebound)
3. **Volume** — volume hari sinyal di atas rata-rata 20 hari
4. **Struktur** — harga dalam radius 5% dari support/resistance terdekat
5. **Stop loss** — swing low terakhir, harus di bawah entry
6. **Risk-reward** — dihitung terhadap TP1; rasio minimal 1:2

Alert sinyal A menyertakan dua level take profit:
- **TP1** = resistance terdekat di atas entry (dipakai untuk kriteria risk-reward)
- **TP2** = resistance berikutnya di atas TP1; kalau tidak ada, fallback `entry + 2x risk` (kelipatan diatur via `tp2_risk_multiple`)

Semua angka di atas adalah default `config.yaml` dan bisa diubah tanpa menyentuh kode.

## Setup dari nol sampai alert pertama

### 1. Buat bot Telegram (via BotFather)

1. Buka Telegram, cari **@BotFather** (centang biru resmi).
2. Kirim `/newbot`, ikuti instruksi: beri nama (mis. `IDX Signal Bot`) dan username (harus diakhiri `bot`, mis. `idx_sinyal_saya_bot`).
3. BotFather membalas dengan **bot token** format `123456789:AAF...xyz`. Simpan, jangan dibagikan.
4. **Penting:** kirim pesan apa saja (mis. `/start`) ke bot barumu — bot tidak bisa memulai chat duluan.

### 2. Ambil chat ID

1. Buka di browser (ganti `<TOKEN>`):
   ```
   https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
2. Cari `"chat":{"id":123456789,...}` di respons JSON. Angka itu adalah **chat ID** kamu.
3. Kalau respons kosong, kirim pesan lagi ke bot lalu refresh.

### 3. Sesuaikan config.yaml

Edit daftar `tickers` (tanpa suffix `.JK`) dan threshold sesuai gaya trading:

```yaml
tickers:
  - BBCA
  - TLKM
```

### 4. Push ke GitHub

```bash
git remote add origin git@github.com:<username>/idx-signal-bot.git
git push -u origin main
```

### 5. Isi GitHub Secrets

Di repo GitHub: **Settings → Secrets and variables → Actions → New repository secret**:

| Nama | Isi |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token dari BotFather (langkah 1) |
| `TELEGRAM_CHAT_ID` | Chat ID (langkah 2) |

Token **hanya** disimpan sebagai secret — jangan pernah ditulis di kode atau config.

### 6. Uji manual

Di tab **Actions** repo GitHub, pilih workflow **Swing Signal Check** atau **Breakout Signal Check** → **Run workflow**. Cek log run-nya; kalau ada sinyal yang lolos, alert pertama masuk ke Telegram. Tidak ada sinyal = tidak ada pesan (by design, menghindari notification fatigue).

## Jalankan test lokal (sebelum push)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```

Semua test memakai data sample — tidak ada panggilan API asli.

Smoke test pipeline tanpa Telegram/API (pakai mock data): ubah sementara `data_source: mock` di `config.yaml`, lalu:

```bash
python -m src.main_swing
python -m src.main_breakout
```

## Sumber data

Default: **Yahoo Finance** via `yfinance` (ticker `.JK`). Gratis dan cukup stabil untuk data harian + volume, tapi **tidak resmi dan delayed** — cukup untuk sinyal 15-menitan, bukan tick-by-tick.

Sumber data memakai **adapter pattern** ([src/data_source.py](src/data_source.py)). Untuk ganti ke API resmi/berbayar: buat subclass `DataSource` baru, daftarkan di `create_data_source()`, ubah `data_source:` di config. Titik penggantian ditandai `>>> GANTI DI SINI <<<` di kode. Logic sinyal tidak perlu diubah sama sekali.

## Estimasi kuota GitHub Actions

Repo privat GitHub Free: **2.000 menit/bulan**.

| Workflow | Run/minggu | Durasi/run | Menit/bulan (±4,3 mgg) |
|---|---|---|---|
| Breakout (Sen–Kam 28x/hari, Jum 19x) | ±131 | ±1,5 mnt | ±850 |
| Swing (1x/hari bursa) | 5 | ±2,5 mnt | ±55 |
| **Total** | | | **±900 (45% kuota)** |

Masih aman, tapi kalau nanti mendekati batas (mis. tambah banyak ticker sehingga run melambat):
- jadikan repo **publik** → kuota tak terbatas, atau
- kurangi frekuensi sinyal B (mis. tiap 30 menit: ganti `*/15` jadi `*/30`).

## Struktur project

```
├── .github/workflows/
│   ├── swing_check.yml       # sinyal A, 1x sehari setelah closing
│   └── breakout_check.yml    # sinyal B, tiap 15 menit jam bursa
├── src/
│   ├── data_source.py        # adapter pattern (yahoo/mock)
│   ├── indicators.py         # MA, RSI, support/resistance, swing low (pure functions)
│   ├── signal_swing.py       # sinyal A: 6 kriteria berlapis
│   ├── signal_breakout.py    # sinyal B: breakout volume
│   ├── alert.py              # kirim ke Telegram
│   ├── main_swing.py         # orkestrasi sinyal A
│   └── main_breakout.py      # orkestrasi sinyal B
├── tests/                    # semua pakai data sample, tanpa API
├── config.yaml               # ticker + semua threshold
└── requirements.txt
```

## Batasan v1 (disengaja)

- Hanya dua sinyal di atas. MACD, Bollinger Bands, sentiment, bandarmology = v2, setelah v1 terbukti jalan.
- Tidak ada modul eksekusi order — broker ritel Indonesia belum punya API order resmi.
- Sinyal bukan rekomendasi; tetap lakukan analisis sendiri sebelum entry.
