import os
from dotenv import load_dotenv
import sys
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google.cloud import bigquery
from google.oauth2 import service_account

# ==============================================================================
# Configuration
# ==============================================================================
load_dotenv()

KEY_FILE = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
PROPERTY_ID = os.getenv("GA4_PROPERTY_ID")
PROJECT_ID = os.getenv("BQ_PROJECT_ID")
DATASET_ID = os.getenv("BQ_DATASET_ID")
TABLE_ID = os.getenv("BQ_TABLE_ID")

START_TOTAL = datetime.strptime("2025-01-01", "%Y-%m-%d")
END_TOTAL = datetime.strptime("2026-07-15", "%Y-%m-%d")

API_LIMIT = 100000
# ==============================================================================

print("🚀 Startuji kompletní import všech dat s partitioningem a clusteringem...")

try:
    # Inicializace GA4 a BigQuery klientů
    credentials = service_account.Credentials.from_service_account_file(
        KEY_FILE)
    ga4_client = BetaAnalyticsDataClient(credentials=credentials)
    bq_client = bigquery.Client(project=PROJECT_ID, credentials=credentials)

    # Proměnné pro BigQuery
    full_table_path = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    je_to_prvni_zapis = True

    # Výpočet celkového počtu měsíců
    celkem_mesicu = 0
    temp_datum = START_TOTAL.replace(day=1)
    while temp_datum <= END_TOTAL:
        celkem_mesicu += 1
        temp_datum += relativedelta(months=1)

    # Inicializace proměnných pro hlavní smyčku
    index_mesice = 0
    celkem_odeslano_radku = 0
    aktualni_mesic = START_TOTAL.replace(day=1)

    while aktualni_mesic <= END_TOTAL:

        # Nastavení proměnných pro vizualizaci
        index_mesice += 1
        procento_casu = int((index_mesice / celkem_mesicu) * 100)

        # Chceme začít od skutečného startu nastaveného uživatelem
        skutecny_start = max(START_TOTAL, aktualni_mesic)
        pripadny_konec = aktualni_mesic + \
            relativedelta(months=1) - relativedelta(days=1)
        skutecny_konec = min(END_TOTAL, pripadny_konec)

        # Nastavení proměnných pro query
        start_str = skutecny_start.strftime("%Y-%m-%d")
        end_str = skutecny_konec.strftime("%Y-%m-%d")

        print(
            f"\n📅 [{index_mesice}/{celkem_mesicu} | {procento_casu}%] Období: {start_str} až {end_str}")

        # Inicializace proměnných pro smyčku pagination
        offset = 0
        radku_v_mesici = 0

        while True:
            print("  ⏳ Komunikuji s GA4 API... ", end="")
            sys.stdout.flush()

            request = RunReportRequest(
                property=f"properties/{PROPERTY_ID}",
                dimensions=[
                    Dimension(name="itemId"),
                    Dimension(name="date")
                ],
                metrics=[
                    Metric(name="itemRevenue"),
                    Metric(name="itemsViewed"),
                    Metric(name="itemsPurchased")
                ],
                date_ranges=[
                    DateRange(start_date=start_str, end_date=end_str)],
                limit=API_LIMIT,
                offset=offset
            )

            response = ga4_client.run_report(request)

            if not response.rows:
                print("žádná další data v tomto měsíci.")
                break

            print("Data přijata. Zpracovávám: ", end="")
            sys.stdout.flush()

            dim_headers = [dim.name for dim in response.dimension_headers]
            metric_headers = [
                metric.name for metric in response.metric_headers]
            vsechny_hlavicky = dim_headers + metric_headers

            vycistena_data = []
            for i, row in enumerate(response.rows):
                textove_hodnoty = [v.value for v in row.dimension_values]
                ciselne_hodnoty = [v.value for v in row.metric_values]
                vycistena_data.append(textove_hodnoty + ciselne_hodnoty)

                if (i + 1) % 10000 == 0:
                    print(".", end="")
                    sys.stdout.flush()

            df = pd.DataFrame(vycistena_data, columns=vsechny_hlavicky)

            # Bez filtrace: Převod textu na formát DATE bez času
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d").dt.date
            df["itemRevenue"] = df["itemRevenue"].astype(float)
            df["itemsViewed"] = df["itemsViewed"].astype(int)
            df["itemsPurchased"] = df["itemsPurchased"].astype(int)

            pocet_radku = len(df)
            radku_v_mesici += pocet_radku
            celkem_odeslano_radku += pocet_radku

            print(f" Hotovo (načteno {pocet_radku:,} řádků).")

            # 🟢 KROK: Inicializace tabulky s optimalizací
            if je_to_prvni_zapis:
                print(
                    f"  📥 [RESET] Zakládám novou optimalizovanou tabulku s partitioningem...")

                # Smazání staré tabulky, pokud existuje
                bq_client.delete_table(full_table_path, not_found_ok=True)

                # Definice pevného schématu tabulky
                schema = [
                    bigquery.SchemaField("itemId", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
                    bigquery.SchemaField("itemRevenue", "FLOAT64"),
                    bigquery.SchemaField("itemsViewed", "INTEGER"),
                    bigquery.SchemaField("itemsPurchased", "INTEGER"),
                ]

                nova_tabulka = bigquery.Table(full_table_path, schema=schema)
                nova_tabulka.time_partitioning = bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY,
                    field="date"
                )
                nova_tabulka.clustering_fields = ["itemId"]

                bq_client.create_table(nova_tabulka)
                dispozice_zapisu = bigquery.WriteDisposition.WRITE_APPEND
                je_to_prvni_zapis = False
            else:
                dispozice_zapisu = bigquery.WriteDisposition.WRITE_APPEND

            # Odeslání dávky do BigQuery
            print(f"  📥 Odesílám dávku do BigQuery... ", end="")
            sys.stdout.flush()

            job_config = bigquery.LoadJobConfig(
                write_disposition=dispozice_zapisu)
            job = bq_client.load_table_from_dataframe(
                df, full_table_path, job_config=job_config)
            job.result()

            print(
                f"Uloženo. (V měsíci: {radku_v_mesici:,} | Celkem v cloudu: {celkem_odeslano_radku:,} řádků)")

            # Kontrola stránkování (Pokud přišlo méně dat než limit, je to poslední stránka)
            if len(vycistena_data) < API_LIMIT:
                break
            offset += API_LIMIT

        # Přechod na další měsíc
        aktualni_mesic += relativedelta(months=1)

    print("\n✅ Všechna data byla úspěšně stažena a uložena do BigQuery bez filtrace!")

except Exception as e:
    print(f"\n❌ Neočekávaná chyba během běhu skriptu: {e}")
    sys.exit(1)
