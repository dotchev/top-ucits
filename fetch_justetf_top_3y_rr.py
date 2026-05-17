"""Fetch top JustETF funds by 3-year return/risk ratio.

Fetches ETF data from justetf.com across multiple strategy categories
(Long-only, Active, Short & Leveraged), merges duplicates, and ranks
funds by their 3-year return/risk ratio in descending order.

Sends 4 HTTP requests to justetf.com:
    1 GET to fetch the search page and extract a counter value,
    3 POSTs to fetch funds for each strategy category.

Input: HTTP requests to justetf.com search API (no local input files).
Output: justetf-top-3y-rr.csv — all funds sorted by 3-year return/risk
    ratio descending. Includes all properties from JustETF plus strategy.
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
    "ticker",
    "name",
    "isin",
    "wkn",
    "valor_number",
    "currency",
    "ter_percent",
    "distribution",
    "replication",
    "fund_size_m",
    "number_of_holdings",
    "inception_date",
    "domicile_country",
    "has_securities_lending",
    "sustainable",
    "week_return_percent",
    "month_return_percent",
    "three_month_return_percent",
    "six_month_return_percent",
    "ytd_return_percent",
    "one_year_return_percent",
    "one_year_return_risk",
    "one_year_volatility_percent",
    "one_year_max_drawdown_percent",
    "one_year_dividend_yield_percent",
    "year_return_1_percent",
    "year_return_2_percent",
    "year_return_3_percent",
    "year_return_4_percent",
    "three_year_return_percent",
    "three_year_return_risk",
    "three_year_volatility_percent",
    "three_year_max_drawdown_percent",
    "five_year_return_percent",
    "five_year_return_risk",
    "five_year_volatility_percent",
    "five_year_max_drawdown_percent",
    "max_drawdown_percent",
    "current_dividend_yield_percent",
    "strategy",
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
        "valor_number": row.get("valorNumber"),
        "name": clean_text(row.get("name")),
        "currency": clean_text(row.get("fundCurrency")),
        "ter_percent": parse_number(row.get("ter")),
        "distribution": clean_text(row.get("distributionPolicy")),
        "replication": clean_text(row.get("replicationMethod")),
        "fund_size_m": parse_number(row.get("fundSize")),
        "number_of_holdings": parse_number(row.get("numberOfHoldings")),
        "inception_date": parse_date(row.get("inceptionDate")),
        "domicile_country": clean_text(row.get("domicileCountry")),
        "has_securities_lending": clean_text(row.get("hasSecuritiesLending")),
        "sustainable": clean_text(row.get("sustainable")),
        "week_return_percent": parse_number(row.get("weekReturnCUR")),
        "month_return_percent": parse_number(row.get("monthReturnCUR")),
        "three_month_return_percent": parse_number(row.get("threeMonthReturnCUR")),
        "six_month_return_percent": parse_number(row.get("sixMonthReturnCUR")),
        "ytd_return_percent": parse_number(row.get("ytdReturnCUR")),
        "one_year_return_percent": parse_number(row.get("yearReturnCUR")),
        "one_year_return_risk": parse_number(row.get("yearReturnPerRiskCUR")),
        "one_year_volatility_percent": parse_number(row.get("yearVolatilityCUR")),
        "one_year_max_drawdown_percent": parse_number(row.get("yearMaxDrawdownCUR")),
        "one_year_dividend_yield_percent": parse_number(row.get("yearDividendYield")),
        "year_return_1_percent": parse_number(row.get("yearReturn1CUR")),
        "year_return_2_percent": parse_number(row.get("yearReturn2CUR")),
        "year_return_3_percent": parse_number(row.get("yearReturn3CUR")),
        "year_return_4_percent": parse_number(row.get("yearReturn4CUR")),
        "three_year_return_percent": parse_number(row.get("threeYearReturnCUR")),
        "three_year_return_risk": parse_number(row.get("threeYearReturnPerRiskCUR")),
        "three_year_volatility_percent": parse_number(row.get("threeYearVolatilityCUR")),
        "three_year_max_drawdown_percent": parse_number(row.get("threeYearMaxDrawdownCUR")),
        "five_year_return_percent": parse_number(row.get("fiveYearReturnCUR")),
        "five_year_return_risk": parse_number(row.get("fiveYearReturnPerRiskCUR")),
        "five_year_volatility_percent": parse_number(row.get("fiveYearVolatilityCUR")),
        "five_year_max_drawdown_percent": parse_number(row.get("fiveYearMaxDrawdownCUR")),
        "max_drawdown_percent": parse_number(row.get("maxDrawdownCUR")),
        "current_dividend_yield_percent": parse_number(row.get("currentDividendYield")),
        "strategy": row.get("strategy"),
    }


def return_risk_sort_key(row: dict[str, Any]) -> float:
    value = parse_number(row.get("threeYearReturnPerRiskCUR"))
    if value is None:
        return float("-inf")
    return value


def main() -> None:
    with requests.Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        counter = fetch_counter(session)
        results = [
            fetch_strategy(session, counter, strategy) for strategy in STRATEGIES
        ]

    rows = merged_rows(results)
    ranked_rows = [
        row
        for row in rows
        if parse_number(row.get("threeYearReturnPerRiskCUR")) is not None
    ]
    ranked_rows.sort(key=return_risk_sort_key, reverse=True)

    with open("justetf-top-3y-rr.csv", "w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        for row in ranked_rows:
            writer.writerow(output_row(row))

    fetched = sum(len(result.rows) for result in results)
    print(f"Fetched rows: {fetched}")
    print(f"Unique funds: {len(rows)}")
    print(f"Funds with 3y return/risk: {len(ranked_rows)}")
    print(f"Saved rows: {len(ranked_rows)}")


if __name__ == "__main__":
    main()
