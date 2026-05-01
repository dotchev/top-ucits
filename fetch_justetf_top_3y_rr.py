"""Fetch top JustETF funds by 3-year return/risk ratio."""

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
    "rank",
    "isin",
    "wkn",
    "ticker",
    "name",
    "three_year_return_risk",
    "three_year_return_percent",
    "three_year_volatility_percent",
    "one_year_return_risk",
    "five_year_return_risk",
    "currency",
    "ter_percent",
    "fund_size_m",
    "inception_date",
    "distribution",
    "replication",
    "domicile_country",
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


def output_row(rank: int, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "rank": rank,
        "isin": row.get("isin"),
        "wkn": row.get("wkn"),
        "ticker": row.get("ticker"),
        "name": clean_text(row.get("name")),
        "three_year_return_risk": parse_number(row.get("threeYearReturnPerRiskCUR")),
        "three_year_return_percent": parse_number(row.get("threeYearReturnCUR")),
        "three_year_volatility_percent": parse_number(row.get("threeYearVolatilityCUR")),
        "one_year_return_risk": parse_number(row.get("yearReturnPerRiskCUR")),
        "five_year_return_risk": parse_number(row.get("fiveYearReturnPerRiskCUR")),
        "currency": clean_text(row.get("fundCurrency")),
        "ter_percent": parse_number(row.get("ter")),
        "fund_size_m": parse_number(row.get("fundSize")),
        "inception_date": parse_date(row.get("inceptionDate")),
        "distribution": clean_text(row.get("distributionPolicy")),
        "replication": clean_text(row.get("replicationMethod")),
        "domicile_country": clean_text(row.get("domicileCountry")),
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
        for rank, row in enumerate(ranked_rows, start=1):
            writer.writerow(output_row(rank, row))

    fetched = sum(len(result.rows) for result in results)
    print(f"Fetched rows: {fetched}")
    print(f"Unique funds: {len(rows)}")
    print(f"Funds with 3y return/risk: {len(ranked_rows)}")
    print(f"Saved rows: {len(ranked_rows)}")


if __name__ == "__main__":
    main()
