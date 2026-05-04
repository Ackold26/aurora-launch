# Mediascope - Required Fields Spec

**Status:** v1.0 (2026-05-04)
**Sources:** Mediascope TV (panel-based ratings), Mediascope Digital, AdIndex Digital Budget

## Контекст

Mediascope - syndicated provider медиа-данных в РФ:
- **Mediascope TV** - panel-based audience measurements (TRP / GRP / budgets per channel/programme/demo)
- **Mediascope Digital** - panel-based digital impressions

**AdIndex Digital Budget** - alternative source для digital spend tracker (отдельная подписка).

Все три источника поддерживаются Aurora Launch для proxy media data.

**Доступ:** через подписку клиента / агентства. Aurora не покупает Mediascope напрямую.

---

## Section 1: Mediascope TV

### 1.1 Mandatory Fields

| Field | Type | Description | Example |
|---|---|---|---|
| `period_start` | date | ISO YYYY-MM-DD | 2024-08-05 |
| `period_end` | date | ISO YYYY-MM-DD | 2024-08-11 |
| `channel` | string | TV channel name | "Первый", "Россия 1", "НТВ", "СТС", "ТНТ" |
| `target_demo` | string | Демо-группа | "W 25-54", "M 18-44", "All 18+", "All 4+" |
| `trp` | float | Target Rating Points | 145.3 |
| `grp` | float | Gross Rating Points (All 4+) | 87.2 |
| `budget_rub` | float | Стоимость размещения, ₽ | 4500000 |
| `format_type` | enum | "spot" / "sponsorship" / "product_placement" | "spot" |

### 1.2 Recommended Fields

| Field | Type | Description |
|---|---|---|
| `daypart` | enum | "prime" / "off_prime" / "early_morning" / "late_night" |
| `programme_genre` | string | "news", "sports", "series", "movies", ... |
| `creative_id` | string | Идентификатор ролика (для creative analysis) |
| `creative_duration_sec` | int | Длительность в секундах (15/20/30 most common) |
| `quality_index` | float | Communication Quality Index (если доступен) |

### 1.3 Channel Standardization

**Aurora использует canonical channel names. Список актуален на 2026-05-04:**

| Mediascope name | Canonical | Note |
|---|---|---|
| "Первый канал" | "perviy" | Federal #1 (Channel One) |
| "Россия 1" | "rossiya_1" | Federal #2 (VGTRK) |
| "НТВ" | "ntv" | Federal (Gazprom-Media) |
| "Пятый канал" | "five" | Federal (НМГ) |
| "Россия 24" | "rossiya_24" | News (VGTRK) |
| "ТВ Центр" | "tv_centr" | |
| "ОТР" | "otr" | Public broadcasting |
| "СТС" | "sts" | Entertainment (НМГ) |
| "ТНТ" | "tnt" | Entertainment (Gazprom-Media) |
| "Пятница" | "friday" | Lifestyle (Gazprom-Media) |
| "ТВ-3" | "tv3" | Mystery / entertainment |
| "РЕН-ТВ" | "ren_tv" | НМГ |
| "Звезда" | "zvezda" | Defense Ministry |
| "Домашний" | "domashniy" | Female audience |
| "МАТЧ ТВ" | "match_tv" | Sports |
| "Спас" | "spas" | Religious |
| **Kids channels** | | |
| "Карусель" | "karusel" | State kids channel |
| "Мульт" | "mult" | Kids (НМГ) |
| "СТС Kids" | "sts_kids" | Kids (НМГ) |
| "Тлум HD" | "tlum_hd" | Kids cartoon |
| **Aggregate buckets** | | |
| (региональные) | "regional_aggregate" | All regional channels combined |
| (нишевые тематические) | "niche_thematic_aggregate" | Cable thematic channels combined |

Mapping table maintained в `engines/channel_canonical.yaml` (Phase A deliverable).

**Note:** список may evolve - federal landscape РФ периодически меняется. Адаптеры формата handle missing channels gracefully (fallback к "unknown_<name>").

### 1.4 Period Requirements

- **Minimum: 18 месяцев** weekly или monthly
- **Recommended: 24+ месяцев** (overlap с DSM data 24+)
- **Grain: weekly preferred** (better для adstock estimation)
- **Continuous coverage**: нет skipping weeks > 1 неделя

### 1.5 Sample Row Format (Mediascope TV 2024 export)

Excel format:

```
| Period_Start | Period_End | Channel    | Target_Demo  | TRP   | GRP   | Budget_RUB | Format_Type | Daypart |
| 2024-08-05   | 2024-08-11 | Первый     | W 25-54     | 145.3 | 87.2  | 4500000    | spot        | prime   |
| 2024-08-05   | 2024-08-11 | Россия 1   | W 25-54     | 132.7 | 79.4  | 3800000    | spot        | prime   |
| 2024-08-05   | 2024-08-11 | НТВ        | W 25-54     | 87.5  | 52.3  | 2400000    | spot        | prime   |
| 2024-08-12   | 2024-08-18 | Первый     | W 25-54     | 152.8 | 91.1  | 4700000    | spot        | prime   |
```

---

## Section 2: Mediascope Digital

### 2.1 Mandatory Fields

| Field | Type | Description |
|---|---|---|
| `period_start` | date | ISO YYYY-MM-DD |
| `period_end` | date | ISO YYYY-MM-DD |
| `platform` | string | Yandex / VK / Mail.ru / Telegram / programmatic networks |
| `placement_type` | enum | "context" / "display" / "video" / "native" |
| `impressions` | int | Показы |
| `budget_rub` | float | Бюджет, ₽ |

### 2.2 Recommended Fields

| Field | Type | Description |
|---|---|---|
| `clicks` | int | Клики |
| `ctr` | float | Click-through rate (% или decimal) |
| `views` | int | Просмотры video (для video placements) |
| `vtr` | float | View-through rate (% completion) |
| `target_demo` | string | Если доступно (digital панели) |
| `geo_code` | string | Если доступно |
| `device_type` | enum | "desktop" / "mobile" / "tablet" / "tv" |

### 2.3 Platform Standardization

**Актуально на 2026 (РФ digital landscape после консолидации 2022-2024):**

| Mediascope / vendor name | Canonical | Note |
|---|---|---|
| "Yandex Direct" | "yandex_direct" | Search ads |
| "Yandex РСЯ" | "yandex_rsya" | Display (advertising network) |
| "Yandex Display" | "yandex_display" | Premium display |
| "Yandex Видеосеть" | "yandex_video" | Video advertising |
| "VK Реклама" | "vk_ads" | Объединяет VK + бывший myTarget (sunset 2024) + Одноклассники |
| "Telegram Ads" | "telegram_ads" | Official Telegram Ads platform |
| **DSP / programmatic** | | |
| "Soloway" | "dsp_soloway" | Russian DSP |
| "Between Exchange" | "dsp_between" | Russian SSP/DSP |
| "Hybrid.ai" | "dsp_hybrid" | Russian DSP |
| "iSeller" | "dsp_iseller" | E-commerce DSP |
| **Premium publishers** | | |
| "Premium native" | "premium_native_aggregate" | Аggregate (Lenta, Forbes RU, Cosmo, etc.) |
| **Other / fallback** | | |
| "Other programmatic" | "programmatic_other" | Catch-all for небольших networks |

Note: Meta (Facebook/Instagram) - **не доступна в РФ для рекламы** с 2022; Google Ads - **suspended for РФ advertisers** с 2022. Эти platforms не входят в active catalog Aurora Launch.

### 2.4 Sample Row Format

```
| Period_Start | Period_End | Platform       | Placement_Type | Impressions | Budget_RUB | Clicks | CTR  |
| 2024-08-05   | 2024-08-11 | yandex_direct | context        | 2300000     | 850000     | 45000  | 1.96 |
| 2024-08-05   | 2024-08-11 | yandex_rsya   | display        | 1850000     | 420000     | 28000  | 1.51 |
| 2024-08-05   | 2024-08-11 | vk_ads        | display        | 1200000     | 290000     | 18500  | 1.54 |
| 2024-08-05   | 2024-08-11 | telegram_ads  | native         | 950000      | 380000     | 14200  | 1.49 |
```

---

## Section 3: Cross-validation TV vs Digital

### 3.1 Period overlap

- Both TV и Digital MUST overlap >= 12 месяцев с DSM data
- Total media data >= 18 месяцев

### 3.2 Sanity checks

- **CPP check (TV)**: budget_rub / TRP должно быть в reasonable range для категории / sub-категории / demo
  - W 25-54 prime spot: 200,000-400,000 ₽/TRP в 2024
  - All 4+: 80,000-180,000 ₽/TRP
  - Off-prime: ~60% от prime
- **CPM check (Digital)**: budget_rub / (impressions/1000) - reasonable for placement_type
  - Display: 50-300 ₽/CPM
  - Video: 200-800 ₽/CPM
  - Native: 300-1500 ₽/CPM
- **Aurora computes implied CPP/CPM**, flags outliers

### 3.3 Coverage check (Aurora-side validator)

```python
def cross_validate_media_coverage(
    tv_df: pd.DataFrame,
    digital_df: Optional[pd.DataFrame],
    dsm_df: pd.DataFrame,
) -> List[str]:
    issues = []

    tv_period = (tv_df["period_start"].min(), tv_df["period_end"].max())
    dsm_period = (dsm_df["period"].min(), dsm_df["period"].max())

    overlap_start = max(tv_period[0], dsm_period[0])
    overlap_end = min(tv_period[1], dsm_period[1])
    overlap_months = (overlap_end - overlap_start).days / 30

    if overlap_months < 12:
        issues.append(f"TV/DSM overlap < 12 months ({overlap_months:.1f})")

    if digital_df is not None:
        dig_period = (digital_df["period_start"].min(), digital_df["period_end"].max())
        # ... same check
        pass

    return issues
```

---

## Section 4: AdIndex Digital Budget (alternative source)

**Когда использовать:** клиент имеет AdIndex подписку но не Mediascope Digital.

### 4.0 AdIndex Format Detection

```python
# engines/data_adapters/adindex_format_detector.py

import pandas as pd

class AdIndexFormatDetector:
    """Detect AdIndex Digital Budget format version."""

    SIGNATURES = {
        "AI_BUDGET_V2024": frozenset([
            "period", "advertiser", "platform", "spend_rub",
        ]),
        "AI_BUDGET_V2023": frozenset([
            "period", "advertiser", "channel", "spend_rub",  # was "channel" not "platform"
        ]),
    }

    def detect(self, df: pd.DataFrame) -> str:
        cols = frozenset(c.lower().strip().replace(" ", "_") for c in df.columns)
        for version, signature in self.SIGNATURES.items():
            if signature.issubset(cols):
                return version
        raise ValueError(
            f"Unrecognized AdIndex format. Columns seen: {sorted(cols)[:10]}..."
        )
```

### 4.1 Differences vs Mediascope Digital

| Aspect | Mediascope Digital | AdIndex Digital Budget |
|---|---|---|
| Data type | Panel-based impressions | Syndicated spend tracker |
| Granularity | Platform + placement_type + demo | Platform + advertiser only |
| Frequency | Weekly | Monthly |
| Demo data | Available | Not available |
| Impressions | Yes | Estimated only |
| Cost data | Estimated | Direct (spend tracker) |

### 4.2 AdIndex Format

```
| Period   | Advertiser | Platform     | Spend_RUB |
| 2024-08  | Бренд X    | yandex       | 2300000   |
| 2024-08  | Бренд X    | vk           | 850000    |
| 2024-08  | Бренд X    | programmatic | 1100000   |
```

### 4.3 Aurora Launch supports both

Format adapter detects source format on import:
- `MediascopeDigitalFormatAdapter` для Mediascope
- `AdIndexBudgetFormatAdapter` для AdIndex

Output - common Aurora Launch internal media schema (см. `engines/launch_schema.py`).

**Tradeoff:** AdIndex data слабее на impressions level (estimated). Aurora forecasts с AdIndex source имеют wider CI - validator сообщает об этом.

---

## Section 5: Format Adapters

### 5.1 Known Mediascope TV format versions

| Version | Year | Key changes |
|---|---|---|
| MS_TV_V2023 | 2023 | Original column naming |
| MS_TV_V2024 | 2024 | Added quality_index, expanded daypart |

Note: V2025 adapter будет добавлен когда Mediascope опубликует 2025 формат (~июль 2026 ежегодное обновление). Plan B - manual mapping fallback для exotic / unknown formats.

### 5.2 Format adapter implementation

**`engines/data_adapters/mediascope_tv_v2024.py`**:

```python
from .base import MediascopeFormatAdapter
import pandas as pd

class MediascopeTVAdapterV2024(MediascopeFormatAdapter):
    """Adapter for Mediascope TV 2024 format."""

    COLUMN_MAP = {
        "Period_Start": "period_start",
        "Period_End": "period_end",
        "Channel": "channel_raw",
        "Target_Demo": "target_demo",
        "TRP": "trp",
        "GRP": "grp",
        "Budget_RUB": "budget_rub",
        "Format_Type": "format_type",
        "Daypart": "daypart",
        "Quality_Index": "quality_index",
    }

    def parse(self, file_path: Path) -> pd.DataFrame:
        df = pd.read_excel(file_path, sheet_name=0)
        df = df.rename(columns=self.COLUMN_MAP)

        # Date parsing
        df["period_start"] = pd.to_datetime(df["period_start"])
        df["period_end"] = pd.to_datetime(df["period_end"])

        # Channel canonicalization
        df["channel"] = df["channel_raw"].apply(self._canonicalize_channel)

        # Numeric coercion
        for col in ["trp", "grp", "budget_rub", "quality_index"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def _canonicalize_channel(self, raw_name: str) -> str:
        """Map raw Mediascope channel name to Aurora canonical."""
        # Use channel_canonical.yaml mapping
        return CHANNEL_CANONICAL_MAP.get(raw_name.strip(), f"unknown_{raw_name}")
```

---

## Section 6: Validator Rules

### 6.1 Coverage check

```python
def validate_mediascope_tv_coverage(df: pd.DataFrame) -> List[str]:
    issues = []
    weeks = df.groupby(["period_start"]).size().shape[0]
    if weeks < 78:  # 18 months ≈ 78 weeks
        issues.append(f"Only {weeks} weeks (need 78+ for 18 months)")

    # Detect gaps
    sorted_starts = sorted(df["period_start"].unique())
    for i in range(1, len(sorted_starts)):
        delta = (sorted_starts[i] - sorted_starts[i-1]).days
        if delta > 14:  # > 2 weeks gap
            issues.append(f"Gap >2 weeks between {sorted_starts[i-1]} and {sorted_starts[i]}")
    return issues
```

### 6.2 CPP sanity

```python
def validate_cpp_reasonable(df: pd.DataFrame) -> List[str]:
    issues = []
    df = df[df["trp"] > 0].copy()
    df["cpp"] = df["budget_rub"] / df["trp"]

    # Group by demo + daypart, check median CPP в ranges
    for (demo, daypart), group in df.groupby(["target_demo", "daypart"]):
        median_cpp = group["cpp"].median()
        expected_range = EXPECTED_CPP_RANGES.get((demo, daypart))
        if expected_range and not (expected_range[0] <= median_cpp <= expected_range[1]):
            issues.append(
                f"CPP out of range for {demo}/{daypart}: {median_cpp:.0f} ₽/TRP "
                f"(expected {expected_range[0]}-{expected_range[1]})"
            )
    return issues

EXPECTED_CPP_RANGES = {
    ("W 25-54", "prime"): (200_000, 400_000),
    ("W 25-54", "off_prime"): (120_000, 250_000),
    ("All 4+", "prime"): (80_000, 180_000),
    # ... maintained в config
}
```

### 6.3 Budget consistency

```python
def validate_budget_consistency(df: pd.DataFrame) -> List[str]:
    issues = []
    # Sum by month - sanity check на orders of magnitude
    monthly_budgets = df.groupby(df["period_start"].dt.to_period("M"))["budget_rub"].sum()
    if monthly_budgets.max() / monthly_budgets.median() > 50:
        issues.append("Suspicious monthly budget volatility (>50× max/median ratio)")
    if (df["budget_rub"] < 0).any():
        issues.append("Negative budget values detected")
    return issues
```

---

## Section 7: Special Cases

### 7.1 Brand с минимальной TV-активностью (digital-first launch)

- Mediascope TV может быть пустым / minimal
- Aurora supports digital-only proxy (если recipient тоже digital-first)
- Validator: warning "TV media insufficient - proxy/recipient must be digital-first"

### 7.2 Multi-target proxy brand

- Брендbiy могут таргетировать несколько демо-групп (W 25-54 + M 25-44 для FMCG)
- Aurora aggregates: weighted average TRP по target_demo proportions
- Or: train per-demo models separately (multi-output, Phase D feature)

### 7.3 Sponsorship vs spot

- Sponsorship - длительные форматы, разная adstock decay
- Aurora separates format_types в model (если both are present)
- Spec в S004 Adaptation Rules

---

## Связанные документы

- `DATA_REQUIREMENTS.md` - master spec (Sections 2.2, 2.3, 2.4)
- `DSM_FIELDS.md` - DSM companion data
- `RECIPIENT_ANCHORS.md` - recipient media plan
- `../03_Architecture/DATA_PRIVACY.md` - local-first handling
- `engines/channel_canonical.yaml` (Phase A) - channel mapping
