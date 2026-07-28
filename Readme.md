# GA4 to BigQuery Downloader

Python skript pro efektivní stahování statistik produktů z **Google Analytics 4 (GA4) API** a jejich ukládání do **Google BigQuery**. Skript stahuje data po měsíčních dávkách a filtruje je na základě seznamu ID.

## 🛠️ Požadavky a Instalace

1. Aktivujte své virtuální prostředí (`ga4-downloader`).
2. Nainstalujte potřebné knihovny:
   ```bash
   pip install -r requirements.txt
   ```

## ⚙️ Příprava před spuštěním

Do kořenové složky projektu vložte následující soubory (oba jsou ignorovány v `.gitignore`):

1. **`ga4_key.json`** – Přihlašovací klíč k service accountu z Google Cloud Console.
2. **`ids.csv`** – CSV soubor obsahující sloupec `id_polozky` se seznamem ID produktů, které chcete z GA4 stahovat.

## 🚀 Spuštění skriptu

Skript spusťte standardně přes terminál:

```bash
python nazev_vaseho_skriptu.py
```

- **První spuštění** smaže starou tabulku v BigQuery a založí novou (`WRITE_TRUNCATE`).
- **Následné dávky** data plynule přisypávají (`WRITE_APPEND`).
- Průběh stahování se živě vypisuje do konzole včetně indikátoru aktivity (teček).
