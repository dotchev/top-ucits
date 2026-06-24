# JustETF Fund Data

Fetches the full ETF/ETC universe from [justetf.com](https://www.justetf.com)
and saves it as one CSV row per unique fund. The single script
[fetch_justetf_funds.py](fetch_justetf_funds.py) fetches the data and writes the
CSV. It does no filtering or ranking — filter and sort the output downstream as
you need.

## What it does

1. Loads the JustETF search page and parses a dynamic [Wicket](https://wicket.apache.org/)
   counter that the screener endpoint requires.
2. Queries the screener endpoint once per **strategy category**:
   - `epg-longOnly` → *Long-only* (passive buy-and-hold ETFs/ETCs)
   - `epg-activeEtfs` → *Active* (actively managed ETFs)
   - `epg-shortAndLeveraged` → *Short & Leveraged* (leveraged/inverse products)
3. Merges results by ISIN. If the same ISIN appears in more than one category,
   the strategy labels are combined (e.g. `Long-only, Active`).
4. Writes every unique fund to [justetf-funds.csv](justetf-funds.csv), in the
   order returned by JustETF.

Exactly **4 HTTP requests** are made per run: 1 `GET` for the page + counter,
and 3 `POST`s to the screener (one per strategy). There are no local input
files — all data is fetched live.

## Usage

Create a virtual environment and install dependencies (first time only):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt    # requests, pandas
```

Then, in each new shell, activate the venv and run the script:

```bash
source .venv/bin/activate          # Windows: .venv\Scripts\activate
python3 fetch_justetf_funds.py
```

On completion it overwrites `justetf-funds.csv` and prints a summary:

```
Fetched rows: <raw rows across all strategies>
Unique funds: <after merging by ISIN>
Saved rows: <written to CSV>
```

A typical run fetches ~4,800 raw rows and writes ~4,200 unique funds.

## Output columns

Rows are in JustETF's native order.Column names use compact abbreviations
(periods: `1W`/`1M`/`3M`/`6M`/`YTD`/`1Y`/`3Y`/`5Y`; metrics: `_ret_%` return,
`_rr` return/risk, `_vol_%` volatility, `_mdd_%` max drawdown, `_yield_%`
dividend yield). `Y1`–`Y4` are discrete calendar-year returns (most recent
first), distinct from the trailing `1Y` window.

| Column | Meaning |
| --- | --- |
| `ticker`, `name` | Exchange ticker and fund name |
| `isin`, `wkn`, `valor` | Security identifiers (ISIN, German WKN, Swiss Valor) |
| `ccy` | Fund base currency |
| `ter_%` | Total expense ratio (% per year) |
| `dist` | Distribution policy (distributing / accumulating) |
| `repl` | Replication method (physical / synthetic) |
| `size_m` | Fund size (millions) |
| `holdings` | Number of holdings |
| `inception` | Inception date (ISO 8601) |
| `domicile` | Country of domicile |
| `sec_lending` | Whether the fund engages in securities lending |
| `sustainable` | Whether classified as sustainable / ESG |
| `1W_ret_%` … `YTD_ret_%` | Trailing returns over 1W/1M/3M/6M and year-to-date |
| `1Y_ret_%`, `1Y_rr`, `1Y_vol_%`, `1Y_mdd_%`, `1Y_yield_%` | Trailing 1-year return, return/risk, volatility, max drawdown, dividend yield |
| `Y1_ret_%` … `Y4_ret_%` | Discrete calendar-year returns, most recent first |
| `3Y_ret_%`, `3Y_rr`, `3Y_vol_%`, `3Y_mdd_%` | Trailing 3-year metrics |
| `5Y_ret_%`, `5Y_rr`, `5Y_vol_%`, `5Y_mdd_%` | Trailing 5-year metrics |
| `mdd_%` | Max drawdown since inception |
| `yield_%` | Current dividend yield |
| `strategy` | JustETF strategy category/categories |

Full per-column descriptions live next to `OUTPUT_COLUMNS` in
[fetch_justetf_funds.py](fetch_justetf_funds.py).

## Notes for coding agents

- **Single source of truth for the schema** is `OUTPUT_COLUMNS` in the script.
  `output_row()` maps raw JustETF JSON keys (e.g. `threeYearReturnPerRiskCUR`)
  to these output names — when changing columns, keep both in sync or
  `csv.DictWriter` will raise on the mismatch.
- The screener endpoint requires the dynamic Wicket counter from the page; don't
  hard-code it. See `fetch_counter()` / `COUNTER_RE`.
- `parse_number`, `clean_text`, and `parse_date` normalize values: strip `%` and
  thousands separators, remove embedded HTML (e.g. `<br />`), and convert
  JustETF `dd.mm.yy` dates to ISO `yyyy-mm-dd`.
- Be polite to the API — this is live third-party data. Avoid extra requests for
  fields derivable from data already in hand.
