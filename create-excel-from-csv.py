import pandas as pd

df_csv = pd.read_csv("bq-results-main-products.csv")

df_csv.to_excel("bg-results-vystupni_soubor.xlsx", index=False)
