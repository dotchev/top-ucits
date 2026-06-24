"""Fetch JustETF fund data.

Fetches ETF data from justetf.com across multiple strategy categories
(Long-only, Active, Short & Leveraged) and merges duplicates by ISIN.

Sends 4 HTTP requests to justetf.com:
    1 GET to fetch the search page and extract a counter value,
    3 POSTs to fetch funds for each strategy category.

Input: HTTP requests to justetf.com search API (no local input files).
Output: justetf-funds.csv — one row per unique fund (deduplicated by ISIN),
    in the order returned by JustETF. Includes all properties from JustETF
    plus strategy. Filter and sort downstream as needed.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import datetime
from html import unescape
from typing import Any

import requests


BASE_URL = "https://www.justetf.com/en/search.html"
USER_AGENT = "My User Agent 1.0"

STRATEGIES = {
    "epg-longOnly": "Long-only",
    "epg-activeEtfs": "Active",
    "epg-shortAndLeveraged": "Short & Leveraged",
}

COUNTER_RE = re.compile(
    r"(\d)-1\.0-container-tabsContentContainer-tabsContentRepeater-1-"
    r"container-content-etfsTablePanel&search=ETFS&_wicket=1"
)

OUTPUT_COLUMNS = [
    "ticker",       # exchange ticker symbol
    "name",         # fund name
    "isin",         # International Securities Identification Number
    "wkn",          # German securities identification number (Wertpapierkennnummer)
    "valor",        # Swiss security identification number
    "ccy",          # fund base currency
    "ter_%",        # total expense ratio, percent per year
    "dist",         # distribution policy (distributing / accumulating)
    "repl",         # replication method (physical / synthetic)
    "size_m",       # fund size, millions
    "holdings",     # number of holdings
    "inception",    # inception date (ISO 8601)
    "domicile",     # country of domicile
    "sec_lending",  # whether the fund engages in securities lending
    "sustainable",  # whether the fund is classified as sustainable/ESG
    "1W_ret_%",     # 1-week return, percent
    "1M_ret_%",     # 1-month return, percent
    "3M_ret_%",     # 3-month return, percent
    "6M_ret_%",     # 6-month return, percent
    "YTD_ret_%",    # year-to-date return, percent
    "1Y_ret_%",     # trailing 1-year return, percent
    "1Y_rr",        # trailing 1-year return/risk ratio
    "1Y_vol_%",     # trailing 1-year volatility, percent
    "1Y_mdd_%",     # trailing 1-year max drawdown, percent
    "1Y_yield_%",   # trailing 1-year dividend yield, percent
    "Y1_ret_%",     # most recent calendar-year return, percent
    "Y2_ret_%",     # 2nd most recent calendar-year return, percent
    "Y3_ret_%",     # 3rd most recent calendar-year return, percent
    "Y4_ret_%",     # 4th most recent calendar-year return, percent
    "3Y_ret_%",     # trailing 3-year return, percent
    "3Y_rr",        # trailing 3-year return/risk ratio (primary sort key)
    "3Y_vol_%",     # trailing 3-year volatility, percent
    "3Y_mdd_%",     # trailing 3-year max drawdown, percent
    "5Y_ret_%",     # trailing 5-year return, percent
    "5Y_rr",        # trailing 5-year return/risk ratio
    "5Y_vol_%",     # trailing 5-year volatility, percent
    "5Y_mdd_%",     # trailing 5-year max drawdown, percent
    "mdd_%",        # max drawdown since inception, percent
    "yield_%",      # current dividend yield, percent
    "strategy",     # JustETF strategy category/categories
]


@dataclass
class FetchResult:
    rows: list[dict[str, Any]]
    records_total: int
    records_filtered: int


def parse_number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    text = str(value).strip().replace("%", "").replace(",", "")
    if not text:
        return None
    return float(text)


def clean_text(value: Any) -> str | None:
    if value in (None, "", "-"):
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(str(value)))).strip()


def parse_date(value: Any) -> str | None:
    text = clean_text(value)
    if text is None:
        return None
    return datetime.strptime(text, "%d.%m.%y").date().isoformat()


def fetch_counter(session: requests.Session) -> str:
    response = session.get(f"{BASE_URL}?search=ETFS", timeout=30)
    response.raise_for_status()
    match = COUNTER_RE.search(response.text)
    return match.group(1) if match else "0"


def fetch_strategy(
    session: requests.Session, counter: str, strategy: str
) -> FetchResult:
    response = session.post(
        (
            f"{BASE_URL}?{counter}-1.0-container-tabsContentContainer-"
            "tabsContentRepeater-1-container-content-etfsTablePanel="
            "&search=ETFS&_wicket=1"
        ),
        data={
            "draw": 1,
            "start": 0,
            "length": -1,
            "lang": "en",
            "country": "DE",
            "universeType": "private",
            "defaultCurrency": "EUR",
            "etfsParams": f"search=ETF&productGroup={strategy}&ls=any",
        },
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    rows = payload["data"]
    for row in rows:
        row["strategy"] = STRATEGIES[strategy]
    return FetchResult(
        rows=rows,
        records_total=payload["recordsTotal"],
        records_filtered=payload["recordsFiltered"],
    )


def merged_rows(results: list[FetchResult]) -> list[dict[str, Any]]:
    rows_by_isin: dict[str, dict[str, Any]] = {}
    for result in results:
        for row in result.rows:
            isin = row["isin"]
            if isin not in rows_by_isin:
                rows_by_isin[isin] = row
                continue

            existing = rows_by_isin[isin]
            strategy = row["strategy"]
            if strategy not in existing["strategy"]:
                existing["strategy"] = f"{existing['strategy']}, {strategy}"
    return list(rows_by_isin.values())


def output_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "isin": row.get("isin"),
        "wkn": row.get("wkn"),
        "ticker": row.get("ticker"),
        "valor": row.get("valorNumber"),
        "name": clean_text(row.get("name")),
        "ccy": clean_text(row.get("fundCurrency")),
        "ter_%": parse_number(row.get("ter")),
        "dist": clean_text(row.get("distributionPolicy")),
        "repl": clean_text(row.get("replicationMethod")),
        "size_m": parse_number(row.get("fundSize")),
        "holdings": parse_number(row.get("numberOfHoldings")),
        "inception": parse_date(row.get("inceptionDate")),
        "domicile": clean_text(row.get("domicileCountry")),
        "sec_lending": clean_text(row.get("hasSecuritiesLending")),
        "sustainable": clean_text(row.get("sustainable")),
        "1W_ret_%": parse_number(row.get("weekReturnCUR")),
        "1M_ret_%": parse_number(row.get("monthReturnCUR")),
        "3M_ret_%": parse_number(row.get("threeMonthReturnCUR")),
        "6M_ret_%": parse_number(row.get("sixMonthReturnCUR")),
        "YTD_ret_%": parse_number(row.get("ytdReturnCUR")),
        "1Y_ret_%": parse_number(row.get("yearReturnCUR")),
        "1Y_rr": parse_number(row.get("yearReturnPerRiskCUR")),
        "1Y_vol_%": parse_number(row.get("yearVolatilityCUR")),
        "1Y_mdd_%": parse_number(row.get("yearMaxDrawdownCUR")),
        "1Y_yield_%": parse_number(row.get("yearDividendYield")),
        "Y1_ret_%": parse_number(row.get("yearReturn1CUR")),
        "Y2_ret_%": parse_number(row.get("yearReturn2CUR")),
        "Y3_ret_%": parse_number(row.get("yearReturn3CUR")),
        "Y4_ret_%": parse_number(row.get("yearReturn4CUR")),
        "3Y_ret_%": parse_number(row.get("threeYearReturnCUR")),
        "3Y_rr": parse_number(row.get("threeYearReturnPerRiskCUR")),
        "3Y_vol_%": parse_number(row.get("threeYearVolatilityCUR")),
        "3Y_mdd_%": parse_number(row.get("threeYearMaxDrawdownCUR")),
        "5Y_ret_%": parse_number(row.get("fiveYearReturnCUR")),
        "5Y_rr": parse_number(row.get("fiveYearReturnPerRiskCUR")),
        "5Y_vol_%": parse_number(row.get("fiveYearVolatilityCUR")),
        "5Y_mdd_%": parse_number(row.get("fiveYearMaxDrawdownCUR")),
        "mdd_%": parse_number(row.get("maxDrawdownCUR")),
        "yield_%": parse_number(row.get("currentDividendYield")),
        "strategy": row.get("strategy"),
    }


def main() -> None:
    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        counter = fetch_counter(session)
        results = [
            fetch_strategy(session, counter, strategy) for strategy in STRATEGIES
        ]

    rows = merged_rows(results)

    with open("justetf-funds.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(output_row(row))

    fetched = sum(len(result.rows) for result in results)
    print(f"Fetched rows: {fetched}")
    print(f"Unique funds: {len(rows)}")
    print(f"Saved rows: {len(rows)}")


if __name__ == "__main__":
    main()
