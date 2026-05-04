# DSM Group - Required Fields Spec

**Status:** v1.0 (2026-05-04)
**Source:** DSM Group monthly Excel выгрузки (РФ pharma + retail panel)

## Контекст

DSM Group - один из ключевых syndicated data providers в РФ. Monthly retail audit с географической грануляцией (РФ + города). Используется как primary source proxy sales data в Aurora Launch для pharma + FMCG.

**Доступ:** через подписку клиента (rosskaya / pharma manufacturer / FMCG agency). Aurora Launch не покупает DSM напрямую - клиент / агентство приносит выгрузку.

**Format versioning:** DSM меняет column naming + grain в новых версиях своих отчётов. Aurora Launch использует Format Adapters pattern для multi-version support (см. `03_Architecture/`).

---

## Section 1: Mandatory Fields

### 1.1 Brand Identification

| Field | Type | Description | Example |
|---|---|---|---|
| `brand_id` | string | DSM internal brand ID | "B12345" |
| `brand_name` | string | Brand name | "Кагоцел" |
| `manufacturer` | string | Производитель / corporation | "Ниармедик" |

### 1.2 Period

| Field | Type | Description | Example |
|---|---|---|---|
| `period` | string | YYYY-MM | "2024-08" |

### 1.3 Geo

| Field | Type | Description | Example |
|---|---|---|---|
| `geo_code` | string | Geographic identifier | "RF_total" / "MSK" / "SPB" / city codes |
| `geo_name` | string | Human-readable | "Россия" / "Москва" |

### 1.4 Sales Metrics

| Field | Type | Description | Required |
|---|---|---|---|
| `sales_rub` | float | Продажи в рублях | YES |
| `sales_packs` | int | Продажи в упаковках (units) | YES |
| `avg_price_rub_per_pack` | float | Средняя цена за упаковку = sales_rub / sales_packs | DERIVED |

### 1.5 Distribution Metrics

| Field | Type | Description | Range | Required |
|---|---|---|---|---|
| `distribution_numeric_pct` | float | % торговых точек где продаётся бренд | 0..100 | YES |
| `distribution_weighted_pct` | float | % взвешенный по обороту | 0..100 | YES |

### 1.6 Penetration (опционально для some categories)

| Field | Type | Description | Range | Required |
|---|---|---|---|---|
| `penetration_pct` | float | % покупателей категории, купивших бренд | 0..100 | RECOMMENDED |

### 1.7 Pricing

| Field | Type | Description | Required |
|---|---|---|---|
| `price_shelf_avg` | float | Средняя цена на полке, ₽ | YES |
| `price_wholesale_avg` | float | Средняя оптовая цена, ₽ | RECOMMENDED |

---

## Section 2: Recommended Fields (boost forecast accuracy)

### 2.1 SKU Breakdown

| Field | Type | Description |
|---|---|---|
| `sku_id` | string | DSM internal SKU code |
| `sku_name` | string | SKU name (форма выпуска / упаковка) |
| `sku_dosage` | string | Pharma dosage (если применимо) |
| `sku_packaging` | string | "10 tab", "20 tab", etc. |

### 2.2 Category Context

| Field | Type | Description |
|---|---|---|
| `atc_class` | string | ATC class (для pharma): N02BE51, R05CA10, ... |
| `category_name` | string | Категория: "противопростудные", "молочка", ... |
| `subcategory_name` | string | Sub-category: "противовирусные пероральные", "йогурты литровые", ... |
| `category_total_rub` | float | Общий объём категории за period (для market context) |
| `category_total_packs` | int | Общий объём категории, упаковки |

### 2.3 Promo Context (если есть)

| Field | Type | Description |
|---|---|---|
| `promo_share_pct` | float | % продаж по промо |
| `discount_avg_pct` | float | Средняя глубина скидки |

---

## Section 3: Period Requirements

### Coverage

- **Minimum: 24 непрерывных месяцев** (для adstock + hill calibration)
- **Recommended: 36+ месяцев** (для категорийной сезонности + trend)
- **No gaps > 1 месяц** в continuous period
- **Recent data**: latest period должен быть не старше 3 месяцев на момент Aurora Launch проекта

### Edge cases

- **DSM data discontinued for brand** (бренд снят с производства) - не подходит как прокси
- **DSM coverage incomplete** (нет некоторых месяцев) - validator detects gaps + блокирует если > MAX_GAP

---

## Section 4: Sample Row Format (DSM 2024 export)

Excel format с следующими columns:

```
| Brand_ID | Brand | Manufacturer | Period   | Geo  | Sales_RUB | Sales_Packs | Distr_Num_% | Distr_Wt_% | Pen_% | Price_Shelf | Price_Wholesale |
| B12345   | Кагоцел | Ниармедик   | 2024-08  | RF   | 425000000 | 1850000     | 87.3        | 91.2       | 8.5   | 230         | 195             |
| B12345   | Кагоцел | Ниармедик   | 2024-08  | MSK  | 95000000  | 410000      | 92.1        | 95.4       | 12.3  | 232         | 197             |
| B12345   | Кагоцел | Ниармедик   | 2024-09  | RF   | 480000000 | 2100000     | 88.1        | 92.0       | 9.2   | 229         | 195             |
```

---

## Section 5: Format Adapters (multi-version support)

### 5.1 Known DSM format versions

| Version | Year | Key changes |
|---|---|---|
| V2022 | 2022 | Original column naming, RF only |
| V2023 | 2023 | Added city breakdown, renamed "Sales_RUB" → "Sales_Rubles" |
| V2024 | 2024 | Added penetration, expanded ATC class structure |

Note: V2025 adapter будет добавлен когда DSM Group опубликует 2025 формат (~июль 2026 ежегодное обновление). Plan B - manual mapping fallback для exotic / unknown formats.

### 5.2 Auto-detection logic

**`engines/data_adapters/dsm_format_detector.py`**:

```python
import pandas as pd
from typing import Literal

DSMFormatVersion = Literal["V2022", "V2023", "V2024", "V2025"]

class DsmFormatDetector:
    """Auto-detect DSM Excel format version от headers."""

    SIGNATURES = {
        "V2024": frozenset([
            "brand_id", "brand", "manufacturer", "period", "geo",
            "sales_rub", "sales_packs", "distr_num_%", "distr_wt_%",
            "pen_%", "price_shelf", "price_wholesale",
        ]),
        "V2023": frozenset([
            "brand_id", "brand", "manufacturer", "period", "geo",
            "sales_rubles", "sales_packs", "distr_num_%", "distr_wt_%",
            "price_shelf", "price_wholesale",
        ]),
        "V2022": frozenset([
            "brand", "manufacturer", "period",
            "sales_rub", "sales_packs", "distribution_%", "price_avg",
        ]),
    }

    def detect(self, df: pd.DataFrame) -> DSMFormatVersion:
        cols = frozenset(c.lower().strip().replace(" ", "_") for c in df.columns)
        for version, signature in self.SIGNATURES.items():
            if signature.issubset(cols):
                return version  # type: ignore
        raise ValueError(
            f"Unrecognized DSM format. Columns: {sorted(cols)[:10]}..."
        )
```

### 5.3 Format adapter

**`engines/data_adapters/dsm_v2024.py`**:

```python
from .base import DsmFormatAdapter
import pandas as pd

class DsmFormatAdapterV2024(DsmFormatAdapter):
    """Adapter for DSM 2024 format."""

    COLUMN_MAP = {
        "Brand_ID": "brand_id",
        "Brand": "brand_name",
        "Manufacturer": "manufacturer",
        "Period": "period",
        "Geo": "geo_code",
        "Sales_RUB": "sales_rub",
        "Sales_Packs": "sales_packs",
        "Distr_Num_%": "distribution_numeric_pct",
        "Distr_Wt_%": "distribution_weighted_pct",
        "Pen_%": "penetration_pct",
        "Price_Shelf": "price_shelf_avg",
        "Price_Wholesale": "price_wholesale_avg",
    }

    def parse(self, file_path: Path) -> pd.DataFrame:
        df = pd.read_excel(file_path, sheet_name=0)
        df = df.rename(columns=self.COLUMN_MAP)
        df["period"] = pd.to_datetime(df["period"], format="%Y-%m")
        # Sanity coercion
        df["sales_rub"] = pd.to_numeric(df["sales_rub"], errors="coerce")
        df["sales_packs"] = pd.to_numeric(df["sales_packs"], errors="coerce")
        # ... full implementation
        return df
```

---

## Section 6: Validator Rules

### 6.1 Coverage check

```python
def check_coverage(df: pd.DataFrame) -> List[str]:
    issues = []
    months = pd.to_datetime(df["period"]).dt.to_period("M").unique()
    if len(months) < 24:
        issues.append(f"Only {len(months)} months (need 24+)")

    # Detect gaps
    sorted_months = sorted(months)
    for i in range(1, len(sorted_months)):
        delta = (sorted_months[i].to_timestamp() - sorted_months[i-1].to_timestamp()).days
        if delta > 35:  # > 1 month gap
            issues.append(f"Gap detected between {sorted_months[i-1]} and {sorted_months[i]}")
    return issues
```

### 6.2 Currency consistency

```python
def check_currency_consistency(df: pd.DataFrame) -> List[str]:
    issues = []
    # Sales_RUB должен быть в RUB только (sanity на orders of magnitude)
    if df["sales_rub"].max() / df["sales_rub"].median() > 1000:
        issues.append("Suspicious sales magnitude - possibly mixed currencies")
    if (df["sales_rub"] < 0).any():
        issues.append("Negative sales values detected")
    return issues
```

### 6.3 Distribution range

```python
def check_distribution_range(df: pd.DataFrame) -> List[str]:
    issues = []
    if (df["distribution_numeric_pct"] < 0).any() or (df["distribution_numeric_pct"] > 100).any():
        issues.append("distribution_numeric_pct out of 0..100 range")
    if (df["distribution_weighted_pct"] < df["distribution_numeric_pct"]).any():
        issues.append(
            "distribution_weighted_pct < distribution_numeric_pct in some rows "
            "(weighted should be >= numeric for established brands)"
        )
    return issues
```

---

## Section 7: Special Cases

### 7.1 Pharma (DSM Pharma audit)

- ATC class обязателен для valid pharma proxy match
- Rx vs OTC distinction critical (нельзя transfer Rx -> OTC поведение)
- Promo data обычно недоступно (pharma не promo'ится в classical sense)

### 7.2 FMCG (DSM Retail audit)

- Sub-category match critical (молочка != snacks)
- Promo data важна (promo lift может dominate launch period)
- Private label brands - special case (не подходят как прокси для national brands)

### 7.3 Multi-SKU brands

- Если прокси имеет много SKU - aggregate на brand level или выбрать lead SKU?
- Decision rule (S003): brand-level aggregate если recipient single-SKU launching, lead SKU если recipient multi-SKU portfolio

---

## Связанные документы

- `DATA_REQUIREMENTS.md` - master spec (Section 2.1)
- `MEDIASCOPE_FIELDS.md` - Mediascope companion data
- `RECIPIENT_ANCHORS.md` - что recipient собирает
- `../03_Architecture/DATA_PRIVACY.md` - local-first handling DSM data
