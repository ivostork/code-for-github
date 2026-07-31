import os
import re
from google.cloud import bigquery
from google.oauth2 import service_account
from dotenv import load_dotenv
import pandas as pd
import unidecode

# 1. NAČTENÍ ENVIRONMENT PROMĚNNÝCH
load_dotenv()

# Automatické načtení z vašeho .env
PROJECT_ID = os.getenv("BQ_PROJECT_ID")
DATASET_ID = os.getenv("BQ_DATASET_ID")
TABLE_ID = os.getenv("BQ_TABLE_ID2")  # Použije 'main_product_id'
CREDENTIALS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

# Kontrola, zda jsou všechny potřebné proměnné v .env přítomny
if not all([PROJECT_ID, DATASET_ID, TABLE_ID, CREDENTIALS_PATH]):
    raise ValueError(
        "V souboru .env chybí některá z klíčových proměnných "
        "(BQ_PROJECT_ID, BQ_DATASET_ID, BQ_TABLE_ID2, GOOGLE_APPLICATION_CREDENTIALS)."
    )

# 2. NAČTENÍ A OČISTA DAT Z CSV
print("Načítám a čistím data z CSV...")
df = pd.read_csv("ids.csv")

# Pročištění názvů sloupců
new_columns = []
for c in df.columns:
    # Odstranění diakritiky, whitespaces a převod na malá písmena
    c_cleaned = unidecode.unidecode(c).strip().lower()
    # Náhrada mezer podtržítkem
    c_cleaned = re.sub(r" ", r"_", c_cleaned)
    # Odstranění závorek a hvězdiček
    c_cleaned = re.sub(r"[()*]", r"", c_cleaned)
    new_columns.append(c_cleaned)

df.columns = new_columns

# EXPLICITNÍ PŘETYPOVÁNÍ ID NA STRING
if "id_polozky" in df.columns:
    df["id_polozky"] = df["id_polozky"].astype(str)

# Očištění hodnot ve sloupci s cenou a PŘETYPOVÁNÍ NA FLOAT
target_price_col = "koncovy_zakaznik_s_dph"

if target_price_col in df.columns:
    # Odstraní 'Kč' a všechny mezery (např. '1 579 Kč' -> '1579')
    df[target_price_col] = df[target_price_col].astype(str).str.replace(
        r"[^\d]", "", regex=True
    )
    # Přetypování na FLOAT (desetinné číslo)
    df[target_price_col] = pd.to_numeric(
        df[target_price_col], errors="coerce").astype(float)

# 3. AUTENTIKACE A INICIALIZACE BIGQUERY KLIENTA
print("Připojuji se k Google BigQuery...")
credentials = service_account.Credentials.from_service_account_file(
    CREDENTIALS_PATH
)
client = bigquery.Client(credentials=credentials, project=PROJECT_ID)

# Sestavení plné cesty k tabulce (project.dataset.table)
full_table_path = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"

# 4. KONFIGURACE A SPOUŠTĚNÍ IMPORTU DO BIGQUERY
job_config = bigquery.LoadJobConfig(
    # WRITE_TRUNCATE: přepíše tabulku při každém spuštění novými daty
    write_disposition="WRITE_TRUNCATE",
    # Automaticky určí správné datové typy v BigQuery podle Pandas
    autodetect=True,
)

print(f"Nahrávám DataFrame do tabulky {full_table_path}...")
try:
    # Spuštění nahrávání
    job = client.load_table_from_dataframe(
        df, full_table_path, job_config=job_config
    )

    # Čekání na dokončení operace
    job.result()

    print("---")
    print(f"Úspěch! Do tabulky bylo nahráno {df.shape[0]} řádků.")

except Exception as e:
    print("---")
    print(f"Během nahrávání došlo k chybě:\n{e}")
