# JustETF 3Y Return/Risk Notes

- Main generated output: `justetf-top-3y-rr.csv`.
- Regeneration script: `fetch_justetf_top_3y_rr.py`.
- Command: `python3 fetch_justetf_top_3y_rr.py`.
- The script fetches live data from `https://www.justetf.com/en/search.html`.
- It writes all funds that have a finite `threeYearReturnPerRiskCUR` value.
- Latest run fetched 4,766 raw rows, merged them into 4,238 unique funds by ISIN, found 2,867 funds with a 3Y return/risk value, and wrote 2,867 CSV data rows plus the header.
- The CSV is sorted descending by `three_year_return_risk`.
- Latest validation showed top row `XEON` at `22.17` and bottom row `XJSE` at `-1.28`.

## JustETF Requests

- The script makes 4 requests to `justetf.com` per run:
- 1 `GET /en/search.html?search=ETFS` to fetch the page and parse the dynamic Wicket counter.
- 3 `POST` requests to the screener endpoint, one for each product group.

## Product Groups

- `epg-longOnly`: standard long-only products, usually passive buy-and-hold ETFs/ETCs.
- `epg-activeEtfs`: actively managed ETFs.
- `epg-shortAndLeveraged`: leveraged and inverse products.
- The POST payload sends these as `etfsParams=search=ETF&productGroup=<group>&ls=any`.
- Rows from the three groups are merged by ISIN; if an ISIN appears in multiple groups, the script combines the strategy labels.

## Output Columns

- Required columns included: `ticker`, `name`, `three_year_return_risk`.
- Additional columns currently written: `rank`, `isin`, `wkn`, `three_year_return_percent`, `three_year_volatility_percent`, `one_year_return_risk`, `five_year_return_risk`, `currency`, `ter_percent`, `fund_size_m`, `inception_date`, `distribution`, `replication`, `domicile_country`, `strategy`.
- The script strips embedded HTML such as `<br />` from text fields and converts JustETF `dd.mm.yy` dates to ISO `yyyy-mm-dd`.
