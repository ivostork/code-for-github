import os
from dotenv import load_dotenv
from google.cloud import bigquery
from google.oauth2 import service_account

# 1. Načtení konfigurace
load_dotenv()

KEY_FILE = "ga4_key.json"
PROJECT_ID = os.getenv("BQ_PROJECT_ID")
DATASET_ID = os.getenv("BQ_DATASET_ID")
TABLE_ID = os.getenv("BQ_TABLE_ID2")
SHEET_URL = os.getenv("SHEET_URL")


def run_import():
    if not all([PROJECT_ID, DATASET_ID, TABLE_ID, SHEET_URL]):
        print("❌ Chyba: V souboru .env chybí některé proměnné (BQ_PROJECT_ID, BQ_DATASET_ID, BQ_TABLE_ID2, SHEET_URL).")
        return

    print(f"🚀 Zahajuji import a transformaci sloupců do: {TABLE_ID}")

    try:
        scopes = ["https://www.googleapis.com/auth/bigquery",
                  "https://www.googleapis.com/auth/drive"]
        credentials = service_account.Credentials.from_service_account_file(
            KEY_FILE, scopes=scopes)
        client = bigquery.Client(project=PROJECT_ID, credentials=credentials)

        final_table_path = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
        staging_table_path = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}_staging"

        # --- KROK 1: Dočasné propojení ---
        external_config = bigquery.ExternalConfig("GOOGLE_SHEETS")
        external_config.source_uris = [SHEET_URL]
        external_config.options.skip_leading_rows = 1
        external_config.autodetect = True

        staging_table = bigquery.Table(staging_table_path)
        staging_table.external_data_configuration = external_config
        client.delete_table(staging_table_path, not_found_ok=True)
        client.create_table(staging_table)

        # --- KROK 2: SQL s přejmenováním a čištěním ---
        # Zde definujeme, jak se mají sloupce přejmenovat a vyčistit
        sql_query = f"""
        CREATE OR REPLACE TABLE `{final_table_path}` AS
        SELECT 
            CAST(id_polozk AS STRING) as id_polozky,
            `Název položky` as Nazev_polozky,
            Dodavatel,
            Výrobce as Vyrobce,
            CAST(
                REPLACE(
                    REGEXP_REPLACE(`Koncový zákazník`, r'[^0-9,.]', ''), 
                    ',', '.'
                ) AS FLOAT64
            ) as Koncovy_zakaznik,
            `Počet variant` as Pocet_variant,
            `Počet obrázků` as Pocet_obrazku
        FROM `{staging_table_path}`
        """

        print("  - Čistím názvy sloupců, odstraňuji diakritiku a měnu...")
        query_job = client.query(sql_query)
        query_job.result()

        # --- KROK 3: Úklid ---
        client.delete_table(staging_table_path)

        print(
            f"✅ HOTOVO! Tabulka `{TABLE_ID}` byla vytvořena s čistými názvy:")
        print(
            f"   - Nazev_polozky, Vyrobce, Koncovy_zakaznik, Pocet_variant, Pocet_obrazku")

    except Exception as e:
        print(f"❌ Chyba: {e}")


if __name__ == "__main__":
    run_import()
