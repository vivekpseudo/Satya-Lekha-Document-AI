from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import re
from typing import Iterable


@dataclass
class FinancialRow:
    label: str
    values: list[Decimal | None]
    source_page: int | None = None
    bbox: dict | None = None


def parse_amount(value: str) -> Decimal | None:
    if not value:
        return None
    s = value.strip().replace(",", "").replace("₹", "")
    if s in {"-", "—", "–", ""}:
        return None

    negative = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    s = re.sub(r"[^0-9.\-]", "", s)

    try:
        number = Decimal(s)
    except InvalidOperation:
        return None
    return -number if negative else number


def normalize_table_rows(
    rows: Iterable[list[str]], source_page: int | None = None
) -> list[FinancialRow]:
    normalized = []

    for row in rows:
        if not row:
            continue
        first = row[0] or {}
        first_text = first.get("text", "") if isinstance(first, dict) else str(first)
        label = " ".join(first_text.split())
        if not label:
            continue

        values = [
            parse_amount(cell.get("text", "") if isinstance(cell, dict) else str(cell))
            for cell in row[1:]
        ]
        if not any(value is not None for value in values):
            continue

        bbox = first.get("bbox") if isinstance(first, dict) else None
        normalized.append(
            FinancialRow(label=label, values=values, source_page=source_page, bbox=bbox)
        )

    return normalized


def classify_statement_rows(
    rows: Iterable[FinancialRow], statement_type: str
) -> dict[str, list[FinancialRow]]:
    groups = {
        "assets": [], "liabilities": [], "equity": [],
        "income": [], "expenses": [], "other": [],
    }

    keyword_map = {
        "assets": ["cash", "bank", "receivable", "inventory", "property", "plant",
                   "equipment", "investment", "asset"],
        "liabilities": ["payable", "borrowings", "loan", "lease liability",
                         "provision", "liability", "debt"],
        "equity": ["share capital", "reserves", "retained earnings", "equity"],
        "income": ["revenue", "income", "sales", "profit", "interest income"],
        "expenses": ["cost", "expense", "depreciation", "employee benefits",
                     "finance cost", "tax expense"],
    }

    for row in rows:
        label = row.label.lower()
        for group, keywords in keyword_map.items():
            if any(keyword in label for keyword in keywords):
                groups[group].append(row)
                break
        else:
            groups["other"].append(row)

    return groups
