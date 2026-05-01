"""Fetch full ETF overview from justETF and save to CSV."""

from justetf_scraping import load_overview

df = load_overview()
print(f"Columns: {list(df.columns)}")
print(f"Rows: {len(df)}")
df.to_csv("/output/justetf_all.csv")
print("Saved to /output/justetf_all.csv")
