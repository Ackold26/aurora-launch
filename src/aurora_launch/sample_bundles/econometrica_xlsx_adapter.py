"""XLSX adapter для Эконометрика wide-format test datasets (Phase Σ.0.4).

Reads Materia Medica's standard data export format (DSM Group / Mediascope
normalised) и returns structured EconometricaDataset for downstream
synthetic-posterior derivation.

Wide-format schema (per actual test files):

    Date  | OLV Показы | OLV Просмотры | OLV Бюджет до НДС до АК
          | Banners Показы | Banners Клики | Banners Визиты | Banners Бюджет
          | Social Показы | Social Клики | Social Визиты | Social Бюджет
          | Retail Media показы | Retail Media бюджет
          | Performance Клики | Performance Визиты | Performance Бюджет
          | Статьи прочтения | Статьи Бюджет
          | (Спецпроекты прочтения | Спецпроекты Бюджет)
          | Кол-во запросов
          | Продажи в руб. бренд | Продажи в руб. конкуренты | SOM в руб
          | Продажи в уп. бренд | Продажи в уп. конкуренты | SOM в уп.

Per channel we extract Бюджет (spend) as the primary regressor. Adstock /
hill response then learns from spend → sales correlations.

Date column may be in Russian month form "январь 2023" — normalised к
ISO format YYYY-MM-DD (first of month).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

_log = logging.getLogger(__name__)


class EconometricaXLSXError(ValueError):
    """Raised on schema mismatch / parsing failure."""


_RUS_MONTHS: dict[str, int] = {
    "январь": 1, "января": 1,
    "февраль": 2, "февраля": 2,
    "март": 3, "марта": 3,
    "апрель": 4, "апреля": 4,
    "май": 5, "мая": 5,
    "июнь": 6, "июня": 6,
    "июль": 7, "июля": 7,
    "август": 8, "августа": 8,
    "сентябрь": 9, "сентября": 9,
    "октябрь": 10, "октября": 10,
    "ноябрь": 11, "ноября": 11,
    "декабрь": 12, "декабря": 12,
}


CHANNEL_PATTERNS: list[tuple[str, str]] = [
    # (channel_id, header_keyword_match_lowercase)
    ("olv", "olv бюджет"),
    ("banners", "banners бюджет"),
    ("social", "social бюджет"),
    ("retail_media", "retail media бюджет"),
    ("performance", "performance бюджет"),
    ("articles", "статьи бюджет"),
    ("specials", "спецпроект бюджет"),
]

SALES_BRAND_KEYWORDS: list[str] = [
    "продажи в руб. бренд",
    "продажи в руб бренд",
    "продажи в руб. бренда",
]
SALES_COMPETITORS_KEYWORDS: list[str] = [
    "продажи в руб. конкуренты",
    "продажи в руб конкуренты",
]


@dataclass(frozen=True)
class EconometricaDataset:
    """Normalised view of one Эконометрика XLSX sheet."""

    brand_id: str  # opaque identifier (from sheet name или caller)
    granularity: str  # "monthly" (Эконометрика test data is monthly)
    n_periods: int
    dates_iso: list[str]  # ISO YYYY-MM-DD format
    channel_ids: list[str]
    spend_by_channel: dict[str, list[float]]  # channel_id → spend per period
    sales_brand: list[float]
    sales_competitors: list[float]
    raw_headers: list[str] = field(default_factory=list)


def _normalise_header(s: str) -> str:
    """Strip whitespace, line breaks, normalise case for header matching."""
    return " ".join(s.lower().replace("\n", " ").replace("\r", " ").split())


def _parse_russian_month(label: str) -> str | None:
    """Convert 'январь 2023' style label → ISO 'YYYY-MM-01'.

    Returns None if не parseable (для caller to handle gracefully).
    """
    if not isinstance(label, str):
        return None
    parts = label.strip().lower().split()
    if len(parts) != 2:
        return None
    month_word, year_str = parts
    month = _RUS_MONTHS.get(month_word)
    if month is None:
        return None
    try:
        year = int(year_str)
    except ValueError:
        return None
    if not 2000 <= year <= 2100:
        return None
    return f"{year:04d}-{month:02d}-01"


def _coerce_numeric(value: Any) -> float | None:
    """Convert "3,836,962 ₽" → 3836962.0; "5.19" → 5.19; "" → None."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and np.isnan(value):
            return None
        return float(value)
    if not isinstance(value, str):
        return None
    cleaned = value.strip().replace("\xa0", "").replace(" ", "")
    cleaned = cleaned.replace("₽", "").replace(",", "").strip()
    if cleaned == "" or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _detect_sheet_name(xlsx_path: Path, requested: str | None) -> str:
    """Use first sheet если caller didn't specify."""
    sheets = pd.ExcelFile(xlsx_path).sheet_names
    if not sheets:
        raise EconometricaXLSXError(f"No sheets в {xlsx_path}")
    if requested is not None:
        if requested not in sheets:
            raise EconometricaXLSXError(
                f"Sheet {requested!r} not found в {xlsx_path}. "
                f"Available: {sheets}"
            )
        return requested
    return sheets[0]


def _find_channel_column(headers_normalised: list[str], keyword: str) -> int | None:
    """Match by substring (handles wrapping line breaks in original headers)."""
    for i, h in enumerate(headers_normalised):
        if keyword in h:
            return i
    return None


def _find_sales_column(headers_normalised: list[str], keywords: Iterable[str]) -> int | None:
    for kw in keywords:
        for i, h in enumerate(headers_normalised):
            if kw in h:
                return i
    return None


def load_econometrica_xlsx(
    xlsx_path: str | Path,
    *,
    sheet_name: str | None = None,
    brand_id: str | None = None,
) -> EconometricaDataset:
    """Parse one Эконометрика XLSX sheet → normalised dataset.

    Args:
        xlsx_path: path к .xlsx file
        sheet_name: optional sheet name (defaults к first sheet)
        brand_id: optional opaque identifier (defaults к sheet_name)

    Returns:
        EconometricaDataset с structured spend + sales data

    Raises:
        EconometricaXLSXError: file unreadable, schema mismatch
    """
    xlsx_path = Path(xlsx_path)
    if not xlsx_path.exists():
        raise EconometricaXLSXError(f"File not found: {xlsx_path}")

    target_sheet = _detect_sheet_name(xlsx_path, sheet_name)

    try:
        df = pd.read_excel(xlsx_path, sheet_name=target_sheet, dtype=object)
    except Exception as exc:
        raise EconometricaXLSXError(
            f"Cannot read {xlsx_path}::{target_sheet}: {exc}"
        ) from exc

    if df.empty:
        raise EconometricaXLSXError(f"Sheet {target_sheet!r} is empty")

    raw_headers = list(df.columns.astype(str))
    norm_headers = [_normalise_header(h) for h in raw_headers]

    # First column = Date / Месяц
    date_col = 0  # Convention: первый столбец = date
    dates_raw = df.iloc[:, date_col].tolist()
    dates_iso: list[str] = []
    valid_rows: list[int] = []
    for row_idx, raw in enumerate(dates_raw):
        iso = _parse_russian_month(str(raw)) if raw is not None else None
        if iso is None:
            # Try pandas parsing (если уже datetime)
            try:
                ts = pd.to_datetime(raw, errors="coerce")
                if not pd.isna(ts):
                    iso = ts.strftime("%Y-%m-01")
            except (ValueError, TypeError):
                pass
        if iso is not None:
            dates_iso.append(iso)
            valid_rows.append(row_idx)
    if not valid_rows:
        raise EconometricaXLSXError(
            f"No valid date rows found в {target_sheet!r}. "
            f"Expected Russian month format ('январь 2023') or datetime."
        )

    # Detect channels by spend column presence
    spend_by_channel: dict[str, list[float]] = {}
    channel_ids: list[str] = []
    for ch_id, keyword in CHANNEL_PATTERNS:
        col_idx = _find_channel_column(norm_headers, keyword)
        if col_idx is None:
            continue
        spend_series = df.iloc[valid_rows, col_idx]
        spend_values = [
            (_coerce_numeric(v) or 0.0) for v in spend_series.tolist()
        ]
        # Drop channel if all zero — Эконометрика sometimes has placeholder columns
        if any(v > 0 for v in spend_values):
            spend_by_channel[ch_id] = spend_values
            channel_ids.append(ch_id)

    if not channel_ids:
        raise EconometricaXLSXError(
            f"No active media channels found в {target_sheet!r}. "
            f"Headers: {raw_headers[:10]}..."
        )

    # Sales columns
    sales_brand_idx = _find_sales_column(norm_headers, SALES_BRAND_KEYWORDS)
    sales_comp_idx = _find_sales_column(norm_headers, SALES_COMPETITORS_KEYWORDS)
    if sales_brand_idx is None:
        raise EconometricaXLSXError(
            f"Sales brand column not found в {target_sheet!r}"
        )
    sales_brand_raw = df.iloc[valid_rows, sales_brand_idx].tolist()
    sales_brand = [(_coerce_numeric(v) or 0.0) for v in sales_brand_raw]

    if sales_comp_idx is not None:
        sales_comp_raw = df.iloc[valid_rows, sales_comp_idx].tolist()
        sales_competitors = [(_coerce_numeric(v) or 0.0) for v in sales_comp_raw]
    else:
        sales_competitors = [0.0] * len(valid_rows)

    final_brand_id = brand_id or target_sheet

    _log.info(
        "Loaded Эконометрика dataset: brand=%s, n_periods=%d, channels=%s",
        final_brand_id,
        len(valid_rows),
        channel_ids,
    )

    return EconometricaDataset(
        brand_id=final_brand_id,
        granularity="monthly",
        n_periods=len(valid_rows),
        dates_iso=dates_iso,
        channel_ids=channel_ids,
        spend_by_channel=spend_by_channel,
        sales_brand=sales_brand,
        sales_competitors=sales_competitors,
        raw_headers=raw_headers,
    )
